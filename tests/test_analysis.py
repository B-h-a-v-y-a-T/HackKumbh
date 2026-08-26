"""
Unit tests for analysis modules: head orientation, visibility, body geometry.
"""

import math

import numpy as np
import pytest

from app.perception.core.constants import (
    KP_NOSE,
    KP_LEFT_EYE,
    KP_RIGHT_EYE,
    KP_LEFT_EAR,
    KP_RIGHT_EAR,
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    KP_LEFT_ELBOW,
    KP_RIGHT_ELBOW,
    KP_LEFT_WRIST,
    KP_RIGHT_WRIST,
    KP_LEFT_HIP,
    KP_RIGHT_HIP,
    DirectionLabel,
    TrackingState,
    VisibilityLevel,
    TOTAL_KEYPOINTS,
)
from app.perception.core.data_models import (
    BoundingBox,
    KeypointSet,
    TrackedObject,
)
from app.perception.analysis.head_orientation import HeadOrientationEstimator
from app.perception.analysis.visibility import VisibilityEstimator
from app.perception.analysis.body_geometry import BodyGeometryAnalyzer


def _make_keypoints(**kwargs) -> KeypointSet:
    """Helper to create a KeypointSet with specific points set."""
    kps = KeypointSet.empty()
    for idx, (x, y, c) in kwargs.items():
        kps.xy[idx] = [x, y]
        kps.confidence[idx] = c
    return kps


# ---------------------------------------------------------------------------
# HeadOrientationEstimator
# ---------------------------------------------------------------------------

class TestHeadOrientation:
    def setup_method(self):
        self.estimator = HeadOrientationEstimator(min_landmark_confidence=0.3)

    def test_forward_facing(self):
        """Symmetric eyes and nose centered → FORWARD."""
        kps = KeypointSet.empty()
        # Nose centered between eyes, only slightly below (realistic proportion)
        kps.xy[KP_NOSE] = [100, 103]
        kps.confidence[KP_NOSE] = 0.9
        kps.xy[KP_LEFT_EYE] = [90, 100]
        kps.confidence[KP_LEFT_EYE] = 0.9
        kps.xy[KP_RIGHT_EYE] = [110, 100]
        kps.confidence[KP_RIGHT_EYE] = 0.9
        kps.xy[KP_LEFT_EAR] = [75, 102]
        kps.confidence[KP_LEFT_EAR] = 0.9
        kps.xy[KP_RIGHT_EAR] = [125, 102]
        kps.confidence[KP_RIGHT_EAR] = 0.9

        result = self.estimator.estimate(kps)
        assert result.direction == DirectionLabel.FORWARD
        assert abs(result.yaw) < 20  # Close to zero
        assert result.confidence > 0.5

    def test_unknown_when_no_nose(self):
        """No visible nose → UNKNOWN."""
        kps = KeypointSet.empty()
        kps.confidence[KP_NOSE] = 0.1  # Below threshold
        kps.xy[KP_LEFT_EYE] = [90, 100]
        kps.confidence[KP_LEFT_EYE] = 0.9

        result = self.estimator.estimate(kps)
        assert result.direction == DirectionLabel.UNKNOWN

    def test_unknown_when_no_eyes(self):
        """Nose visible but no eyes → UNKNOWN."""
        kps = KeypointSet.empty()
        kps.xy[KP_NOSE] = [100, 110]
        kps.confidence[KP_NOSE] = 0.9
        kps.confidence[KP_LEFT_EYE] = 0.1
        kps.confidence[KP_RIGHT_EYE] = 0.1

        result = self.estimator.estimate(kps)
        assert result.direction == DirectionLabel.UNKNOWN

    def test_looking_right_missing_left_ear(self):
        """Left ear hidden → likely turned right."""
        kps = KeypointSet.empty()
        kps.xy[KP_NOSE] = [100, 110]
        kps.confidence[KP_NOSE] = 0.9
        kps.xy[KP_LEFT_EYE] = [90, 100]
        kps.confidence[KP_LEFT_EYE] = 0.9
        kps.xy[KP_RIGHT_EYE] = [110, 100]
        kps.confidence[KP_RIGHT_EYE] = 0.9
        # Only right ear visible
        kps.xy[KP_RIGHT_EAR] = [125, 105]
        kps.confidence[KP_RIGHT_EAR] = 0.9
        kps.confidence[KP_LEFT_EAR] = 0.1  # Hidden

        result = self.estimator.estimate(kps)
        # Should lean toward LEFT (negative yaw) because left ear is hidden
        assert result.yaw < 0

    def test_looking_down(self):
        """Nose significantly below eyes → DOWN."""
        kps = KeypointSet.empty()
        kps.xy[KP_NOSE] = [100, 140]  # Nose much lower
        kps.confidence[KP_NOSE] = 0.9
        kps.xy[KP_LEFT_EYE] = [90, 100]
        kps.confidence[KP_LEFT_EYE] = 0.9
        kps.xy[KP_RIGHT_EYE] = [110, 100]
        kps.confidence[KP_RIGHT_EYE] = 0.9

        result = self.estimator.estimate(kps)
        assert result.direction == DirectionLabel.DOWN
        assert result.pitch < 0


# ---------------------------------------------------------------------------
# VisibilityEstimator
# ---------------------------------------------------------------------------

class TestVisibility:
    def setup_method(self):
        self.estimator = VisibilityEstimator(min_confidence=0.3)

    def test_fully_visible(self):
        """All keypoints high confidence → high overall score."""
        kps = KeypointSet.empty()
        # Set all upper body keypoints to high confidence
        for idx in range(17):
            kps.xy[idx] = [100 + idx * 10, 200]
            kps.confidence[idx] = 0.9
        # Set hand keypoints
        for idx in range(91, 133):
            kps.xy[idx] = [100 + (idx - 91) * 5, 300]
            kps.confidence[idx] = 0.8

        bbox = BoundingBox(50, 100, 300, 500)
        tracked = [TrackedObject(track_id=1, bbox=bbox)]

        result = self.estimator.estimate(
            kps, bbox, tracked, 1, 1280, 720,
        )
        assert result.overall > 0.6
        assert result.head > 0.5
        assert result.camera_visibility == VisibilityLevel.GOOD

    def test_no_keypoints(self):
        """All keypoints zero confidence → poor visibility."""
        kps = KeypointSet.empty()
        bbox = BoundingBox(50, 100, 300, 500)
        tracked = [TrackedObject(track_id=1, bbox=bbox)]

        result = self.estimator.estimate(kps, bbox, tracked, 1, 1280, 720)
        assert result.overall < 0.1
        assert result.camera_visibility == VisibilityLevel.POOR

    def test_frame_edge_detection(self):
        """Bbox at frame edge → is_at_frame_edge = True."""
        kps = KeypointSet.empty()
        for idx in range(17):
            kps.confidence[idx] = 0.8
            kps.xy[idx] = [10 + idx, 100]
        bbox = BoundingBox(0, 50, 100, 300)  # At left edge
        tracked = [TrackedObject(track_id=1, bbox=bbox)]

        result = self.estimator.estimate(kps, bbox, tracked, 1, 1280, 720)
        assert result.is_at_frame_edge == True

    def test_inter_person_occlusion(self):
        """Two overlapping bboxes → occlusion detected."""
        kps = KeypointSet.empty()
        for idx in range(17):
            kps.confidence[idx] = 0.8
            kps.xy[idx] = [150, 200]
        bbox1 = BoundingBox(100, 100, 300, 400)
        bbox2 = BoundingBox(150, 100, 350, 400)  # Overlapping
        tracked = [
            TrackedObject(track_id=1, bbox=bbox1),
            TrackedObject(track_id=2, bbox=bbox2),
        ]

        result = self.estimator.estimate(kps, bbox1, tracked, 1, 1280, 720)
        assert result.is_occluded_by_person == True

    def test_batch_estimation(self):
        """Batch estimation returns results for all tracks."""
        kps1 = KeypointSet.empty()
        kps1.confidence[:17] = 0.8
        kps2 = KeypointSet.empty()
        kps2.confidence[:17] = 0.3

        tracked = [
            TrackedObject(track_id=1, bbox=BoundingBox(100, 100, 300, 400)),
            TrackedObject(track_id=2, bbox=BoundingBox(500, 100, 700, 400)),
        ]
        kps_map = {1: kps1, 2: kps2}

        results = self.estimator.estimate_batch(tracked, kps_map, 1280, 720)
        assert 1 in results
        assert 2 in results
        assert results[1].overall > results[2].overall


# ---------------------------------------------------------------------------
# BodyGeometryAnalyzer
# ---------------------------------------------------------------------------

class TestBodyGeometry:
    def setup_method(self):
        self.analyzer = BodyGeometryAnalyzer(min_confidence=0.3)

    def test_shoulder_width(self):
        """Correct shoulder width computation."""
        kps = KeypointSet.empty()
        kps.xy[KP_LEFT_SHOULDER] = [100, 200]
        kps.confidence[KP_LEFT_SHOULDER] = 0.9
        kps.xy[KP_RIGHT_SHOULDER] = [200, 200]
        kps.confidence[KP_RIGHT_SHOULDER] = 0.9

        result = self.analyzer.analyze(kps)
        assert result.shoulder_width_px == pytest.approx(100.0, abs=0.1)
        assert result.shoulder_center == (150.0, 200.0)

    def test_arm_extension(self):
        """Arm extension normalized by shoulder width."""
        kps = KeypointSet.empty()
        kps.xy[KP_LEFT_SHOULDER] = [100, 200]
        kps.confidence[KP_LEFT_SHOULDER] = 0.9
        kps.xy[KP_RIGHT_SHOULDER] = [200, 200]
        kps.confidence[KP_RIGHT_SHOULDER] = 0.9
        kps.xy[KP_LEFT_WRIST] = [50, 300]
        kps.confidence[KP_LEFT_WRIST] = 0.9

        result = self.analyzer.analyze(kps)
        assert result.left_arm_extension > 0
        # Should be roughly dist(100,200 → 50,300) / 100 ≈ 1.12
        assert result.left_arm_extension == pytest.approx(1.12, abs=0.1)

    def test_no_shoulders(self):
        """No visible shoulders → zero measurements."""
        kps = KeypointSet.empty()
        result = self.analyzer.analyze(kps)
        assert result.shoulder_width_px == 0.0
        assert result.left_arm_extension == 0.0
        assert result.right_arm_extension == 0.0

    def test_torso_lean(self):
        """Leaning torso → non-zero lean angle."""
        kps = KeypointSet.empty()
        # Shoulders at (100, 200) and (200, 200) → center (150, 200)
        kps.xy[KP_LEFT_SHOULDER] = [100, 200]
        kps.confidence[KP_LEFT_SHOULDER] = 0.9
        kps.xy[KP_RIGHT_SHOULDER] = [200, 200]
        kps.confidence[KP_RIGHT_SHOULDER] = 0.9
        # Hips shifted right → center (180, 400) → leaning right
        kps.xy[KP_LEFT_HIP] = [130, 400]
        kps.confidence[KP_LEFT_HIP] = 0.9
        kps.xy[KP_RIGHT_HIP] = [230, 400]
        kps.confidence[KP_RIGHT_HIP] = 0.9

        result = self.analyzer.analyze(kps)
        # Shoulder center (150, 200), hip center (180, 400)
        # Lean: atan2(150-180, 400-200) = atan2(-30, 200) ≈ -8.5 degrees
        assert result.torso_lean_angle != 0.0
