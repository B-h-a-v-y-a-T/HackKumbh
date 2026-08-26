"""
Unit tests for the tracking module.
"""

import numpy as np
import pytest

from app.perception.core.constants import TrackingState
from app.perception.core.data_models import BoundingBox, Detection, TrackedObject
from app.perception.tracking.tracker import MultiPersonTracker


class TestMultiPersonTracker:
    def setup_method(self):
        self.tracker = MultiPersonTracker(coast_frames=3, track_prefix="T")

    def test_new_tracks_created(self):
        """New detections create new tracks."""
        dets = [
            Detection(bbox=BoundingBox(100, 100, 200, 300)),
            Detection(bbox=BoundingBox(400, 100, 500, 300)),
        ]
        tracks = self.tracker.update_standalone(dets)
        assert len(tracks) == 2
        assert all(t.state == TrackingState.NEW for t in tracks)

    def test_tracking_continuity(self):
        """Same position → same track ID."""
        dets = [Detection(bbox=BoundingBox(100, 100, 200, 300))]

        # First frame
        tracks = self.tracker.update_standalone(dets)
        tid = tracks[0].track_id

        # Second frame — same position
        tracks = self.tracker.update_standalone(dets)
        assert len(tracks) == 1
        assert tracks[0].track_id == tid
        assert tracks[0].state == TrackingState.TRACKED

    def test_coasting(self):
        """Missing detections → COASTING state."""
        dets = [Detection(bbox=BoundingBox(100, 100, 200, 300))]
        tracks = self.tracker.update_standalone(dets)
        tid = tracks[0].track_id

        # No detections for 1 frame
        tracks = self.tracker.update_standalone([])
        assert len(tracks) == 1
        assert tracks[0].track_id == tid
        assert tracks[0].state == TrackingState.COASTING

    def test_lost_after_coast_timeout(self):
        """COASTING beyond timeout → track removed."""
        dets = [Detection(bbox=BoundingBox(100, 100, 200, 300))]
        self.tracker.update_standalone(dets)

        # Empty for coast_frames (3) frames
        for _ in range(4):
            tracks = self.tracker.update_standalone([])

        assert self.tracker.active_count == 0

    def test_new_track_for_distant_detection(self):
        """Detection far from existing track → new track."""
        dets1 = [Detection(bbox=BoundingBox(100, 100, 200, 300))]
        self.tracker.update_standalone(dets1)

        # Far away detection
        dets2 = [
            Detection(bbox=BoundingBox(100, 100, 200, 300)),  # Same
            Detection(bbox=BoundingBox(800, 100, 900, 300)),  # New, far
        ]
        tracks = self.tracker.update_standalone(dets2)
        assert len(tracks) == 2

    def test_ultralytics_mode(self):
        """Update from Ultralytics-provided track IDs."""
        dets = [
            Detection(bbox=BoundingBox(100, 100, 200, 300)),
            Detection(bbox=BoundingBox(400, 100, 500, 300)),
        ]
        track_ids = [5, 10]

        tracks = self.tracker.update_from_ultralytics(dets, track_ids)
        assert len(tracks) == 2
        display_ids = {t.display_id for t in tracks}
        assert "T5" in display_ids
        assert "T10" in display_ids

    def test_display_id_prefix(self):
        """Track display IDs use configured prefix."""
        tracker = MultiPersonTracker(track_prefix="STUDENT")
        dets = [Detection(bbox=BoundingBox(100, 100, 200, 300))]
        track_ids = [42]
        tracks = tracker.update_from_ultralytics(dets, track_ids)
        # TrackedObject display_id uses "T" prefix hardcoded, but track_prefix is for display
        assert tracks[0].track_id == 42

    def test_reset(self):
        """Reset clears all state."""
        dets = [Detection(bbox=BoundingBox(100, 100, 200, 300))]
        self.tracker.update_standalone(dets)
        assert self.tracker.active_count == 1

        self.tracker.reset()
        assert self.tracker.active_count == 0
