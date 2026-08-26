"""
Desk / interaction ROI estimation.

Estimates the desk or interaction region for each tracked student
based on their pose keypoints. This ROI can be used by downstream
modules for high-resolution object detection (e.g., phone detection).
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.perception.core.constants import (
    KP_LEFT_SHOULDER,
    KP_LEFT_WRIST,
    KP_RIGHT_SHOULDER,
    KP_RIGHT_WRIST,
    KP_LEFT_ELBOW,
    KP_RIGHT_ELBOW,
    DEFAULT_KEYPOINT_CONF,
)
from app.perception.core.data_models import BoundingBox, DeskROI, KeypointSet

logger = logging.getLogger(__name__)


class DeskROIEstimator:
    """
    Estimates the desk/interaction region from student pose.

    The desk ROI is the area below the shoulders and around the wrists
    where a student would interact with their desk, papers, or objects.

    Strategy:
    1. Use wrist positions as the primary desk area indicators
    2. Fall back to shoulder-relative estimation if wrists are not visible
    3. Extend the region slightly below and to the sides for full desk coverage

    Args:
        below_shoulder_ratio: How far below shoulders to extend (fraction of bbox height).
        side_padding_ratio: Horizontal padding as fraction of bbox width.
        min_confidence: Minimum keypoint confidence for using a landmark.
    """

    def __init__(
        self,
        below_shoulder_ratio: float = 1.0,
        side_padding_ratio: float = 0.45,
        min_confidence: float = DEFAULT_KEYPOINT_CONF,
    ):
        self.below_shoulder_ratio = below_shoulder_ratio
        self.side_padding_ratio = side_padding_ratio
        self.min_confidence = min_confidence

    def estimate(
        self,
        keypoints: KeypointSet,
        person_bbox: BoundingBox,
        img_w: int,
        img_h: int,
    ) -> DeskROI:
        """
        Estimate the desk/interaction ROI for a single student.

        Args:
            keypoints: Whole-body keypoints for this student.
            person_bbox: Bounding box of the detected person.
            img_w: Frame width.
            img_h: Frame height.

        Returns:
            DeskROI with estimated bounding box and confidence.
        """
        # Try wrist-based estimation first (most accurate)
        roi = self._from_wrists(keypoints, person_bbox, img_w, img_h)
        if roi is not None:
            return roi

        # Fall back to elbow-based
        roi = self._from_elbows(keypoints, person_bbox, img_w, img_h)
        if roi is not None:
            return roi

        # Fall back to shoulder-relative estimation
        return self._from_shoulders(keypoints, person_bbox, img_w, img_h)

    def _from_wrists(
        self,
        kps: KeypointSet,
        bbox: BoundingBox,
        img_w: int,
        img_h: int,
    ) -> Optional[DeskROI]:
        """Estimate desk ROI from wrist positions and body geometry."""
        lw_x, lw_y, lw_c = kps.get_point(KP_LEFT_WRIST)
        rw_x, rw_y, rw_c = kps.get_point(KP_RIGHT_WRIST)

        wrists = []
        if lw_c >= self.min_confidence:
            wrists.append((lw_x, lw_y))
        if rw_c >= self.min_confidence:
            wrists.append((rw_x, rw_y))

        if not wrists:
            return None

        wrist_xs = [w[0] for w in wrists]
        wrist_ys = [w[1] for w in wrists]

        # Shoulder anchor
        ls_x, ls_y, ls_c = kps.get_point(KP_LEFT_SHOULDER)
        rs_x, rs_y, rs_c = kps.get_point(KP_RIGHT_SHOULDER)

        shoulder_y = bbox.y1 + bbox.height * 0.28
        shoulder_span = bbox.width
        if ls_c >= self.min_confidence and rs_c >= self.min_confidence:
            shoulder_y = (ls_y + rs_y) / 2
            shoulder_span = max(abs(rs_x - ls_x), bbox.width * 0.6)

        pad_x = max(shoulder_span * self.side_padding_ratio, 60.0)
        below_ext = max(bbox.height * 0.35, 80.0)

        # Cover wrists, chest-to-lap zone, and surrounding desk area
        min_wrist_x = min(wrist_xs)
        max_wrist_x = max(wrist_xs)
        max_wrist_y = max(wrist_ys)

        roi_x1 = min(bbox.x1 - pad_x * 0.5, min_wrist_x - pad_x)
        roi_x2 = max(bbox.x2 + pad_x * 0.5, max_wrist_x + pad_x)
        roi_y1 = max(0.0, shoulder_y)
        roi_y2 = min(float(img_h), max(max_wrist_y + below_ext, bbox.y2 + 20.0))

        roi_bbox = BoundingBox(
            x1=max(0.0, roi_x1),
            y1=max(0.0, roi_y1),
            x2=min(float(img_w), max(roi_x2, roi_x1 + 160.0)),
            y2=min(float(img_h), max(roi_y2, roi_y1 + 160.0)),
        )

        confidence = float(np.mean([lw_c if lw_c >= self.min_confidence else 0.5,
                                    rw_c if rw_c >= self.min_confidence else 0.5]))
        return DeskROI(bbox=roi_bbox, confidence=max(0.4, confidence))

    def _from_elbows(
        self,
        kps: KeypointSet,
        bbox: BoundingBox,
        img_w: int,
        img_h: int,
    ) -> Optional[DeskROI]:
        """Estimate desk ROI from elbow positions."""
        le_x, le_y, le_c = kps.get_point(KP_LEFT_ELBOW)
        re_x, re_y, re_c = kps.get_point(KP_RIGHT_ELBOW)

        if le_c < self.min_confidence and re_c < self.min_confidence:
            return None

        elbows = []
        if le_c >= self.min_confidence:
            elbows.append((le_x, le_y))
        if re_c >= self.min_confidence:
            elbows.append((re_x, re_y))

        elbow_center_y = np.mean([e[1] for e in elbows])
        pad_x = max(bbox.width * self.side_padding_ratio, 60.0)
        below_ext = max(bbox.height * 0.45, 90.0)

        roi_bbox = BoundingBox(
            x1=max(0.0, bbox.x1 - pad_x),
            y1=max(0.0, elbow_center_y - 20.0),
            x2=min(float(img_w), max(bbox.x2 + pad_x, bbox.x1 + 160.0)),
            y2=min(float(img_h), max(elbow_center_y + below_ext, bbox.y2 + 20.0)),
        )

        confidence = np.mean([le_c if le_c >= self.min_confidence else 0.4,
                             re_c if re_c >= self.min_confidence else 0.4]) * 0.75
        return DeskROI(bbox=roi_bbox, confidence=float(confidence))

    def _from_shoulders(
        self,
        kps: KeypointSet,
        bbox: BoundingBox,
        img_w: int,
        img_h: int,
    ) -> DeskROI:
        """Fallback: estimate desk ROI from shoulder/bbox position."""
        ls_x, ls_y, ls_c = kps.get_point(KP_LEFT_SHOULDER)
        rs_x, rs_y, rs_c = kps.get_point(KP_RIGHT_SHOULDER)

        if ls_c >= self.min_confidence and rs_c >= self.min_confidence:
            shoulder_y = (ls_y + rs_y) / 2
        else:
            shoulder_y = bbox.y1 + bbox.height * 0.28

        pad_x = max(bbox.width * self.side_padding_ratio, 60.0)
        below_ext = bbox.height * self.below_shoulder_ratio

        roi_bbox = BoundingBox(
            x1=max(0.0, bbox.x1 - pad_x),
            y1=max(0.0, shoulder_y),
            x2=min(float(img_w), max(bbox.x2 + pad_x, bbox.x1 + 160.0)),
            y2=min(float(img_h), max(shoulder_y + below_ext, bbox.y2 + 20.0)),
        )

        return DeskROI(bbox=roi_bbox, confidence=0.3)
