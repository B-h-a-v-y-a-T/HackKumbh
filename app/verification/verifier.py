"""
High-Accuracy Verifier — Runs RT-DETRv4-L + ViTPose++-L on suspicious windows.

Cross-checks object evidence with pose evidence. Produces verification confidence.
Questions this stage helps answer:
  - Was there actually a phone/chit?
  - Was the apparent object just paper?
  - Was the hand movement real?
  - Was the behaviour caused by occlusion or lighting?
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from app.models.base import ModelRegistry
from app.schemas.common import ObjectDetection, PoseEvidence

logger = logging.getLogger(__name__)


class HighAccuracyVerifier:
    """Runs high-accuracy verification on suspicious temporal windows."""

    def __init__(self, confidence_threshold: float = 0.3) -> None:
        self._confidence_threshold = confidence_threshold

    def verify_frame(
        self,
        frame: np.ndarray,
        roi: Optional[List[int]] = None,
    ) -> dict:
        """
        Run high-accuracy verification on a single frame.

        Returns dict with object detections, pose evidence, and confidence.
        """
        registry = ModelRegistry.get_instance()

        # Object verification with RT-DETR
        ha_detector = registry.get_high_accuracy_detector("rtdetr")
        object_dets = ha_detector.predict(frame, self._confidence_threshold)

        # Pose verification with ViTPose++
        pose_verifier = registry.get_pose_verifier("vitpose")
        pose = pose_verifier.predict(frame, bbox=roi)

        # Cross-check: compute verification confidence
        verification_conf = self._cross_check(object_dets, pose)

        return {
            "object_detections": object_dets,
            "pose_evidence": pose,
            "verification_confidence": verification_conf,
            "verified_objects": [d.object_class for d in object_dets if d.confidence > 0.5],
            "notes": self._generate_notes(object_dets, pose),
        }

    def verify_window(
        self,
        frames: List[np.ndarray],
        roi: Optional[List[int]] = None,
    ) -> dict:
        """Verify a temporal window by analyzing multiple frames."""
        if not frames:
            return {
                "object_detections": [],
                "pose_evidence": PoseEvidence(),
                "verification_confidence": 0.0,
                "verified_objects": [],
                "notes": ["NO_FRAMES"],
            }

        all_dets = []
        all_poses = []
        all_confs = []

        # Sample frames (don't need every frame for verification)
        step = max(1, len(frames) // 5)
        sampled = frames[::step][:5]

        for frame in sampled:
            result = self.verify_frame(frame, roi)
            all_dets.extend(result["object_detections"])
            all_poses.append(result["pose_evidence"])
            all_confs.append(result["verification_confidence"])

        # Aggregate results
        best_dets = self._deduplicate_detections(all_dets)
        avg_pose = self._average_pose(all_poses)
        avg_conf = sum(all_confs) / len(all_confs) if all_confs else 0.0

        return {
            "object_detections": best_dets,
            "pose_evidence": avg_pose,
            "verification_confidence": round(avg_conf, 4),
            "verified_objects": list({d.object_class for d in best_dets if d.confidence > 0.5}),
            "notes": self._generate_notes(best_dets, avg_pose),
        }

    def _cross_check(
        self, detections: List[ObjectDetection], pose: PoseEvidence
    ) -> float:
        """Cross-check object detections with pose evidence."""
        if not detections:
            return 0.0

        max_obj_conf = max(d.confidence for d in detections)
        pose_conf = pose.pose_confidence

        # If pose shows low visibility, reduce confidence
        if pose.reason and "LOW_VISIBILITY" in pose.reason:
            return round(max_obj_conf * 0.5, 4)

        # Combine object and pose confidence
        combined = (max_obj_conf * 0.7 + pose_conf * 0.3)
        return round(min(1.0, combined), 4)

    def _deduplicate_detections(
        self, detections: List[ObjectDetection]
    ) -> List[ObjectDetection]:
        """Keep highest-confidence detection per class."""
        best = {}
        for det in detections:
            if det.object_class not in best or det.confidence > best[det.object_class].confidence:
                best[det.object_class] = det
        return list(best.values())

    def _average_pose(self, poses: List[PoseEvidence]) -> PoseEvidence:
        """Average pose evidence across frames."""
        if not poses:
            return PoseEvidence()
        valid = [p for p in poses if p.pose_confidence > 0.1]
        if not valid:
            return PoseEvidence(
                head_direction="UNKNOWN",
                reason="LOW_VISIBILITY",
            )
        avg_head_conf = sum(p.head_confidence for p in valid) / len(valid)
        avg_pose_conf = sum(p.pose_confidence for p in valid) / len(valid)
        avg_hand_vis = sum(p.hand_visibility for p in valid) / len(valid)
        avg_torso = sum(p.torso_rotation for p in valid) / len(valid)
        # Most common head direction
        dirs = [p.head_direction for p in valid if p.head_direction != "UNKNOWN"]
        head_dir = max(set(dirs), key=dirs.count) if dirs else "UNKNOWN"

        return PoseEvidence(
            head_confidence=round(avg_head_conf, 4),
            head_direction=head_dir,
            torso_rotation=round(avg_torso, 2),
            hand_visibility=round(avg_hand_vis, 4),
            pose_confidence=round(avg_pose_conf, 4),
        )

    def _generate_notes(
        self, detections: List[ObjectDetection], pose: PoseEvidence
    ) -> List[str]:
        """Generate human-readable verification notes."""
        notes = []
        if not detections:
            notes.append("NO_OBJECTS_VERIFIED")
        if pose.reason:
            notes.append(pose.reason)
        if pose.hand_visibility < 0.3:
            notes.append("LOW_HAND_VISIBILITY")
        for det in detections:
            if det.confidence > 0.8:
                notes.append(f"HIGH_CONFIDENCE_{det.object_class.upper()}")
        return notes
