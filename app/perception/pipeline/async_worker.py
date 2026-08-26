"""
Real-time Asynchronous Pipeline Worker.

Decouples frame acquisition, YOLO11-pose inference, Part 2 risk analysis,
and visualization onto a dedicated high-performance background thread.
Provides zero-latency latest-frame buffers to WebSockets and MJPEG stream endpoints.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from app.perception.behaviour.adapter import pipeline_output_to_frame_input
from app.perception.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.perception.behaviour.mock_generator.stream_generator import MockPoseStreamGenerator
from app.perception.capture.video_source import SourceType, StreamStatus, VideoSource
from app.perception.pipeline.perception_pipeline import PerceptionPipeline
from app.perception.visualization.debug_visualizer import DebugVisualizer

logger = logging.getLogger(__name__)


class AsyncPipelineWorker:
    """
    High-throughput asynchronous pipeline engine running at 25+ FPS.
    """

    def __init__(self, media_dir: Optional[Path] = None):
        self.media_dir = media_dir or Path("media")
        self.risk_engine = BehaviourRiskEngine()
        self.mock_generator = MockPoseStreamGenerator()
        self.visualizer = DebugVisualizer(
            enabled=True,
            show_fps=True,
            show_skeleton=True,
            show_bbox=True,
            show_head_direction=True,
            show_visibility=True,
        )

        self._source_mode = "mock"  # "mock", "video", "live"
        self._video_path = "demo_feed_1.mp4"
        self._pipeline: Optional[PerceptionPipeline] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Thread-safe atomic latest outputs
        self._latest_jpeg: Optional[bytes] = None
        self._latest_packet: Optional[Dict[str, Any]] = None
        self._frame_id = 0
        self._fps_actual = 0.0

    def start(self):
        """Start the background worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="PipelineWorker")
        self._thread.start()
        logger.info("AsyncPipelineWorker thread started.")

    def stop(self):
        """Stop the background worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._release_pipeline()
        logger.info("AsyncPipelineWorker thread stopped.")

    def _release_pipeline(self):
        """Safely close active pipeline resources."""
        with self._lock:
            pipe = self._pipeline
            self._pipeline = None
        if pipe is not None:
            try:
                pipe.video_source.release()
            except Exception:
                pass

    def set_source(self, mode: str, video_path: Optional[str] = None):
        """Change input source seamlessly without blocking frame readers."""
        new_pipeline = None
        if mode in ("video", "live"):
            try:
                if mode == "live":
                    cam_source = 0
                else:
                    src = video_path or self._video_path or "demo_feed_1.mp4"
                    if not os.path.isabs(src):
                        resolved = (self.media_dir / src).resolve()
                        if resolved.exists():
                            src = str(resolved)
                        elif Path(src).exists():
                            src = str(Path(src).resolve())
                    cam_source = src

                new_pipeline = PerceptionPipeline(config={
                    "camera": {"source": cam_source},
                    "detection": {
                        "confidence": 0.18,
                        "model": "yolo11n-pose.pt",
                        "imgsz": 640,
                    },
                })
                if not new_pipeline.video_source.open():
                    logger.warning("Video source failed to open: %s", cam_source)
                    new_pipeline = None
                else:
                    logger.info("Pipeline initialized on source: %s", cam_source)
            except Exception as e:
                logger.error("Failed to init PerceptionPipeline: %s", e)
                new_pipeline = None

        with self._lock:
            old_pipeline = self._pipeline
            self._pipeline = new_pipeline
            self._source_mode = mode
            if video_path:
                self._video_path = video_path

        if old_pipeline is not None:
            try:
                old_pipeline.video_source.release()
            except Exception:
                pass
        logger.info("AsyncPipelineWorker switched source to: %s (%s)", mode, self._video_path)

    def get_latest_frame(self) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], float]:
        """O(1) non-blocking read of the latest frame JPEG and telemetry packet."""
        with self._lock:
            return self._latest_jpeg, self._latest_packet, self._fps_actual

    def process_client_webcam_frame(self, raw_bgr_image: np.ndarray) -> Tuple[bytes, Dict[str, Any]]:
        """Process a live frame captured from the client's browser webcam."""
        with self._lock:
            if self._pipeline is None:
                self._init_pipeline()
            pipeline = self._pipeline

        p1_output = pipeline.process_frame(raw_bgr_image, None) if pipeline else None
        self._frame_id += 1

        if p1_output is not None:
            frame_input = pipeline_output_to_frame_input(p1_output, self._frame_id)
            analysis = self.risk_engine.process_frame(frame_input)
            risk_by_track = {t.track_id: t for t in analysis.tracks}
            annotated = self.visualizer.draw(raw_bgr_image, p1_output, risk_by_track=risk_by_track)
        else:
            annotated = raw_bgr_image
            frame_input = self.mock_generator.generate_frame()
            analysis = self.risk_engine.process_frame(frame_input)

        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        packet = self._build_packet(frame_input, analysis, scenario="WEBCAM")

        return buf.tobytes(), packet

    def _worker_loop(self):
        """Core high-FPS processing loop running on dedicated worker thread."""
        target_fps = 25.0
        frame_interval = 1.0 / target_fps
        last_calc_time = time.perf_counter()
        fps_counter = 0

        while self._running:
            t0 = time.perf_counter()

            try:
                with self._lock:
                    mode = self._source_mode
                    pipeline = self._pipeline

                if mode in ("video", "live") and pipeline is not None and pipeline.video_source._opened:
                    # ── REAL VIDEO PIPELINE ────────────────────────────────
                    success, raw_frame, health = pipeline.video_source.read()

                    if not success or raw_frame is None:
                        # Video loop rewind
                        if pipeline.video_source._source_type == SourceType.VIDEO_FILE and pipeline.video_source._cap is not None:
                            pipeline.video_source._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            pipeline.video_source._stream_status = StreamStatus.CONNECTED
                            success, raw_frame, health = pipeline.video_source.read()

                    if success and raw_frame is not None:
                        self._frame_id += 1
                        p1_output = pipeline.process_frame(raw_frame, health)
                        frame_input = pipeline_output_to_frame_input(p1_output, self._frame_id)
                        analysis = self.risk_engine.process_frame(frame_input)

                        risk_by_track = {t.track_id: t for t in analysis.tracks}
                        annotated = self.visualizer.draw(raw_frame, p1_output, risk_by_track=risk_by_track)

                        if annotated is not None:
                            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            jpeg_bytes = buf.tobytes()
                        else:
                            jpeg_bytes = None

                        packet = self._build_packet(frame_input, analysis, scenario="LIVE_FEED")

                        with self._lock:
                            self._latest_jpeg = jpeg_bytes
                            self._latest_packet = packet
                else:
                    # ── SYNTHETIC DEMO SIMULATION ─────────────────────────
                    self._frame_id += 1
                    mock_frame = self.mock_generator.generate_frame()
                    analysis = self.risk_engine.process_frame(mock_frame)
                    packet = self._build_packet(mock_frame, analysis, scenario="SIMULATION")

                    with self._lock:
                        self._latest_packet = packet

                # FPS calculation
                fps_counter += 1
                now = time.perf_counter()
                if now - last_calc_time >= 1.0:
                    self._fps_actual = fps_counter / (now - last_calc_time)
                    fps_counter = 0
                    last_calc_time = now
            except Exception as e:
                logger.exception("Error in worker loop iteration: %s", e)

            # Sleep to maintain smooth real-time cadence
            elapsed = time.perf_counter() - t0
            sleep_needed = max(0.002, frame_interval - elapsed)
            time.sleep(sleep_needed)

    def _build_packet(self, frame_input, analysis, scenario="LIVE") -> Dict[str, Any]:
        """Builds telemetry packet for client consumption."""
        risk_by_track = {t.track_id: t for t in analysis.tracks}
        tracks_payload = []

        for tr in frame_input.tracks:
            ri = risk_by_track.get(tr.track_id)
            tracks_payload.append({
                "track_id": tr.track_id,
                "seat_id": tr.seat_id,
                "bbox": tr.bbox.dict() if tr.bbox else None,
                "desk_zone": tr.desk_zone.dict() if tr.desk_zone else None,
                "keypoints": [kp.dict() for kp in tr.keypoints],
                "additional_meta": tr.additional_meta or {},
                "risk_score": ri.risk_score if ri else 0,
                "confidence": ri.confidence if ri else 1.0,
                "events": ri.events if ri else [],
                "group_id": ri.group_id if ri else None,
                "duration_sec": ri.duration_sec if ri else 0.0,
                "baseline_deviation": ri.baseline_deviation if ri else 0.0,
                "reason_codes": ri.reason_codes if ri else [],
                "status": ri.status.value if ri else "NORMAL",
                "gaze_angle_deg": ri.gaze_angle_deg if ri else 0.0,
                "torso_angle_deg": ri.torso_angle_deg if ri else 0.0,
                "hand_outside_zone": ri.hand_outside_zone if ri else False,
                "writing_active": ri.writing_active if ri else True,
                "is_suppressed": ri.is_suppressed_by_context if ri else False,
            })

        return {
            "type": "FRAME_TELEMETRY",
            "frame_id": frame_input.frame_id,
            "timestamp_ms": frame_input.timestamp_ms,
            "scenario": scenario,
            "source_mode": self._source_mode,
            "tracks": tracks_payload,
            "groups": [g.dict() for g in analysis.groups],
            "latency_ms": analysis.system_latency_ms,
        }
