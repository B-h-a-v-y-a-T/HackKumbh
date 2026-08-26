"""
Unified Frame Analyzer — Common AI Analysis Engine.

Shared execution pipeline for BOTH Live Camera Streams and Uploaded Video Files:
1. Skeleton / Pose Detection (YOLO11-pose + 17 COCO keypoints)
2. Multi-Person Tracking (ByteTrack persistent track IDs)
3. Behaviour Detection & Risk Engine (gaze, turns, torso, hands, leaky risk)
4. High-Resolution Student/Desk ROI Object Detection (Phone, Paper Chit, Earbuds)
5. Temporal Consensus & Confirmation Tracker
6. Canonical Event Generation & OpenCV Visualizer
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.behaviour.adapter import pipeline_output_to_frame_input
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.models.base import ModelRegistry
from app.perception.core.data_models import StudentState
from app.perception.pipeline.perception_pipeline import PerceptionPipeline, PipelineOutput
from app.perception.visualization.debug_visualizer import DebugVisualizer
from app.roi.consensus import TemporalConsensusTracker
from app.roi.cropper import ROICropper
from app.schemas.common import TriggerType

logger = logging.getLogger(__name__)


class CommonFrameAnalyzer:
    """
    Unified AI analysis pipeline that executes identical skeleton, behaviour,
    and object detection logic regardless of whether the source is live or a video file.
    """

    def __init__(
        self,
        pipeline: Optional[PerceptionPipeline] = None,
        risk_engine: Optional[BehaviourRiskEngine] = None,
        visualizer: Optional[DebugVisualizer] = None,
    ):
        self.pipeline = pipeline
        self.risk_engine = risk_engine or BehaviourRiskEngine()
        self.visualizer = visualizer or DebugVisualizer(
            enabled=True,
            show_fps=True,
            show_skeleton=True,
            show_bbox=False,  # No large human boxes
            show_head_direction=True,
            show_visibility=True,
        )
        self.cropper = ROICropper(detector_input_size=640)
        self.consensus_tracker = TemporalConsensusTracker(window_sec=2.5)
        self._event_counter = 1000

    def _get_pipeline(self) -> Optional[PerceptionPipeline]:
        """Lazy load or obtain perception pipeline."""
        if self.pipeline is None:
            try:
                self.pipeline = PerceptionPipeline()
            except Exception as ex:
                logger.warning("Could not initialize PerceptionPipeline: %s", ex)
        return self.pipeline

    def analyze_frame(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp_sec: float,
        source_id: str = "LIVE",
        continuous_object_scan: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute the complete unified 3-tier analysis on a single video frame.

        Args:
            frame: BGR video frame (H, W, 3).
            frame_id: Monotonic frame counter.
            timestamp_sec: Video or wall-clock timestamp in seconds.
            source_id: Identifier of stream or video filename.
            continuous_object_scan: Whether to scan high-res ROIs for contraband objects.

        Returns:
            Dictionary containing:
            - frame_id: int
            - timestamp: float
            - time_str: formatted "HH:MM:SS.mmm"
            - students: list of detected students with keypoints and bounding boxes
            - tracks: list of track risk outputs with behaviour events and risk scores
            - events: list of newly generated canonical events
            - object_detections: list of confirmed object detections
            - annotated_frame: np.ndarray with skeletons, compact pills, and object boxes
        """
        h, w = frame.shape[:2]
        pipeline = self._get_pipeline()
        p1_output: Optional[PipelineOutput] = None

        # 1. Part 1: Perception Pipeline (Pose, Tracking, Spatial ROI)
        if pipeline is not None:
            try:
                p1_output = pipeline.process_frame(frame)
            except Exception as ex:
                logger.debug("Perception pipeline execution exception: %s", ex)

        students: List[StudentState] = p1_output.students if p1_output else []

        # 2. Part 3: High-Resolution ROI Object Detection (Phone, Chit, Earbuds)
        object_detections_by_track: Dict[str, List[dict]] = {}
        temporal_scores_by_track: Dict[str, float] = {}
        all_object_detections: List[dict] = []

        if continuous_object_scan and students:
            all_object_detections, object_detections_by_track, temporal_scores_by_track = self._detect_objects_in_rois(
                frame, students, timestamp_sec
            )

        # 3. Part 2: Behaviour Risk Engine
        if p1_output is not None:
            frame_input = pipeline_output_to_frame_input(
                p1_output,
                frame_id,
                object_detections_by_track=object_detections_by_track,
                temporal_scores_by_track=temporal_scores_by_track,
            )
            analysis = self.risk_engine.process_frame(frame_input)
        else:
            # Fallback if no students in frame
            from app.behaviour.schemas.events import FrameAnalysisResponse
            analysis = FrameAnalysisResponse(room_id="ROOM_01", frame_id=frame_id, timestamp_ms=timestamp_sec * 1000.0, tracks=[], groups=[])

        # 4. Canonical Events Generation with Exact Timestamps
        canonical_events: List[Dict[str, Any]] = []
        minutes = int(timestamp_sec // 60)
        seconds = int(timestamp_sec % 60)
        millis = int((timestamp_sec - int(timestamp_sec)) * 1000)
        time_str = f"{minutes:02d}:{seconds:02d}.{millis:03d}"

        risk_by_track = {t.track_id: t for t in analysis.tracks}

        for track_risk in analysis.tracks:
            tid = track_risk.track_id
            seat_id = track_risk.seat_id or "UNASSIGNED"
            score = track_risk.risk_score

            # Priority categorization
            if score >= 80:
                priority = "CRITICAL"
                status = "CRITICAL_RISK"
            elif score >= 60:
                priority = "HIGH"
                status = "HIGH_RISK"
            elif score >= 30:
                priority = "WATCH"
                status = "WATCH_LIST"
            else:
                priority = "LOW"
                status = "NORMAL"

            # Behaviour and Object Events
            for evt in track_risk.events:
                self._event_counter += 1
                evt_type = evt.replace("_", " ").upper() if isinstance(evt, str) else str(evt)
                canonical_events.append({
                    "event_id": f"EVT_{source_id[:6]}_{self._event_counter}",
                    "source": "UPLOADED_VIDEO" if source_id != "LIVE" else "LIVE_CAMERA",
                    "video_id": source_id,
                    "camera_id": "CAMERA_01",
                    "track_id": tid,
                    "seat_id": seat_id,
                    "timestamp": round(timestamp_sec, 3),
                    "time_str": time_str,
                    "event_type": evt_type,
                    "confidence": round(track_risk.confidence, 2),
                    "priority": priority,
                    "status": status,
                    "risk_score": score,
                    "object_evidence": track_risk.object_evidence,
                    "reasons": track_risk.reason_codes,
                })

            # Check if confirmed object detections exist
            track_objs = object_detections_by_track.get(tid, [])
            for obj in track_objs:
                self._event_counter += 1
                cls_name = obj.get("object_class", "PHONE").replace("_", " ").upper()
                canonical_events.append({
                    "event_id": f"OBJ_{source_id[:6]}_{self._event_counter}",
                    "source": "UPLOADED_VIDEO" if source_id != "LIVE" else "LIVE_CAMERA",
                    "video_id": source_id,
                    "camera_id": "CAMERA_01",
                    "track_id": tid,
                    "seat_id": seat_id,
                    "timestamp": round(timestamp_sec, 3),
                    "time_str": time_str,
                    "event_type": f"{cls_name} DETECTED",
                    "confidence": round(float(obj.get("confidence", 0.85)), 2),
                    "priority": "CRITICAL" if cls_name == "PHONE" else "HIGH",
                    "status": "CRITICAL_RISK" if cls_name == "PHONE" else "HIGH_RISK",
                    "risk_score": max(score, 85 if cls_name == "PHONE" else 75),
                    "bbox": obj.get("bbox"),
                    "object_evidence": [obj],
                })

        # 5. Visualizer Rendering (Skeletons + Compact Risk Pills + Tight Object Boxes)
        try:
            annotated_frame = self.visualizer.draw(
                frame.copy(),
                p1_output,
                risk_by_track=risk_by_track,
                roboflow_detections=all_object_detections,
            )
        except Exception:
            annotated_frame = frame.copy()

        return {
            "frame_id": frame_id,
            "timestamp": timestamp_sec,
            "time_str": time_str,
            "students": students,
            "tracks": analysis.tracks,
            "events": canonical_events,
            "object_detections": all_object_detections,
            "annotated_frame": annotated_frame,
        }

    def _detect_objects_in_rois(
        self,
        frame: np.ndarray,
        students: List[StudentState],
        timestamp_sec: float,
    ) -> Tuple[List[dict], Dict[str, List[dict]], Dict[str, float]]:
        """
        Scan high-resolution crops from student desk/lap zones for contraband objects.
        Uses Roboflow Phone Detector or registered custom object detector.
        """
        all_dets: List[dict] = []
        by_track: Dict[str, List[dict]] = {}
        scores_by_track: Dict[str, float] = {}

        registry = ModelRegistry.get_instance()
        try:
            detector = registry.get_detector("live")
        except KeyError:
            try:
                from app.object_detection.roboflow_phone_detector import RoboflowPhoneDetector
                detector = RoboflowPhoneDetector()
                registry.register_detector("live", detector)
            except Exception:
                detector = None
        if detector is None:
            return all_dets, by_track, scores_by_track

        for s in students:
            if not s.bbox:
                continue

            tid = s.track_id
            bx1, by1, bx2, by2 = int(s.bbox.x1), int(s.bbox.y1), int(s.bbox.x2), int(s.bbox.y2)
            bw = max(bx2 - bx1, 10)
            bh = max(by2 - by1, 10)

            # High-resolution desk/lap crop (from shoulders to lower bbox margin)
            cx1 = max(0, bx1 - int(bw * 0.2))
            cy1 = max(0, by1 + int(bh * 0.25))
            cx2 = min(frame.shape[1], bx2 + int(bw * 0.2))
            cy2 = min(frame.shape[0], by2 + int(bh * 0.15))

            if (cx2 - cx1) < 20 or (cy2 - cy1) < 20:
                continue

            crop = frame[cy1:cy2, cx1:cx2]
            if crop.size == 0:
                continue

            try:
                # Run detector on full-res crop
                dets = detector.detect(crop)
                for d in dets:
                    conf = float(getattr(d, "confidence", 0.0) if hasattr(d, "confidence") else d.get("confidence", 0.0))
                    cls_name = getattr(d, "class_name", "phone") if hasattr(d, "class_name") else d.get("class_name", "phone")
                    bbox = getattr(d, "bbox", None) if hasattr(d, "bbox") else d.get("bbox")

                    if conf >= 0.40 and bbox:
                        # Translate crop coordinates back to full frame
                        if hasattr(bbox, "x1"):
                            fx1 = cx1 + bbox.x1
                            fy1 = cy1 + bbox.y1
                            fx2 = cx1 + bbox.x2
                            fy2 = cy1 + bbox.y2
                        else:
                            fx1 = cx1 + bbox[0]
                            fy1 = cy1 + bbox[1]
                            fx2 = cx1 + bbox[2]
                            fy2 = cy1 + bbox[3]

                        det_dict = {
                            "object_class": cls_name.upper(),
                            "confidence": conf,
                            "bbox": [int(fx1), int(fy1), int(fx2), int(fy2)],
                            "track_id": tid,
                            "seat_id": s.seat_id,
                            "timestamp": timestamp_sec,
                            "is_permitted": bool(getattr(d, "is_permitted", False) if hasattr(d, "is_permitted") else d.get("is_permitted", False) or cls_name.upper() == "CALCULATOR"),
                        }
                        all_dets.append(det_dict)

                        if not det_dict["is_permitted"]:
                            if tid not in by_track:
                                by_track[tid] = []
                            by_track[tid].append(det_dict)
                            scores_by_track[tid] = max(scores_by_track.get(tid, 0.0), conf)
            except Exception as ex:
                logger.debug("ROI object detector error for track %s: %s", tid, ex)

        return all_dets, by_track, scores_by_track
