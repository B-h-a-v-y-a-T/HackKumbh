"""
Unit tests for spatial modules: seat manager, desk ROI.
"""

import numpy as np
import pytest

from app.perception.core.constants import VisibilityLevel, TrackingState
from app.perception.core.data_models import BoundingBox, KeypointSet, TrackedObject
from app.perception.spatial.seat_manager import SeatManager
from app.perception.spatial.desk_roi import DeskROIEstimator
from app.perception.core.constants import (
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    KP_LEFT_WRIST,
    KP_RIGHT_WRIST,
)


class TestSeatManager:
    def test_manual_seat_map(self):
        """Load and use a manual seat map."""
        sm = SeatManager(stability_frames=5)
        sm.load_seat_map({"S1": (200, 300), "S2": (500, 300)})
        assert sm.confirmed_seat_count == 2

    def test_auto_discovery(self):
        """Seats auto-discovered from stable track positions."""
        sm = SeatManager(stability_frames=3, merge_distance=50)

        track = TrackedObject(
            track_id=1,
            bbox=BoundingBox(150, 250, 250, 350),
            state=TrackingState.TRACKED,
        )

        # Simulate stable position for N frames
        for _ in range(10):
            sm.update([track])

        assert sm.confirmed_seat_count >= 1

    def test_seat_assignment(self):
        """Track assigned to nearest seat."""
        sm = SeatManager(stability_frames=3, merge_distance=50)
        sm.load_seat_map({"S1": (200, 300), "S2": (500, 300)})

        track = TrackedObject(
            track_id=1,
            bbox=BoundingBox(180, 280, 220, 320),  # Close to S1
        )

        result = sm.update([track])
        assert 1 in result
        assert result[1].seat_id == "S1"

    def test_vacant_seats(self):
        """Seats without tracks become vacant."""
        sm = SeatManager(stability_frames=3)
        sm.load_seat_map({"S1": (200, 300), "S2": (500, 300)})

        # No tracks for many frames
        for _ in range(50):
            sm.update([])

        all_seats = sm.get_all_seats()
        for seat_info in all_seats.values():
            assert seat_info.is_vacant == True


class TestDeskROI:
    def setup_method(self):
        self.estimator = DeskROIEstimator(min_confidence=0.3)

    def test_from_wrists(self):
        """Desk ROI estimated from wrist positions."""
        kps = KeypointSet.empty()
        kps.xy[KP_LEFT_SHOULDER] = [150, 200]
        kps.confidence[KP_LEFT_SHOULDER] = 0.9
        kps.xy[KP_RIGHT_SHOULDER] = [250, 200]
        kps.confidence[KP_RIGHT_SHOULDER] = 0.9
        kps.xy[KP_LEFT_WRIST] = [120, 350]
        kps.confidence[KP_LEFT_WRIST] = 0.8
        kps.xy[KP_RIGHT_WRIST] = [280, 350]
        kps.confidence[KP_RIGHT_WRIST] = 0.8

        bbox = BoundingBox(100, 150, 300, 450)
        roi = self.estimator.estimate(kps, bbox, 1280, 720)

        assert roi.confidence > 0.5
        assert roi.bbox.y1 < 350  # Starts above wrists
        assert roi.bbox.y2 > 350  # Extends below wrists

    def test_fallback_to_shoulders(self):
        """No wrists or elbows → fallback to shoulder-based estimation."""
        kps = KeypointSet.empty()
        kps.xy[KP_LEFT_SHOULDER] = [150, 200]
        kps.confidence[KP_LEFT_SHOULDER] = 0.9
        kps.xy[KP_RIGHT_SHOULDER] = [250, 200]
        kps.confidence[KP_RIGHT_SHOULDER] = 0.9
        # No wrists or elbows

        bbox = BoundingBox(100, 150, 300, 450)
        roi = self.estimator.estimate(kps, bbox, 1280, 720)

        assert roi.confidence == pytest.approx(0.3)  # Low confidence for fallback
        assert roi.bbox.area > 0
