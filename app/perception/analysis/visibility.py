"""
Visibility and occlusion scoring.

Computes per-body-region and overall visibility scores from keypoint
confidences and inter-person occlusion analysis. Produces GOOD/PARTIAL/POOR
camera visibility levels for each seat.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from app.perception.core.constants import (
    HEAD_INDICES,
    LEFT_ARM_INDICES,
    LEFT_HAND_INDICES,
    RIGHT_ARM_INDICES,
    RIGHT_HAND_INDICES,
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    DEFAULT_KEYPOINT_CONF,
    VisibilityLevel,
)
from app.perception.core.data_models import (
    BoundingBox,
    KeypointSet,
    TrackedObject,
    VisibilityInfo,
)

logger = logging.getLogger(__name__)


class VisibilityEstimator:
    """
    Estimates visibility and occlusion for each tracked student.

    Computes:
    - Per-region visibility from keypoint confidence scores
    - Overall weighted visibility score
    - Inter-person occlusion detection
    - Frame edge proximity detection
    - Camera-level visibility levels (GOOD/PARTIAL/POOR)

    Args:
        min_confidence: Minimum keypoint confidence to consider a point visible.
        head_weight: Weight of head region in overall score.
        shoulder_weight: Weight of shoulders in overall score.
        arm_weight: Weight of arms in overall score.
        hand_weight: Weight of hands in overall score.
        occlusion_iou_threshold: IoU threshold to flag inter-person occlusion.
        edge_margin: Pixel margin from frame edge to flag edge proximity.
    """

    def __init__(
        self,
        min_confidence: float = DEFAULT_KEYPOINT_CONF,
        head_weight: float = 0.30,
        shoulder_weight: float = 0.25,
        arm_weight: float = 0.20,
        hand_weight: float = 0.25,
        occlusion_iou_threshold: float = 0.15,
        edge_margin: int = 20,
    ):
        self.min_confidence = min_confidence
        self.head_weight = head_weight
        self.shoulder_weight = shoulder_weight
        self.arm_weight = arm_weight
        self.hand_weight = hand_weight
        self.occlusion_iou_threshold = occlusion_iou_threshold
        self.edge_margin = edge_margin

    def estimate(
        self,
        keypoints: KeypointSet,
        person_bbox: BoundingBox,
        all_tracked: List[TrackedObject],
        current_track_id: int,
        img_w: int,
        img_h: int,
    ) -> VisibilityInfo:
        """
        Compute visibility info for a single student.

        Args:
            keypoints: The student's keypoints.
            person_bbox: The student's bounding box.
            all_tracked: All currently tracked persons (for occlusion check).
            current_track_id: This student's track ID.
            img_w: Frame width.
            img_h: Frame height.

        Returns:
            VisibilityInfo with per-region and overall scores.
        """
        # Per-region scores from keypoint confidence
        head_vis = self._region_visibility(keypoints, HEAD_INDICES)
        l_shoulder_vis = self._point_visibility(keypoints, KP_LEFT_SHOULDER)
        r_shoulder_vis = self._point_visibility(keypoints, KP_RIGHT_SHOULDER)
        l_arm_vis = self._region_visibility(keypoints, LEFT_ARM_INDICES)
        r_arm_vis = self._region_visibility(keypoints, RIGHT_ARM_INDICES)
        l_hand_vis = self._region_visibility(keypoints, LEFT_HAND_INDICES)
        r_hand_vis = self._region_visibility(keypoints, RIGHT_HAND_INDICES)

        # Combined shoulder score
        shoulder_vis = (l_shoulder_vis + r_shoulder_vis) / 2

        # Weighted overall score
        overall = (
            self.head_weight * head_vis
            + self.shoulder_weight * shoulder_vis
            + self.arm_weight * (l_arm_vis + r_arm_vis) / 2
            + self.hand_weight * (l_hand_vis + r_hand_vis) / 2
        )

        # Inter-person occlusion check
        is_occluded = self._check_person_occlusion(
            person_bbox, all_tracked, current_track_id
        )

        # Frame edge check
        is_at_edge = self._check_frame_edge(person_bbox, img_w, img_h)

        # Reduce overall score for occlusion / edge
        if is_occluded:
            overall *= 0.8
        if is_at_edge:
            overall *= 0.9

        # Camera visibility level
        if overall >= 0.7:
            cam_vis = VisibilityLevel.GOOD
        elif overall >= 0.4:
            cam_vis = VisibilityLevel.PARTIAL
        else:
            cam_vis = VisibilityLevel.POOR

        return VisibilityInfo(
            overall=float(np.clip(overall, 0, 1)),
            head=float(head_vis),
            left_shoulder=float(l_shoulder_vis),
            right_shoulder=float(r_shoulder_vis),
            left_arm=float(l_arm_vis),
            right_arm=float(r_arm_vis),
            left_hand=float(l_hand_vis),
            right_hand=float(r_hand_vis),
            is_occluded_by_person=is_occluded,
            is_at_frame_edge=is_at_edge,
            camera_visibility=cam_vis,
        )

    def _region_visibility(
        self, keypoints: KeypointSet, indices: List[int]
    ) -> float:
        """Average visibility for a group of keypoints."""
        if not indices:
            return 0.0
        confs = keypoints.confidence[indices]
        # Count fraction of keypoints above threshold
        visible_count = np.sum(confs >= self.min_confidence)
        fraction_visible = visible_count / len(indices)
        # Average confidence of visible points
        avg_conf = float(np.mean(confs[confs >= self.min_confidence])) if visible_count > 0 else 0.0
        # Combine fraction and confidence
        return float(0.5 * fraction_visible + 0.5 * avg_conf)

    def _point_visibility(self, keypoints: KeypointSet, idx: int) -> float:
        """Visibility score for a single keypoint."""
        conf = float(keypoints.confidence[idx])
        return conf if conf >= self.min_confidence else 0.0

    def _check_person_occlusion(
        self,
        bbox: BoundingBox,
        all_tracked: List[TrackedObject],
        current_track_id: int,
    ) -> bool:
        """Check if this person is significantly overlapped by another."""
        for track in all_tracked:
            if track.track_id == current_track_id:
                continue
            iou = bbox.iou(track.bbox)
            if iou >= self.occlusion_iou_threshold:
                return True
        return False

    def _check_frame_edge(
        self, bbox: BoundingBox, img_w: int, img_h: int
    ) -> bool:
        """Check if the bbox is at the frame edge."""
        return (
            bbox.x1 < self.edge_margin
            or bbox.y1 < self.edge_margin
            or bbox.x2 > img_w - self.edge_margin
            or bbox.y2 > img_h - self.edge_margin
        )

    def estimate_batch(
        self,
        tracked_objects: List[TrackedObject],
        keypoints_map: Dict[int, KeypointSet],
        img_w: int,
        img_h: int,
    ) -> Dict[int, VisibilityInfo]:
        """
        Estimate visibility for all tracked objects at once.

        Args:
            tracked_objects: All tracked persons.
            keypoints_map: track_id → KeypointSet mapping.
            img_w: Frame width.
            img_h: Frame height.

        Returns:
            Dict mapping track_id → VisibilityInfo.
        """
        result = {}
        for track in tracked_objects:
            kps = keypoints_map.get(track.track_id)
            if kps is None:
                result[track.track_id] = VisibilityInfo()
                continue
            result[track.track_id] = self.estimate(
                kps, track.bbox, tracked_objects, track.track_id, img_w, img_h
            )
        return result
