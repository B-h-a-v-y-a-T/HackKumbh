"""
Main perception pipeline orchestrator.

Fast path architecture:
    Frame → YOLO-pose (detect + track + 17 body keypoints in ONE call)
          → Analysis (head, visibility, geometry, desk ROI, seats)
          → StudentState output

Optional detail path (every N frames):
    → RTMPose on YOLO bboxes (133 keypoints for hands/face)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import yaml

from app.perception.analysis.body_geometry import BodyGeometryAnalyzer
from app.perception.analysis.head_orientation import HeadOrientationEstimator
from app.perception.analysis.visibility import VisibilityEstimator
from app.perception.capture.video_source import VideoSource
from app.perception.core.constants import TrackingState
from app.perception.core.data_models import (
    BoundingBox,
    FrameHealth,
    FrameMeta,
    KeypointSet,
    PipelineOutput,
    StudentState,
    TrackedObject,
)
from app.perception.detection.person_detector import PersonDetector
from app.perception.output.state_emitter import StateEmitter
from app.perception.pose.pose_estimator import PoseEstimator
from app.perception.pose.temporal_keypoints import TemporalKeypointManager
from app.perception.spatial.desk_roi import DeskROIEstimator
from app.perception.spatial.seat_manager import SeatManager
from app.perception.tracking.tracker import MultiPersonTracker
from app.perception.version import SCHEMA_VERSION
from app.perception.visualization.debug_visualizer import DebugVisualizer

logger = logging.getLogger(__name__)


class PerceptionPipeline:
    """
    End-to-end perception pipeline for exam monitoring.

    Fast path (every frame):
    1. YOLO-pose: detect + track + 17 body keypoints in ONE call
    2. Head orientation from body keypoints
    3. Visibility/occlusion scoring
    4. Body geometry normalization
    5. Desk ROI estimation
    6. Seat association
    7. StudentState assembly

    Detail path (every N frames, optional):
    - RTMPose for 133-keypoint wholebody (hands, face)
    - Merged with YOLO body keypoints

    Args:
        config: Configuration dict or path to YAML config file.
    """

    def __init__(self, config: Optional[Dict[str, Any] | str] = None):
        self.config = self._load_config(config)

        cam_cfg = self.config.get("camera", {})
        det_cfg = self.config.get("detection", {})
        pose_cfg = self.config.get("pose", {})
        track_cfg = self.config.get("tracking", {})
        seat_cfg = self.config.get("seats", {})
        vis_cfg = self.config.get("visibility", {})
        head_cfg = self.config.get("head_orientation", {})
        out_cfg = self.config.get("output", {})
        viz_cfg = self.config.get("visualization", {})

        self.camera_id = cam_cfg.get("camera_id", "CAM_01")

        # Core components
        self.video_source = VideoSource(
            source=cam_cfg.get("source", 0),
            width=cam_cfg.get("width", 1280),
            height=cam_cfg.get("height", 720),
            fps=cam_cfg.get("fps", 30),
            camera_id=self.camera_id,
        )

        # YOLO pose model — detection + tracking + 17 body keypoints in one call
        self.detector = PersonDetector(
            model_name=det_cfg.get("model", "yolo11s-pose.pt"),
            confidence=det_cfg.get("confidence", 0.5),
            device=det_cfg.get("device", "auto"),
            imgsz=det_cfg.get("imgsz", 640),
        )

        # Optional detailed pose (RTMPose for hands/face)
        self.detail_enabled = pose_cfg.get("detail_enabled", False)
        self.pose_estimator = PoseEstimator(
            mode=pose_cfg.get("mode", "lightweight"),
            backend=pose_cfg.get("backend", "onnxruntime"),
            device=pose_cfg.get("device", "cpu"),
            detail_interval=pose_cfg.get("detail_interval", 5),
        )

        # Temporal keypoint smoothing and persistence manager
        temporal_cfg = pose_cfg.get("temporal_smoothing", {})
        self.temporal_kps = TemporalKeypointManager(
            ema_alpha=temporal_cfg.get("ema_alpha", 0.75),
            min_detection_conf=temporal_cfg.get("min_detection_conf", 0.20),
            coast_decay=temporal_cfg.get("coast_decay", 0.95),
            max_coast_frames=temporal_cfg.get("max_coast_frames", 45),
            adaptive_alpha=temporal_cfg.get("adaptive_alpha", True),
        )

        tracker_cfg_file = track_cfg.get("tracker", "bytetrack.yaml")
        if tracker_cfg_file not in ("bytetrack.yaml", "botsort.yaml"):
            import os
            # If it's a custom path, make it absolute so Ultralytics finds it
            tracker_cfg_file = os.path.abspath(os.path.join("config", tracker_cfg_file))
        self.tracker_config = tracker_cfg_file

        self.tracker = MultiPersonTracker(
            coast_frames=track_cfg.get("coast_frames", 60),
            track_prefix=track_cfg.get("track_prefix", "T"),
        )

        self.seat_manager = SeatManager(
            stability_frames=seat_cfg.get("stability_frames", 60),
            merge_distance=seat_cfg.get("merge_distance", 50),
        )

        self.visibility_estimator = VisibilityEstimator(
            min_confidence=vis_cfg.get("min_confidence", 0.3),
            head_weight=vis_cfg.get("head_weight", 0.30),
            shoulder_weight=vis_cfg.get("shoulder_weight", 0.25),
            arm_weight=vis_cfg.get("arm_weight", 0.20),
            hand_weight=vis_cfg.get("hand_weight", 0.25),
        )

        self.head_estimator = HeadOrientationEstimator(
            min_landmark_confidence=head_cfg.get("min_landmark_confidence", 0.4),
        )
        from app.perception.analysis.head_orientation import SixDRepNetHeadPosePipeline
        self.head_pose_pipeline = SixDRepNetHeadPosePipeline(
            enabled=head_cfg.get("enabled", True),
            inference_interval=head_cfg.get("inference_interval", 2),
            ema_alpha=head_cfg.get("ema_alpha", 0.45),
        )

        self.body_geometry = BodyGeometryAnalyzer()
        self.desk_roi_estimator = DeskROIEstimator()

        self.emitter = StateEmitter(
            format=out_cfg.get("format", "json"),
            destination=out_cfg.get("destination", "stdout"),
        )

        self.visualizer = DebugVisualizer(
            enabled=viz_cfg.get("enabled", True),
            **{k: v for k, v in viz_cfg.items() if k != "enabled"},
        )

        # Pipeline state
        self._frame_number = 0
        self._fps_history: List[float] = []
        self._running = False

        # Timing breakdown
        self._timing: Dict[str, float] = {}

        # Load manual seat map if configured
        manual_seats = seat_cfg.get("manual_map", None)
        if manual_seats:
            self.seat_manager.load_seat_map(manual_seats)

    def _load_config(self, config: Optional[Dict | str]) -> Dict[str, Any]:
        if config is None:
            return {}
        if isinstance(config, dict):
            return config
        if isinstance(config, str):
            try:
                with open(config, "r") as f:
                    return yaml.safe_load(f) or {}
            except FileNotFoundError:
                logger.warning("Config file not found: %s. Using defaults.", config)
                return {}
        return {}

    def process_frame(self, frame: np.ndarray, frame_health: Optional[FrameHealth] = None) -> PipelineOutput:
        """
        Process a single frame through the fast-path pipeline.

        Single-model path: YOLO-pose → analysis → output.

        Args:
            frame: BGR image (H, W, 3) uint8.
            frame_health: Pre-computed frame health (optional).

        Returns:
            PipelineOutput with all student states.
        """
        t_start = time.perf_counter()
        self._frame_number += 1
        img_h, img_w = frame.shape[:2]

        # ==========================================
        # STEP 1: YOLO-pose — detect + track + pose
        # ==========================================
        t0 = time.perf_counter()
        detections, track_ids, yolo_keypoints = self.detector.detect_pose_track(
            frame, tracker_config=self.tracker_config
        )
        self._timing["yolo"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 2: Update tracker state
        # ==========================================
        t0 = time.perf_counter()
        tracked_objects = self.tracker.update_from_ultralytics(detections, track_ids)
        self._timing["tracking"] = (time.perf_counter() - t0) * 1000

        # Build fresh keypoints mapping for each tracked object
        fresh_keypoints_map: Dict[int, KeypointSet] = {}
        det_by_track_id: Dict[int, int] = {}
        for i, tid in enumerate(track_ids):
            if tid > 0:
                det_by_track_id[tid] = i

        for track in tracked_objects:
            if track.state == TrackingState.LOST:
                continue
            if track.track_id in det_by_track_id:
                idx = det_by_track_id[track.track_id]
                if idx < len(yolo_keypoints):
                    fresh_keypoints_map[track.track_id] = yolo_keypoints[idx]
            else:
                best_iou = -1.0
                best_kps = KeypointSet.empty()
                for i, det in enumerate(detections):
                    iou = track.bbox.iou(det.bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_kps = yolo_keypoints[i] if i < len(yolo_keypoints) else KeypointSet.empty()
                if best_iou >= 0.15:
                    fresh_keypoints_map[track.track_id] = best_kps

        # ==========================================
        # STEP 3: Optional detailed pose (every N frames)
        # ==========================================
        if self.detail_enabled and self.pose_estimator.should_run_this_frame():
            t0 = time.perf_counter()
            active_bboxes = [t.bbox for t in tracked_objects if t.state != TrackingState.LOST]
            active_tids = [t.track_id for t in tracked_objects if t.state != TrackingState.LOST]
            if active_bboxes:
                detail_kps = self.pose_estimator.estimate(frame, active_bboxes, active_tids)
                # Merge: YOLO body (fresh) + detail hands/face (from RTMPose)
                for j, tid in enumerate(active_tids):
                    if j < len(detail_kps) and tid in fresh_keypoints_map:
                        fresh_keypoints_map[tid] = self.pose_estimator.merge_yolo_with_detail(
                            fresh_keypoints_map[tid], detail_kps[j]
                        )
            self._timing["detail_pose"] = (time.perf_counter() - t0) * 1000
        elif self.detail_enabled:
            # Use cached detail for non-detail frames
            for tid in fresh_keypoints_map:
                cached = self.pose_estimator.get_cached(tid)
                if cached is not None:
                    fresh_keypoints_map[tid] = self.pose_estimator.merge_yolo_with_detail(
                        fresh_keypoints_map[tid], cached
                    )

        # ==========================================
        # STEP 3.5: Temporal Smoothing & Coasting Persistence
        # ==========================================
        t0 = time.perf_counter()
        keypoints_map = self.temporal_kps.update(tracked_objects, fresh_keypoints_map)
        self._timing["temporal_pose"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 4: Visibility estimation
        # ==========================================
        t0 = time.perf_counter()
        visibility_map = self.visibility_estimator.estimate_batch(
            tracked_objects, keypoints_map, img_w, img_h,
        )
        self._timing["visibility"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 5: Seat association
        # ==========================================
        t0 = time.perf_counter()
        vis_scores = {tid: vis.overall for tid, vis in visibility_map.items()}
        seat_map = self.seat_manager.update(tracked_objects, vis_scores)
        self._timing["seats"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 5.5: Batched Head Pose Estimation (SixDRepNet)
        # ==========================================
        t0 = time.perf_counter()
        head_orient_map = self.head_pose_pipeline.process_batch(
            frame, tracked_objects, keypoints_map, self._frame_number
        )
        self._timing["head_pose"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 6: Per-student analysis & assembly
        # ==========================================
        t0 = time.perf_counter()
        students: List[StudentState] = []
        for track in tracked_objects:
            kps = keypoints_map.get(track.track_id, KeypointSet.empty())
            vis = visibility_map.get(track.track_id)
            seat = seat_map.get(track.track_id)

            head_orient = head_orient_map.get(track.track_id)
            if head_orient is None:
                head_orient = self.head_estimator.estimate(kps)
            body_geom = self.body_geometry.analyze(kps)
            desk_roi = self.desk_roi_estimator.estimate(kps, track.bbox, img_w, img_h)

            student = StudentState(
                track_id=track.display_id,
                seat_id=seat.seat_id if seat else "UNASSIGNED",
                bbox=track.bbox,
                keypoints=kps,
                head_orientation=head_orient,
                visibility=vis,
                body_geometry=body_geom,
                desk_roi=desk_roi,
                seat_info=seat,
                tracking_state=track.state,
                frames_tracked=track.frames_tracked,
                frames_since_seen=track.frames_since_seen,
                timestamp=time.time(),
            )
            students.append(student)
        self._timing["analysis"] = (time.perf_counter() - t0) * 1000

        # ==========================================
        # STEP 7: Pipeline metrics
        # ==========================================
        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000
        pipeline_fps = 1000.0 / latency_ms if latency_ms > 0 else 0
        self._fps_history.append(pipeline_fps)
        if len(self._fps_history) > 60:
            self._fps_history = self._fps_history[-60:]

        avg_fps = float(np.mean(self._fps_history))

        output = PipelineOutput(
            schema_version=SCHEMA_VERSION,
            frame_meta=FrameMeta(
                timestamp=time.time(),
                camera_id=self.camera_id,
                frame_number=self._frame_number,
                pipeline_fps=avg_fps,
                pipeline_latency_ms=latency_ms,
            ),
            frame_health=frame_health,
            students=students,
        )

        return output

    def run(
        self,
        max_frames: Optional[int] = None,
        on_output: Optional[Callable[[PipelineOutput, np.ndarray], None]] = None,
    ):
        """
        Run the pipeline continuously.

        Args:
            max_frames: Stop after N frames (None = run forever).
            on_output: Callback receiving (PipelineOutput, frame) per frame.
        """
        logger.info("Starting perception pipeline...")

        if not self.video_source.open():
            logger.error("Failed to open video source.")
            return

        self._running = True

        try:
            while self._running:
                success, frame, health = self.video_source.read()

                if not success:
                    if frame is None:
                        logger.info("Video source ended.")
                        break
                    continue

                output = self.process_frame(frame, health)
                self.emitter.emit(output)

                # Visualization
                vis_frame = self.visualizer.draw(frame, output)
                if vis_frame is not None:
                    import cv2
                    cv2.imshow("CopyCop — Perception Pipeline", vis_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q") or key == 27:
                        logger.info("User requested stop.")
                        break
                    elif key == ord("v"):
                        self.visualizer.toggle_visibility()
                    elif key == ord("s"):
                        self.visualizer.toggle_skeleton()
                    elif key == ord("h"):
                        self.visualizer.toggle_head_direction()
                    elif key == ord("d"):
                        self.visualizer.toggle_desk_roi()
                    elif key == ord("t"):
                        self._log_timing()

                if on_output is not None:
                    on_output(output, frame)

                if max_frames is not None and self._frame_number >= max_frames:
                    logger.info("Reached max frames (%d). Stopping.", max_frames)
                    break

        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user.")
        finally:
            self.stop()

    def _log_timing(self):
        """Log per-component timing breakdown."""
        parts = " | ".join(f"{k}: {v:.1f}ms" for k, v in self._timing.items())
        logger.info("Timing: %s", parts)

    def stop(self):
        """Stop the pipeline and release resources."""
        self._running = False
        self.video_source.release()
        try:
            import cv2
            cv2.destroyAllWindows()
        except Exception:
            pass
        logger.info(
            "Pipeline stopped. Processed %d frames. Avg FPS: %.1f",
            self._frame_number,
            float(np.mean(self._fps_history)) if self._fps_history else 0,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def average_fps(self) -> float:
        return float(np.mean(self._fps_history)) if self._fps_history else 0.0
