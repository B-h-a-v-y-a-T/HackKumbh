"""
Async Pipeline Worker — Real-time background processing engine.

Decouples frame acquisition, YOLO-pose inference, Part 2 risk analysis,
and visualization onto a dedicated high-performance background thread.
Provides zero-latency latest-frame buffers to WebSockets and MJPEG endpoints.

Runs the full pipeline:
  Part 1 (Perception) → Part 2 (Behaviour) → ROI Bridge → Part 3 (ROI triggers)
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.behaviour.adapter import pipeline_output_to_frame_input
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.behaviour.mock_generator.stream_generator import MockPoseStreamGenerator
from app.behaviour.roi_bridge import should_trigger_roi, get_trigger_for_events
from app.roi.cropper import ROICropper
from app.roi.quality import ImageQualityAnalyzer, CLAHEPreprocessor
from app.roi.temporal import TemporalSmoother
from app.roi.consensus import TemporalConsensusTracker
from app.models.base import ModelRegistry
from app.schemas.common import TriggerType, ObjectDetection
from app.schemas.evidence import EvidenceEvent
from app.perception.core.constants import KP_LEFT_WRIST, KP_RIGHT_WRIST, KP_NOSE

logger = logging.getLogger(__name__)

# Global worker instance
_worker: Optional[AsyncPipelineWorker] = None


def get_worker() -> Optional[AsyncPipelineWorker]:
    """Get the global pipeline worker instance."""
    return _worker


def set_worker(worker: AsyncPipelineWorker) -> None:
    """Set the global pipeline worker instance."""
    global _worker
    _worker = worker


class AsyncPipelineWorker:
    """
    High-throughput asynchronous pipeline engine running at 25+ FPS.

    Processes frames through:
    1. Part 1: Perception pipeline (person detection, pose, tracking, spatial ROI)
    2. Part 2: Behaviour risk engine (individual + spatial group intelligence)
    3. Part 3: High-resolution cropping, YOLO contraband detection,
       and temporal consensus tracking.
    4. Canonical Evidence Events: Single source of truth for overlays, risk, events & alerts.
    """

    def __init__(self, media_dir: Optional[Path] = None, mock_mode: bool = True):
        self.media_dir = media_dir or Path("media")
        self.risk_engine = BehaviourRiskEngine()
        self.mock_generator = MockPoseStreamGenerator()
        self._mock_mode = mock_mode

        # Part 3 ROI Pipeline Components & Temporal Consensus Tracker
        self.cropper = ROICropper(detector_input_size=640)
        self.quality_analyzer = ImageQualityAnalyzer()
        self.clahe_proc = CLAHEPreprocessor()
        self.temporal_smoother = TemporalSmoother(
            window_sizes={"mobile_phone": 5, "paper_chit": 4, "prohibited_object": 5},
            thresholds={"mobile_phone": 0.55, "paper_chit": 0.45, "prohibited_object": 0.50},
        )
        self.consensus_tracker = TemporalConsensusTracker(window_sec=3.0)
        self._active_trigger_tracks: Dict[str, Dict[str, Any]] = {}
        self._continuous_roi_scan = False
        self._custom_detector = None
        self._canonical_events: List[Dict[str, Any]] = []
        self._event_counter = 1000

        # Source configuration
        self._source_mode = "live"
        self._video_path: Optional[str] = None
        self._pipeline = None  # PerceptionPipeline instance
        self._video_cap: Optional[cv2.VideoCapture] = None

        # Thread management
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Thread-safe latest outputs
        self._latest_jpeg: Optional[bytes] = None
        self._latest_packet: Optional[Dict[str, Any]] = None
        self._frame_id = 0
        self._fps_actual = 0.0

        # Triggered tracks for Part 3 ROI bridge
        self._triggered_tracks: Dict[str, Dict[str, Any]] = {}
        self._last_roi_scan_frame: Dict[str, int] = {}
        self._cached_roi_dets: Dict[str, Any] = {}
        # Dedicated non-blocking ThreadPoolExecutor for background phone detection
        self._phone_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="AsyncPhoneDetector")
        self._phone_future: Optional[Future] = None
        self._cached_phone_dets: List[Dict[str, Any]] = []
        self._cached_roboflow_metrics: Dict[str, Any] = {}
        self._last_async_scan_time: float = 0.0

        from app.perception.visualization.debug_visualizer import DebugVisualizer
        self._visualizer = DebugVisualizer(enabled=True)

    def set_continuous_roi_scan(self, enabled: bool) -> None:
        """Enable or disable diagnostic continuous ROI scanning."""
        with self._lock:
            self._continuous_roi_scan = enabled
        logger.info("Continuous ROI scan: %s", "ENABLED" if enabled else "DISABLED")

    def _get_object_detector(self):
        """Retrieve the active object detector from ModelRegistry."""
        try:
            registry = ModelRegistry.get_instance()
            return registry.get_detector("live")
        except Exception:
            if self._custom_detector is None:
                from app.models.yolo_detector import MockYOLO26SDetector
                self._custom_detector = MockYOLO26SDetector()
                self._custom_detector.load("cpu")
            return self._custom_detector

    @property
    def source_mode(self) -> str:
        return self._source_mode

    @property
    def video_path(self) -> Optional[str]:
        return self._video_path

    @property
    def fps_actual(self) -> float:
        return self._fps_actual

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            return
        self.switch_source("live", camera_id=0)
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="PipelineWorker"
        )
        self._thread.start()
        logger.info("AsyncPipelineWorker thread started.")

    def stop(self) -> None:
        """Stop the background worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._release_pipeline()
        logger.info("AsyncPipelineWorker thread stopped.")

    def _release_pipeline(self) -> None:
        """Safely close active pipeline resources."""
        with self._lock:
            pipe = self._pipeline
            self._pipeline = None
            cap = self._video_cap
            self._video_cap = None
        if pipe is not None:
            try:
                pipe.video_source.release()
            except Exception:
                pass
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def set_source(self, mode: str, video_path: Optional[str] = None) -> None:
        """Alias for switch_source for API compatibility."""
        self.switch_source(mode=mode, video_path=video_path)

    def switch_source(self, mode: str, video_path: Optional[str] = None, camera_id: int = 0) -> None:
        """Switch between simulation mock, local video file, or live hardware webcam."""
        with self._lock:
            already_active = False
            if mode == self._source_mode:
                if mode == "live" and (self._pipeline is not None or self._video_cap is not None):
                    already_active = True
                elif mode == "video" and video_path == self._video_path and (self._pipeline is not None or self._video_cap is not None):
                    already_active = True
                elif mode == "mock":
                    already_active = True
            if already_active:
                logger.info("Source already active: %s (%s), skipping re-init", mode, video_path)
                return
        new_pipeline = None
        new_cap = None

        if mode in ("video", "live"):
            try:
                src = video_path or self._video_path or "demo_feed_1.mp4"
                if mode == "live":
                    cam_source = 0
                else:
                    if not os.path.isabs(str(src)):
                        resolved = (self.media_dir / str(src)).resolve()
                        if resolved.exists():
                            src = str(resolved)
                        elif Path(str(src)).exists():
                            src = str(Path(str(src)).resolve())
                    cam_source = src

                # Try initializing real perception pipeline
                try:
                    from app.config import get_settings
                    from app.perception.pipeline.perception_pipeline import PerceptionPipeline
                    settings = get_settings()
                    dev = settings.perception_device
                    if dev in ("auto", "cuda"):
                        try:
                            import torch
                            dev = "cuda:0" if torch.cuda.is_available() else "cpu"
                        except Exception:
                            dev = "cpu"

                    new_pipeline = PerceptionPipeline(config={
                        "camera": {"source": cam_source},
                        "detection": {
                            "confidence": 0.18,
                            "model": "yolo11n-pose.pt",
                            "device": dev,
                            "imgsz": 640,
                        },
                        "output": {"destination": "none"},
                        "visualization": {"enabled": False},
                    })
                    if not new_pipeline.video_source.open():
                        new_pipeline = None
                except Exception as ex:
                    logger.warning("Could not initialize full YOLO perception pipeline: %s. Using video decoder fallback.", ex)
                    new_pipeline = None

                # If PerceptionPipeline not loaded, open via OpenCV VideoCapture
                if new_pipeline is None:
                    if isinstance(cam_source, int) and os.name == 'nt':
                        cap = cv2.VideoCapture(cam_source, cv2.CAP_DSHOW)
                    else:
                        cap = cv2.VideoCapture(cam_source if isinstance(cam_source, int) else str(cam_source))
                    if cap.isOpened():
                        new_cap = cap
                        logger.info("Opened video capture fallback on: %s", cam_source)
                    else:
                        logger.warning("Video source could not be opened: %s", cam_source)

            except Exception as e:
                logger.error("Failed to set source: %s", e)

        with self._lock:
            old_pipeline = self._pipeline
            old_cap = self._video_cap
            self._pipeline = new_pipeline
            self._video_cap = new_cap
            self._source_mode = mode
            if video_path:
                self._video_path = video_path

        if old_pipeline is not None:
            try:
                old_pipeline.video_source.release()
            except Exception:
                pass
        if old_cap is not None:
            try:
                old_cap.release()
            except Exception:
                pass

        logger.info("Worker switched source to: %s (%s)", mode, self._video_path)

    def get_latest_frame(self) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], float]:
        """O(1) non-blocking read of the latest frame JPEG and telemetry packet."""
        with self._lock:
            return self._latest_jpeg, self._latest_packet, self._fps_actual

    def get_triggered_tracks(self) -> Dict[str, Dict[str, Any]]:
        """Get tracks that have been triggered for Part 3 ROI detection."""
        with self._lock:
            result = dict(self._triggered_tracks)
            self._triggered_tracks.clear()
            return result

    def _worker_loop(self) -> None:
        """Core high-FPS processing loop running on dedicated worker thread."""
        target_fps = 30.0
        frame_interval = 1.0 / target_fps
        last_calc_time = time.perf_counter()
        fps_counter = 0

        while self._running:
            t0 = time.perf_counter()

            try:
                with self._lock:
                    mode = self._source_mode
                    pipeline = self._pipeline
                    cap = self._video_cap

                if mode in ("video", "live") and pipeline is not None and pipeline.video_source._opened:
                    # 1. Full Perception Pipeline with YOLO-pose & Part 3 ROI extraction
                    self._process_real_frame(pipeline)
                elif mode in ("video", "live") and cap is not None and cap.isOpened():
                    # 2. Video Capture with Synthetic Overlay
                    self._process_video_fallback(cap)
                elif mode == "client_live":
                    # 3. Client Webcam Mode (Browser handles camera, WebSocket handles annotations)
                    pass
                elif mode == "live":
                    # 4. Live camera connecting frame (Never show orange line mock simulation!)
                    self._process_connecting_frame()
                else:
                    # 5. Full Synthetic Classroom Simulation (only for explicit mock mode)
                    self._process_mock_frame()

                fps_counter += 1
                now = time.perf_counter()
                if now - last_calc_time >= 1.0:
                    self._fps_actual = fps_counter / (now - last_calc_time)
                    fps_counter = 0
                    last_calc_time = now

            except Exception as e:
                logger.exception("Error in worker loop: %s", e)

            elapsed = time.perf_counter() - t0
            sleep_needed = frame_interval - elapsed
            if sleep_needed > 0.003:
                time.sleep(sleep_needed)

    def _process_connecting_frame(self) -> None:
        """Render a sleek, high-tech dark camera connecting frame while live hardware webcam initializes."""
        self._frame_id += 1
        canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
        canvas[:] = (12, 16, 20)
        for y in range(0, 720, 60):
            cv2.line(canvas, (0, y), (1280, y), (22, 28, 36), 1)
        for x in range(0, 1280, 80):
            cv2.line(canvas, (x, 0), (x, 720), (22, 28, 36), 1)
        cx, cy = 640, 340
        pulse = int((math.sin(time.time() * 4) + 1.0) * 15)
        cv2.circle(canvas, (cx, cy), 50 + pulse, (30, 45, 60), 2, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), 35, (255, 122, 42), 2, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), 8, (255, 122, 42), -1, cv2.LINE_AA)
        title = "DHRISTI AI  LIVE WEBCAM PERCEPTION"
        sub = "CONNECTING HIGH-FPS HARDWARE SENSOR..."
        cv2.putText(canvas, title, (cx - 240, cy + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2, cv2.LINE_AA)
        cv2.putText(canvas, sub, (cx - 220, cy + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 230, 118), 1, cv2.LINE_AA)
        _, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 72, cv2.IMWRITE_JPEG_OPTIMIZE, 0])
        packet = {
            "type": "FRAME_TELEMETRY",
            "frame_id": self._frame_id,
            "timestamp_ms": time.time() * 1000.0,
            "scenario": "CONNECTING",
            "source_mode": self._source_mode,
            "tracks": [],
            "groups": [],
            "triggered_tracks": {},
            "canonical_events": [],
            "roboflow_debug": {},
            "latency_ms": 5.0,
            "fps": 30.0,
        }
        with self._lock:
            self._latest_jpeg = buf.tobytes()
            self._latest_packet = packet

    def _process_real_frame(self, pipeline) -> None:
        """Process a real video frame through Part 1 → Part 3 ROI extraction → Part 2 Evidence Fusion."""
        from app.perception.capture.video_source import SourceType, StreamStatus

        success, raw_frame, health = pipeline.video_source.read()

        if not success or raw_frame is None:
            if hasattr(pipeline.video_source, '_source_type') and \
               pipeline.video_source._source_type == SourceType.VIDEO_FILE and \
               pipeline.video_source._cap is not None:
                pipeline.video_source._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                pipeline.video_source._stream_status = StreamStatus.CONNECTED
                success, raw_frame, health = pipeline.video_source.read()

        if not success or raw_frame is None:
            self._process_connecting_frame()
            return

        if success and raw_frame is not None:
            self._frame_id += 1
            now = time.time()

            # 1. Part 1: Perception Pipeline (Detection, Pose, Tracking, Spatial ROI)
            p1_output = pipeline.process_frame(raw_frame, health)

            # 2. Part 3: Asynchronous Non-Blocking Roboflow Phone Detection (0ms main thread latency)
            object_detections_by_track: Dict[str, List[dict]] = {}
            temporal_scores_by_track: Dict[str, float] = {}

            full_frame_phone_dets, roboflow_metrics = self._poll_async_phone_detection(
                raw_frame, p1_output.students if p1_output else []
            )

            # Associate full-frame Roboflow phone detections with student tracks
            if p1_output and p1_output.students and full_frame_phone_dets:
                for p_det in full_frame_phone_dets:
                    p_box = p_det.get("bbox") or []
                    p_conf = float(p_det.get("confidence", 0.0))
                    cls_name = str(p_det.get("class_name", "PHONE")).upper()
                    is_permitted = p_det.get("is_permitted", False) or (cls_name == "CALCULATOR")

                    if is_permitted:
                        continue

                    if len(p_box) == 4 and p_conf >= 0.15:
                        pcx = (p_box[0] + p_box[2]) / 2.0
                        pcy = (p_box[1] + p_box[3]) / 2.0
                        best_student = None
                        min_dist = float("inf")
                        for student in p1_output.students:
                            if student.bbox:
                                s_bbox = student.bbox
                                if (s_bbox.x1 - 60 <= pcx <= s_bbox.x2 + 60) and (s_bbox.y1 - 60 <= pcy <= s_bbox.y2 + 80):
                                    dist = ((pcx - (s_bbox.x1 + s_bbox.x2)/2)**2 + (pcy - (s_bbox.y1 + s_bbox.y2)/2)**2) ** 0.5
                                    if dist < min_dist:
                                        min_dist = dist
                                        best_student = student
                        if best_student:
                            tid = best_student.track_id
                            c_dict = {
                                "object_class": "PHONE",
                                "confidence": p_conf,
                                "bbox": p_box,
                                "persistence_sec": 1.0,
                                "detection_count": p_det.get("history_count", 1),
                                "is_confirmed": True,
                            }
                            object_detections_by_track[tid] = [c_dict]
                            temporal_scores_by_track[tid] = p_conf

            for student in p1_output.students:
                tid = student.track_id
                if student.desk_roi and student.desk_roi.bbox:
                    droi = student.desk_roi.bbox
                    roi_coords = [int(droi.x1), int(droi.y1), int(droi.x2), int(droi.y2)]

                    # Check trigger status
                    is_active = (tid in self._active_trigger_tracks) or self._continuous_roi_scan

                    # Dynamic trigger activation when wrist genuinely leaves desk boundary
                    if not is_active and student.keypoints:
                        lw_x, lw_y, lw_c = student.keypoints.get_point(KP_LEFT_WRIST)
                        rw_x, rw_y, rw_c = student.keypoints.get_point(KP_RIGHT_WRIST)
                        left_out = (lw_c > 0.30 and (lw_y > droi.y2 + 10 or lw_y < droi.y1 - 20 or lw_x < droi.x1 - 15 or lw_x > droi.x2 + 15))
                        right_out = (rw_c > 0.30 and (rw_y > droi.y2 + 10 or rw_y < droi.y1 - 20 or rw_x < droi.x1 - 15 or rw_x > droi.x2 + 15))
                        if left_out or right_out:
                            is_active = True
                            self._active_trigger_tracks[tid] = {
                                "trigger": TriggerType.HAND_OUTSIDE_DESK.value,
                                "expires_at": now + 3.0,
                            }

                    if is_active and self._continuous_roi_scan:
                        try:
                            # Stagger crop & detection every 4 frames per active track to maintain maximum FPS
                            should_infer = (self._frame_id - self._last_roi_scan_frame.get(tid, 0) >= 4)
                            if should_infer:
                                self._last_roi_scan_frame[tid] = self._frame_id
                                crop, v_roi = self.cropper.crop(raw_frame, roi_coords, resize_to_detector=False)
                                det_input = self.cropper._resize_for_detector(crop)

                                trigger_type = self._active_trigger_tracks.get(tid, {}).get("trigger", "HAND_OUTSIDE_DESK")
                                raw_dets = []
                                if detector is not None and hasattr(detector, 'predict'):
                                    try:
                                        raw_dets = detector.predict(det_input, confidence_threshold=0.35, trigger=trigger_type)
                                    except TypeError:
                                        raw_dets = detector.predict(det_input, confidence_threshold=0.35)
                                det_typed = []
                                for d in raw_dets:
                                    if hasattr(d, 'bbox') and len(d.bbox) == 4:
                                        fx1 = int(v_roi.x1 + d.bbox[0])
                                        fy1 = int(v_roi.y1 + d.bbox[1])
                                        fx2 = int(v_roi.x1 + d.bbox[2])
                                        fy2 = int(v_roi.y1 + d.bbox[3])
                                        c_name = getattr(d, 'object_class', 'unknown_object')
                                        c_conf = float(getattr(d, 'confidence', 0.0))
                                        det_typed.append(ObjectDetection(
                                            object_class=c_name,
                                            confidence=c_conf,
                                            bbox=[fx1, fy1, fx2, fy2],
                                            track_id=tid,
                                            seat_id=student.seat_id,
                                        ))

                                consensus = self.consensus_tracker.update(tid, det_typed, now, seat_id=student.seat_id)
                                self._cached_roi_dets[tid] = consensus
                            else:
                                consensus = self._cached_roi_dets.get(tid)

                            if consensus and consensus.consensus_confidence >= 0.40 and consensus.consensus_class != "unknown_object":
                                c_dict = {
                                    "object_class": consensus.consensus_class,
                                    "confidence": consensus.consensus_confidence,
                                    "bbox": consensus.consensus_bbox,
                                    "persistence_sec": consensus.persistence_sec,
                                    "detection_count": consensus.detection_count,
                                    "is_confirmed": consensus.is_confirmed,
                                }
                                if tid not in object_detections_by_track:
                                    object_detections_by_track[tid] = [c_dict]
                                    temporal_scores_by_track[tid] = consensus.consensus_confidence

                                # Emit / update canonical single source of truth event
                                if consensus.is_confirmed:
                                    existing_evt = next((e for e in reversed(self._canonical_events) if e.get("track_id") == tid and (now - e.get("timestamp", 0) < 6.0)), None)
                                    if existing_evt:
                                        existing_evt["object_confidence"] = consensus.consensus_confidence
                                        existing_evt["object_bbox"] = consensus.consensus_bbox
                                        existing_evt["persistence_sec"] = consensus.persistence_sec
                                        existing_evt["timestamp"] = now
                                    else:
                                        self._event_counter += 1
                                        evt_id = f"EVT-{self._event_counter}"
                                        canon_evt = EvidenceEvent(
                                            alert_id=evt_id,
                                            event_id=evt_id,
                                            track_ids=[tid],
                                            seat_ids=[student.seat_id] if student.seat_id else [],
                                            camera_id="CAM_01",
                                            start_time=now,
                                            end_time=now,
                                            track_id=tid,
                                            seat_id=student.seat_id,
                                            object_class=consensus.consensus_class,
                                            object_confidence=consensus.consensus_confidence,
                                            object_bbox=consensus.consensus_bbox,
                                            persistence_sec=consensus.persistence_sec,
                                            detection_count=consensus.detection_count,
                                            status=TriggerType.HAND_OUTSIDE_DESK.value,
                                            timestamp=now,
                                            timestamp_iso=time.strftime("%H:%M:%S", time.localtime(now)),
                                        )
                                        self._canonical_events.append(canon_evt.model_dump())
                                        if len(self._canonical_events) > 40:
                                            self._canonical_events.pop(0)

                        except Exception as ex:
                            logger.debug("Part 3 ROI error on track %s: %s", tid, ex)

            # 3. Part 2: Behaviour Risk Engine with Object Evidence Integration
            frame_input = pipeline_output_to_frame_input(
                p1_output,
                self._frame_id,
                object_detections_by_track=object_detections_by_track,
                temporal_scores_by_track=temporal_scores_by_track,
            )
            analysis = self.risk_engine.process_frame(frame_input)

            # Update risk_score on canonical events for synchronization
            risk_by_tid = {t.track_id: t.risk_score for t in analysis.tracks}
            for evt in self._canonical_events:
                if evt.get("track_id") in risk_by_tid:
                    evt["risk_score"] = risk_by_tid[evt["track_id"]]
                    if evt["risk_score"] >= 80:
                        evt["status"] = "CRITICAL_RISK"
                    elif evt["risk_score"] >= 60:
                        evt["status"] = "HIGH_RISK"
                    elif evt["risk_score"] >= 30:
                        evt["status"] = "WATCH_LIST"

            # 4. Trigger Bridge: Update active triggers for subsequent frames
            for track_risk in analysis.tracks:
                if should_trigger_roi(track_risk):
                    trig = get_trigger_for_events(track_risk.events) or TriggerType.MANUAL_REVIEW_TRIGGER
                    self._active_trigger_tracks[track_risk.track_id] = {
                        "trigger": trig.value,
                        "expires_at": now + 4.5,
                    }
                    with self._lock:
                        self._triggered_tracks[track_risk.track_id] = {
                            "track_id": track_risk.track_id,
                            "seat_id": track_risk.seat_id,
                            "trigger": trig.value,
                            "risk_score": track_risk.risk_score,
                            "events": track_risk.events,
                            "object_evidence": track_risk.object_evidence,
                            "temporal_score": track_risk.temporal_object_score,
                        }

            # Prune expired triggers
            self._active_trigger_tracks = {
                k: v for k, v in self._active_trigger_tracks.items() if v["expires_at"] > now
            }

            # 5. Visualization with ROI & Evidence Overlay
            try:
                risk_by_track = {t.track_id: t for t in analysis.tracks}
                annotated = self._visualizer.draw(
                    raw_frame,
                    p1_output,
                    risk_by_track=risk_by_track,
                    roboflow_detections=full_frame_phone_dets,
                    roboflow_metrics=roboflow_metrics,
                )
                if annotated is not None:
                    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 72, cv2.IMWRITE_JPEG_OPTIMIZE, 0])
                    jpeg_bytes = buf.tobytes()
                else:
                    jpeg_bytes = None
            except Exception:
                jpeg_bytes = None

            packet = self._build_packet(frame_input, analysis, scenario="LIVE_FEED")

            with self._lock:
                self._latest_jpeg = jpeg_bytes
                self._latest_packet = packet

    def _process_video_fallback(self, cap: cv2.VideoCapture) -> None:
        """Process video frames using video decoder, run YOLO-pose & Roboflow Phone Detection, and overlay analysis."""
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()

        if ret and frame is not None:
            self._frame_id += 1
            if frame.shape[1] != 1280 or frame.shape[0] != 720:
                frame = cv2.resize(frame, (1280, 720))

            pipeline = self._get_pipeline()
            p1_output = None
            if pipeline is not None:
                try:
                    p1_output = pipeline.process_frame(frame)
                except Exception as ex:
                    logger.debug("Perception pipeline error in video fallback: %s", ex)

            full_frame_phone_dets, roboflow_metrics = self._poll_async_phone_detection(
                frame, p1_output.students if p1_output else []
            )

            object_detections_by_track: Dict[str, List[dict]] = {}
            temporal_scores_by_track: Dict[str, float] = {}

            if p1_output and p1_output.students and full_frame_phone_dets:
                for p_det in full_frame_phone_dets:
                    p_box = p_det.get("bbox") or []
                    p_conf = float(p_det.get("confidence", 0.0))
                    cls_name = str(p_det.get("class_name", "PHONE")).upper()
                    is_permitted = p_det.get("is_permitted", False) or (cls_name == "CALCULATOR")

                    if is_permitted:
                        continue

                    if len(p_box) == 4 and p_conf >= 0.15:
                        pcx = (p_box[0] + p_box[2]) / 2.0
                        pcy = (p_box[1] + p_box[3]) / 2.0
                        best_student = None
                        min_dist = float("inf")
                        for student in p1_output.students:
                            if student.bbox:
                                s_bbox = student.bbox
                                if (s_bbox.x1 - 60 <= pcx <= s_bbox.x2 + 60) and (s_bbox.y1 - 60 <= pcy <= s_bbox.y2 + 80):
                                    dist = ((pcx - (s_bbox.x1 + s_bbox.x2)/2)**2 + (pcy - (s_bbox.y1 + s_bbox.y2)/2)**2) ** 0.5
                                    if dist < min_dist:
                                        min_dist = dist
                                        best_student = student
                        if best_student:
                            tid = best_student.track_id
                            object_detections_by_track[tid] = [{
                                "object_class": "PHONE",
                                "confidence": p_conf,
                                "bbox": p_box,
                                "persistence_sec": 1.0,
                                "detection_count": p_det.get("history_count", 1),
                                "is_confirmed": True,
                            }]
                            temporal_scores_by_track[tid] = p_conf

            if p1_output is not None:
                frame_input = pipeline_output_to_frame_input(
                    p1_output,
                    self._frame_id,
                    object_detections_by_track=object_detections_by_track,
                    temporal_scores_by_track=temporal_scores_by_track,
                )
                analysis = self.risk_engine.process_frame(frame_input)
            else:
                mock_frame = self.mock_generator.generate_frame()
                analysis = self.risk_engine.process_frame(mock_frame)

            try:
                risk_by_track = {t.track_id: t for t in analysis.tracks}
                annotated = self._visualizer.draw(
                    frame,
                    output=p1_output,
                    risk_by_track=risk_by_track,
                    roboflow_detections=full_frame_phone_dets,
                    roboflow_metrics=roboflow_metrics,
                )
                if annotated is None:
                    annotated = self._overlay_annotations(frame, mock_frame if p1_output is None else None, analysis)
            except Exception:
                annotated = self._overlay_annotations(frame, mock_frame if p1_output is None else None, analysis)

            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 72, cv2.IMWRITE_JPEG_OPTIMIZE, 0])
            packet = self._build_packet(frame_input if p1_output is not None else mock_frame, analysis, scenario="VIDEO_FEED")

            with self._lock:
                self._latest_jpeg = buf.tobytes()
                self._latest_packet = packet

    def _poll_async_phone_detection(self, frame: np.ndarray, students: List[Any]) -> Tuple[List[dict], dict]:
        """Poll completed background phone detection task and submit new tasks with strict rate-limiting for high FPS."""
        now = time.time()
        if self._phone_future is not None and self._phone_future.done():
            try:
                dets, metrics = self._phone_future.result()
                self._cached_phone_dets = dets
                self._cached_roboflow_metrics = metrics
            except Exception as ex:
                logger.error("Async phone detection execution error: %s", ex)
            self._phone_future = None
            self._last_async_scan_time = now

        # Only submit new background job if at least 0.35s has elapsed since last run to prevent CPU GIL starvation
        if self._phone_future is None and (now - self._last_async_scan_time >= 0.35):
            frame_copy = frame.copy()
            student_bboxes = []
            if students:
                for s in students:
                    if getattr(s, "bbox", None):
                        student_bboxes.append({
                            "x1": float(s.bbox.x1),
                            "y1": float(s.bbox.y1),
                            "x2": float(s.bbox.x2),
                            "y2": float(s.bbox.y2),
                        })
            self._phone_future = self._phone_executor.submit(self._run_phone_detection_task, frame_copy, student_bboxes)

        return self._cached_phone_dets, self._cached_roboflow_metrics

    def _run_phone_detection_task(self, frame: np.ndarray, student_bboxes: List[Dict[str, float]]) -> Tuple[List[dict], dict]:
        """Background thread execution of Roboflow phone detection - optimized single pass."""
        detector = self._get_object_detector()
        if detector is None or not hasattr(detector, "detect"):
            return [], {}

        dets: List[dict] = []
        metrics: dict = {}
        try:
            # Full-frame detection
            dets = detector.detect(frame)
            metrics = getattr(detector, "debug_metrics", {})

            # If full-frame detection yields no phones and students exist, scan high-res crops for student regions
            if not dets and student_bboxes:
                h, w = frame.shape[:2]
                for sb in student_bboxes[:2]:  # Limit to 2 primary active students max
                    cx1 = max(0, int(sb["x1"] - 40))
                    cy1 = max(0, int(sb["y1"] - 20))
                    cx2 = min(w, int(sb["x2"] + 40))
                    cy2 = min(h, int(sb["y2"] + 60))
                    crop = frame[cy1:cy2, cx1:cx2]
                    if crop.size > 0 and (cx2 - cx1) > 40 and (cy2 - cy1) > 40:
                        c_dets = detector.detect(crop)
                        for cd in c_dets:
                            c_box = cd.get("bbox") or []
                            if len(c_box) == 4:
                                cd_copy = dict(cd)
                                cd_copy["bbox"] = [cx1 + c_box[0], cy1 + c_box[1], cx1 + c_box[2], cy1 + c_box[3]]
                                dets.append(cd_copy)
                        if dets:
                            break
        except Exception as ex:
            logger.error("Error in async phone detection task: %s", ex)

        return dets, metrics

    def _process_mock_frame(self) -> None:
        """Process a mock/synthetic frame through Part 2 and render classroom visualization."""
        self._frame_id += 1
        mock_frame = self.mock_generator.generate_frame()
        analysis = self.risk_engine.process_frame(mock_frame)

        # ROI Bridge for mock mode
        for track_risk in analysis.tracks:
            if should_trigger_roi(track_risk):
                trigger = get_trigger_for_events(track_risk.events)
                with self._lock:
                    self._triggered_tracks[track_risk.track_id] = {
                        "track_id": track_risk.track_id,
                        "seat_id": track_risk.seat_id,
                        "trigger": trigger.value if trigger else "MANUAL_REVIEW_TRIGGER",
                        "risk_score": track_risk.risk_score,
                        "events": track_risk.events,
                    }

        # Render synthetic examination hall frame
        canvas = self._render_synthetic_hall(mock_frame, analysis)
        _, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 80])

        packet = self._build_packet(mock_frame, analysis, scenario="SIMULATION")

        with self._lock:
            self._latest_jpeg = buf.tobytes()
            self._latest_packet = packet

    def _render_synthetic_hall(self, frame_input, analysis) -> np.ndarray:
        """Renders a sleek dark-mode synthetic examination hall visual stream."""
        W, H = 1280, 720
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        canvas[:] = (18, 12, 7)  # Deep dark navy background (#070c12 BGR)

        # Grid floor perspective lines
        for x in range(0, W + 1, 80):
            cv2.line(canvas, (x, 0), (x, H), (26, 18, 12), 1)
        for y in range(0, H + 1, 60):
            cv2.line(canvas, (0, y), (W, y), (26, 18, 12), 1)

        # Top Header Banner
        cv2.rectangle(canvas, (0, 0), (W, 36), (22, 15, 10), -1)
        cv2.line(canvas, (0, 36), (W, 36), (40, 30, 20), 1)
        cv2.putText(
            canvas,
            "EXAMINATION HALL A — REAL-TIME ANONYMOUS INTEGRITY MONITOR",
            (20, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        return self._overlay_annotations(canvas, frame_input, analysis)

    def _overlay_annotations(self, canvas: np.ndarray, frame_input, analysis) -> np.ndarray:
        """Draws skeletons, compact tags, group chain lines, and tight object evidence boxes (No human bboxes)."""
        W, H = canvas.shape[1], canvas.shape[0]
        risk_by_track = {t.track_id: t for t in analysis.tracks}

        # 1. Group Interaction Chains
        for grp in analysis.groups:
            if grp.participants and len(grp.participants) >= 2:
                pts = []
                for pid in grp.participants:
                    for tr in frame_input.tracks:
                        if tr.track_id == pid and tr.keypoints:
                            kx = int(tr.keypoints[0].x * W if tr.keypoints[0].x <= 1.0 else tr.keypoints[0].x)
                            ky = int(tr.keypoints[0].y * H if tr.keypoints[0].y <= 1.0 else tr.keypoints[0].y)
                            pts.append((kx, ky))
                            break
                for k in range(len(pts) - 1):
                    cv2.line(canvas, pts[k], pts[k + 1], (0, 165, 255), 2, cv2.LINE_AA)

        # 2. Skeletons & Compact Student Status Indicators (Clean UI — No human boxes)
        COCO_SKELETON = [
            (0, 1), (0, 2), (1, 3), (2, 4),
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
            (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16),
        ]

        for tr in frame_input.tracks:
            ri = risk_by_track.get(tr.track_id)
            risk = ri.risk_score if ri else 0

            # Color coding (BGR)
            if risk >= 80:
                color = (0, 0, 235)     # Critical: Crimson
                bone_col = (80, 80, 245)
            elif risk >= 60:
                color = (0, 165, 255)   # High: Amber
                bone_col = (50, 180, 245)
            elif risk >= 30:
                color = (255, 200, 0)   # Watch: Cyan
                bone_col = (200, 180, 70)
            else:
                color = (0, 230, 118)   # Low: Green
                bone_col = (140, 200, 40)

            # Scale keypoints
            kps = []
            for kp in tr.keypoints:
                kx = int(kp.x * W if kp.x <= 1.0 else kp.x)
                ky = int(kp.y * H if kp.y <= 1.0 else kp.y)
                kps.append((kx, ky, kp.confidence))

            # Bones
            for p1, p2 in COCO_SKELETON:
                if p1 < len(kps) and p2 < len(kps):
                    x1, y1, c1 = kps[p1]
                    x2, y2, c2 = kps[p2]
                    if c1 > 0.15 and c2 > 0.15:
                        cv2.line(canvas, (x1, y1), (x2, y2), bone_col, 2, cv2.LINE_AA)

            # Joints
            for kx, ky, kc in kps:
                if kc > 0.15:
                    cv2.circle(canvas, (kx, ky), 3, color, -1, cv2.LINE_AA)

            # Head Gaze Vector
            if len(kps) > 0 and kps[0][2] > 0.15:
                nx, ny, _ = kps[0]
                gaze_yaw = ri.gaze_angle_deg if (ri and ri.gaze_angle_deg is not None) else 0.0
                rad = math.radians(gaze_yaw)
                gx = int(nx + math.sin(rad) * 32)
                gy = int(ny + math.cos(rad) * 18)
                cv2.arrowedLine(canvas, (nx, ny), (gx, gy), color, 2, tipLength=0.35)

            # Compact Student Label (No large rectangle box)
            hx, hy = (kps[0][0], kps[0][1] - 16) if (kps and kps[0][2] > 0.15) else (200, 200)
            if tr.bbox and (not kps or kps[0][2] <= 0.15):
                hx = int(tr.bbox.x_min * W if tr.bbox.x_min <= 1.0 else tr.bbox.x_min)
                hy = int(tr.bbox.y_min * H if tr.bbox.y_min <= 1.0 else tr.bbox.y_min) - 8

            status_band = "CRITICAL" if risk >= 80 else ("HIGH" if risk >= 60 else ("WATCH" if risk >= 30 else "LOW"))
            label = f"{tr.track_id} | Seat {tr.seat_id} | {status_band} {risk}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.44
            (tw, th), _ = cv2.getTextSize(label, font, scale, 1)

            cv2.rectangle(canvas, (hx - tw // 2 - 4, hy - th - 4), (hx + tw // 2 + 6, hy + 4), (18, 14, 10), -1)
            cv2.rectangle(canvas, (hx - tw // 2 - 4, hy - th - 4), (hx + tw // 2 + 6, hy + 4), color, 1, cv2.LINE_AA)
            cv2.putText(canvas, label, (hx - tw // 2, hy), font, scale, (245, 245, 245), 1, cv2.LINE_AA)

            # 3. Tight Object Bounding Boxes (ONLY for verified contraband evidence)
            if ri and ri.object_evidence:
                for obj in ri.object_evidence:
                    conf_val = float(obj.get("confidence", 0.0))
                    bbox = obj.get("bbox") or []
                    cls_name = obj.get("object_class", "paper_chit")
                    if conf_val >= 0.45 and len(bbox) == 4:
                        ox1, oy1, ox2, oy2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                        obj_col = (0, 165, 255) if cls_name == "paper_chit" else (0, 0, 235)
                        cv2.rectangle(canvas, (ox1, oy1), (ox2, oy2), obj_col, 2, cv2.LINE_AA)
                        obj_tag = f"{cls_name.replace('_', ' ').upper()} {int(conf_val * 100)}%"
                        cv2.rectangle(canvas, (ox1, max(0, oy1 - 16)), (ox1 + 120, oy1), (15, 15, 15), -1)
                        cv2.putText(canvas, obj_tag, (ox1 + 3, max(12, oy1 - 3)), font, 0.38, obj_col, 1, cv2.LINE_AA)

        # 4. Invigilator
        if frame_input.invigilators:
            for inv in frame_input.invigilators:
                ix = int(inv.x * W if inv.x <= 1.0 else inv.x)
                iy = int(inv.y * H if inv.y <= 1.0 else inv.y)
                cv2.circle(canvas, (ix, iy), 14, (240, 240, 80), 2, cv2.LINE_AA)
                cv2.putText(
                    canvas,
                    "PROCTOR",
                    (ix - 26, iy - 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38,
                    (240, 240, 80),
                    1,
                    cv2.LINE_AA,
                )

        return canvas

    def _build_packet(self, frame_input, analysis, scenario="LIVE", roboflow_debug: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Builds telemetry packet with canonical events for client consumption."""
        risk_by_track = {t.track_id: t for t in analysis.tracks}
        tracks_payload = []

        for tr in frame_input.tracks:
            ri = risk_by_track.get(tr.track_id)
            tracks_payload.append({
                "track_id": tr.track_id,
                "seat_id": tr.seat_id,
                "bbox": tr.bbox.model_dump() if tr.bbox else None,
                "desk_zone": tr.desk_zone.model_dump() if tr.desk_zone else None,
                "keypoints": [kp.model_dump() for kp in tr.keypoints],
                "additional_meta": tr.additional_meta or {},
                "risk_score": ri.risk_score if ri else 0,
                "confidence": ri.confidence if ri else 1.0,
                "events": ri.events if ri else [],
                "group_id": ri.group_id if ri else None,
                "duration_sec": ri.duration_sec if ri else 0.0,
                "baseline_deviation": ri.baseline_deviation if ri else 0.0,
                "reason_codes": [rc.value if hasattr(rc, 'value') else rc for rc in (ri.reason_codes if ri else [])],
                "status": ri.status.value if ri else "NORMAL",
                "gaze_angle_deg": ri.gaze_angle_deg if ri else 0.0,
                "torso_angle_deg": ri.torso_angle_deg if ri else 0.0,
                "hand_outside_zone": ri.hand_outside_zone if ri else False,
                "writing_active": ri.writing_active if ri else True,
                "is_suppressed": ri.is_suppressed_by_context if ri else False,
                "object_evidence": ri.object_evidence if ri else None,
                "temporal_object_score": ri.temporal_object_score if ri else None,
            })

        with self._lock:
            trig_snap = dict(self._triggered_tracks)
            events_snap = list(self._canonical_events[-20:])

        return {
            "type": "FRAME_TELEMETRY",
            "frame_id": frame_input.frame_id,
            "timestamp_ms": frame_input.timestamp_ms,
            "scenario": scenario,
            "source_mode": self._source_mode,
            "tracks": tracks_payload,
            "groups": [g.model_dump() for g in analysis.groups],
            "triggered_tracks": trig_snap,
            "canonical_events": events_snap,
            "roboflow_debug": roboflow_debug or {},
            "latency_ms": analysis.system_latency_ms,
            "fps": round(self._fps_actual, 1),
        }
