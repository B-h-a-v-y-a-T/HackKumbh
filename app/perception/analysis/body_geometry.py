"""
Body geometry normalization.

Computes shoulder-relative, camera-distance-independent measurements
so that downstream modules can compare poses across different camera
distances, angles, and student body sizes.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np

from app.perception.core.constants import (
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    KP_LEFT_ELBOW,
    KP_RIGHT_ELBOW,
    KP_LEFT_WRIST,
    KP_RIGHT_WRIST,
    KP_LEFT_HIP,
    KP_RIGHT_HIP,
    KP_NOSE,
    DEFAULT_KEYPOINT_CONF,
)
from app.perception.core.data_models import BodyGeometry, KeypointSet

logger = logging.getLogger(__name__)


class BodyGeometryAnalyzer:
    """
    Computes normalized body geometry measurements.

    All spatial measurements are normalized by shoulder width, making them
    independent of camera distance. This is critical for multi-camera setups
    where the same student may appear at different scales.

    Args:
        min_confidence: Minimum keypoint confidence for using a landmark.
    """

    def __init__(self, min_confidence: float = DEFAULT_KEYPOINT_CONF):
        self.min_conf = min_confidence

    def analyze(self, keypoints: KeypointSet) -> BodyGeometry:
        """
        Analyze body geometry from keypoints.

        Args:
            keypoints: 133-keypoint set.

        Returns:
            BodyGeometry with shoulder-normalized measurements.
        """
        ls = keypoints.get_point(KP_LEFT_SHOULDER)   # (x, y, conf)
        rs = keypoints.get_point(KP_RIGHT_SHOULDER)

        # Shoulder width (reference measurement)
        shoulder_width = 0.0
        shoulder_center = (0.0, 0.0)
        if ls[2] >= self.min_conf and rs[2] >= self.min_conf:
            shoulder_width = math.dist((ls[0], ls[1]), (rs[0], rs[1]))
            shoulder_center = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
        elif ls[2] >= self.min_conf:
            shoulder_center = (ls[0], ls[1])
        elif rs[2] >= self.min_conf:
            shoulder_center = (rs[0], rs[1])

        # Torso lean angle (angle of shoulder midpoint to hip midpoint from vertical)
        torso_lean = self._compute_torso_lean(keypoints, shoulder_center)

        # Arm extensions (normalized by shoulder width)
        l_arm_ext = self._compute_arm_extension(
            keypoints, KP_LEFT_SHOULDER, KP_LEFT_ELBOW, KP_LEFT_WRIST,
            shoulder_width,
        )
        r_arm_ext = self._compute_arm_extension(
            keypoints, KP_RIGHT_SHOULDER, KP_RIGHT_ELBOW, KP_RIGHT_WRIST,
            shoulder_width,
        )

        # Hand positions relative to shoulder center
        l_hand_pos = self._compute_relative_hand_position(
            keypoints, KP_LEFT_WRIST, shoulder_center, shoulder_width,
        )
        r_hand_pos = self._compute_relative_hand_position(
            keypoints, KP_RIGHT_WRIST, shoulder_center, shoulder_width,
        )

        return BodyGeometry(
            shoulder_width_px=round(shoulder_width, 1),
            torso_lean_angle=round(torso_lean, 1),
            left_arm_extension=round(l_arm_ext, 3),
            right_arm_extension=round(r_arm_ext, 3),
            left_hand_position=tuple(round(v, 3) for v in l_hand_pos),
            right_hand_position=tuple(round(v, 3) for v in r_hand_pos),
            shoulder_center=tuple(round(v, 1) for v in shoulder_center),
        )

    def _compute_torso_lean(
        self,
        keypoints: KeypointSet,
        shoulder_center: tuple[float, float],
    ) -> float:
        """Compute torso lean angle from vertical (degrees)."""
        lh = keypoints.get_point(KP_LEFT_HIP)
        rh = keypoints.get_point(KP_RIGHT_HIP)

        hip_center = None
        if lh[2] >= self.min_conf and rh[2] >= self.min_conf:
            hip_center = ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2)
        elif lh[2] >= self.min_conf:
            hip_center = (lh[0], lh[1])
        elif rh[2] >= self.min_conf:
            hip_center = (rh[0], rh[1])

        if hip_center is None or shoulder_center == (0.0, 0.0):
            return 0.0

        # Angle from vertical: atan2 of horizontal offset / vertical distance
        dx = shoulder_center[0] - hip_center[0]
        dy = hip_center[1] - shoulder_center[1]  # Positive upward

        if abs(dy) < 1:
            return 0.0

        angle = math.degrees(math.atan2(dx, dy))
        return float(np.clip(angle, -45, 45))

    def _compute_arm_extension(
        self,
        keypoints: KeypointSet,
        shoulder_idx: int,
        elbow_idx: int,
        wrist_idx: int,
        shoulder_width: float,
    ) -> float:
        """
        Compute arm extension as fraction of shoulder width.

        Full extension ≈ 2× shoulder width. Returns normalized value.
        """
        if shoulder_width < 1:
            return 0.0

        s = keypoints.get_point(shoulder_idx)
        e = keypoints.get_point(elbow_idx)
        w = keypoints.get_point(wrist_idx)

        if s[2] < self.min_conf:
            return 0.0

        # Use the farthest visible point from shoulder
        farthest_dist = 0.0
        if w[2] >= self.min_conf:
            farthest_dist = math.dist((s[0], s[1]), (w[0], w[1]))
        elif e[2] >= self.min_conf:
            farthest_dist = math.dist((s[0], s[1]), (e[0], e[1]))

        return farthest_dist / shoulder_width

    def _compute_relative_hand_position(
        self,
        keypoints: KeypointSet,
        wrist_idx: int,
        shoulder_center: tuple[float, float],
        shoulder_width: float,
    ) -> tuple[float, float]:
        """
        Compute hand position relative to shoulder center, normalized by shoulder width.

        Returns (dx, dy) where:
        - dx: positive = right of center
        - dy: positive = below center
        """
        if shoulder_width < 1 or shoulder_center == (0.0, 0.0):
            return (0.0, 0.0)

        w = keypoints.get_point(wrist_idx)
        if w[2] < self.min_conf:
            return (0.0, 0.0)

        dx = (w[0] - shoulder_center[0]) / shoulder_width
        dy = (w[1] - shoulder_center[1]) / shoulder_width

        return (float(dx), float(dy))
