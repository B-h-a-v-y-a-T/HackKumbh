"""Unit tests for TemporalKeypointManager."""

import numpy as np
import pytest

from app.perception.core.constants import TOTAL_KEYPOINTS, TrackingState
from app.perception.core.data_models import BoundingBox, KeypointSet, TrackedObject
from app.perception.pose.temporal_keypoints import TemporalKeypointManager


def _create_kps(x_val: float, y_val: float, conf: float = 0.8) -> KeypointSet:
    xy = np.full((TOTAL_KEYPOINTS, 2), (x_val, y_val), dtype=np.float32)
    confidence = np.full((TOTAL_KEYPOINTS,), conf, dtype=np.float32)
    return KeypointSet(xy=xy, confidence=confidence)


def _create_track(tid: int, x1: float, y1: float, state: TrackingState = TrackingState.TRACKED) -> TrackedObject:
    bbox = BoundingBox(x1=x1, y1=y1, x2=x1 + 100.0, y2=y1 + 200.0, confidence=0.9)
    return TrackedObject(track_id=tid, bbox=bbox, state=state)


class TestTemporalKeypointManager:
    def test_initialization(self):
        mgr = TemporalKeypointManager(ema_alpha=0.5)
        track = _create_track(1, 100.0, 100.0)
        fresh_kps = _create_kps(150.0, 200.0, 0.9)

        result = mgr.update([track], {1: fresh_kps})
        assert 1 in result
        assert np.isclose(result[1].xy[0, 0], 150.0)
        assert np.isclose(result[1].xy[0, 1], 200.0)

    def test_ema_smoothing(self):
        mgr = TemporalKeypointManager(ema_alpha=0.5)
        track1 = _create_track(1, 100.0, 100.0)
        kps1 = _create_kps(100.0, 100.0, 0.9)
        mgr.update([track1], {1: kps1})

        # Frame 2: joint moves to (110, 110)
        track2 = _create_track(1, 100.0, 100.0)
        kps2 = _create_kps(110.0, 110.0, 0.9)
        result2 = mgr.update([track2], {1: kps2})

        # EMA with alpha=0.5 -> 0.5 * 110 + 0.5 * 100 = 105.0
        assert np.isclose(result2[1].xy[0, 0], 105.0)
        assert np.isclose(result2[1].xy[0, 1], 105.0)

    def test_coasting_translation_and_decay(self):
        mgr = TemporalKeypointManager(coast_decay=0.9, max_coast_frames=10)
        track1 = _create_track(1, 100.0, 100.0)
        kps1 = _create_kps(150.0, 200.0, 0.8)
        mgr.update([track1], {1: kps1})

        # Frame 2: Coasting, bbox shifted by +10 in x and +20 in y
        track2 = _create_track(1, 110.0, 120.0, state=TrackingState.COASTING)
        result2 = mgr.update([track2], {})  # Empty fresh keypoints

        assert 1 in result2
        # Keypoints should be translated by bbox delta
        assert np.isclose(result2[1].xy[0, 0], 160.0)
        assert np.isclose(result2[1].xy[0, 1], 220.0)
        # Confidence should decay
        assert np.isclose(result2[1].confidence[0], 0.8 * 0.9)

    def test_max_coast_exceeded(self):
        mgr = TemporalKeypointManager(max_coast_frames=2)
        track = _create_track(1, 100.0, 100.0)
        kps = _create_kps(150.0, 200.0, 0.8)
        mgr.update([track], {1: kps})

        # Coast frame 1
        mgr.update([_create_track(1, 100.0, 100.0, state=TrackingState.COASTING)], {})
        # Coast frame 2
        mgr.update([_create_track(1, 100.0, 100.0, state=TrackingState.COASTING)], {})
        # Coast frame 3 -> should expire
        res = mgr.update([_create_track(1, 100.0, 100.0, state=TrackingState.COASTING)], {})
        assert np.all(res[1].confidence == 0.0)

    def test_prune_lost_tracks(self):
        mgr = TemporalKeypointManager()
        track = _create_track(1, 100.0, 100.0)
        kps = _create_kps(150.0, 200.0, 0.8)
        mgr.update([track], {1: kps})

        # Track 1 is now LOST
        lost_track = _create_track(1, 100.0, 100.0, state=TrackingState.LOST)
        res = mgr.update([lost_track], {})
        assert 1 not in res
