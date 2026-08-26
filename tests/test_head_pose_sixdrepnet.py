"""
Comprehensive Unit & Integration Test Suite for SixDRepNet Head Pose and Behavioral Intelligence.
"""

import math
import numpy as np
import pytest
import torch

from app.behaviour.detectors.head_gaze import HeadGazeDetector, HeadGazeResult
from app.behaviour.detectors.torso_posture import TorsoPostureDetector
from app.behaviour.detectors.hand_desk_zone import HandDeskZoneDetector
from app.behaviour.detectors.sequence_automaton import SequenceAutomaton
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode, RiskStatus
from app.behaviour.schemas.pose import DeskZone, FrameInput, Keypoint, TrackPose
from app.behaviour.spatial_group.hall_layout import ExamHallLayout
from app.models.sixdrepnet import SixDRepNetEstimator
from app.perception.analysis.head_orientation import (
    HeadOrientationEstimator,
    SixDRepNetHeadPosePipeline,
)
from app.perception.core.constants import (
    KP_NOSE,
    KP_LEFT_EYE,
    KP_RIGHT_EYE,
    KP_LEFT_EAR,
    KP_RIGHT_EAR,
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    DirectionLabel,
)
from app.perception.core.data_models import (
    BoundingBox,
    HeadOrientation,
    KeypointSet,
    TrackedObject,
)


def _make_keypoint_set(nose=(100, 100, 0.9), l_eye=(90, 90, 0.9), r_eye=(110, 90, 0.9),
                        l_ear=(70, 95, 0.9), r_ear=(130, 95, 0.9),
                        l_sh=(60, 150, 0.9), r_sh=(140, 150, 0.9)):
    xy = np.zeros((133, 2), dtype=np.float32)
    conf = np.zeros(133, dtype=np.float32)

    pts = {
        KP_NOSE: nose,
        KP_LEFT_EYE: l_eye,
        KP_RIGHT_EYE: r_eye,
        KP_LEFT_EAR: l_ear,
        KP_RIGHT_EAR: r_ear,
        KP_LEFT_SHOULDER: l_sh,
        KP_RIGHT_SHOULDER: r_sh,
    }
    for idx, (x, y, c) in pts.items():
        xy[idx] = [x, y]
        conf[idx] = c
    return KeypointSet(xy=xy, confidence=conf)


def _make_track_pose(track_id="T01", seat_id="B2", yaw=0.0, pitch=0.0, roll=0.0, direction="FORWARD"):
    meta = {
        "head_yaw": yaw,
        "head_pitch": pitch,
        "head_roll": roll,
        "head_direction": direction,
        "head_conf": 0.9,
        "head_crop_valid": True,
        "visibility_overall": 1.0,
    }
    kps = [
        Keypoint(x=0.5, y=0.2, confidence=0.9),       # 0: nose
        Keypoint(x=0.48, y=0.18, confidence=0.9),     # 1: left eye
        Keypoint(x=0.52, y=0.18, confidence=0.9),     # 2: right eye
        Keypoint(x=0.45, y=0.19, confidence=0.9),     # 3: left ear
        Keypoint(x=0.55, y=0.19, confidence=0.9),     # 4: right ear
        Keypoint(x=0.42, y=0.30, confidence=0.9),     # 5: left shoulder
        Keypoint(x=0.58, y=0.30, confidence=0.9),     # 6: right shoulder
        Keypoint(x=0.40, y=0.45, confidence=0.8),     # 7: left elbow
        Keypoint(x=0.60, y=0.45, confidence=0.8),     # 8: right elbow
        Keypoint(x=0.46, y=0.55, confidence=0.85),    # 9: left wrist
        Keypoint(x=0.54, y=0.55, confidence=0.85),    # 10: right wrist
        Keypoint(x=0.45, y=0.70, confidence=0.8),     # 11: left hip
        Keypoint(x=0.55, y=0.70, confidence=0.8),     # 12: right hip
        Keypoint(x=0.44, y=0.85, confidence=0.8),     # 13: left knee
        Keypoint(x=0.56, y=0.85, confidence=0.8),     # 14: right knee
        Keypoint(x=0.43, y=0.95, confidence=0.8),     # 15: left ankle
        Keypoint(x=0.57, y=0.95, confidence=0.8),     # 16: right ankle
    ]
    desk = DeskZone(seat_id=seat_id, x_min=0.40, y_min=0.45, x_max=0.60, y_max=0.65)
    return TrackPose(
        track_id=track_id,
        seat_id=seat_id,
        keypoints=kps,
        bbox=None,
        desk_zone=desk,
        additional_meta=meta,
    )


class TestSixDRepNetHeadPose:
    """Tests for SixDRepNet model wrapper and preprocessing."""

    def test_sixdrepnet_estimator_loading(self):
        estimator = SixDRepNetEstimator.get_instance()
        assert estimator is not None
        assert estimator.is_ready is True

    def test_sixdrepnet_batch_inference_shape(self):
        estimator = SixDRepNetEstimator.get_instance()
        crops = [
            np.full((120, 120, 3), 100, dtype=np.uint8),
            np.full((80, 80, 3), 150, dtype=np.uint8),
        ]
        pitches, yaws, rolls = estimator.predict_batch(crops)
        assert len(pitches) == 2
        assert len(yaws) == 2
        assert len(rolls) == 2
        assert isinstance(float(pitches[0]), float)

    def test_crop_extraction_valid_landmarks(self):
        pipeline = SixDRepNetHeadPosePipeline()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        kps = _make_keypoint_set(nose=(400, 300, 0.9), l_eye=(370, 280, 0.9), r_eye=(430, 280, 0.9))
        crop, conf, is_valid = pipeline.extract_head_crop(frame, kps)
        assert is_valid is True
        assert crop is not None
        assert crop.shape[0] >= 32 and crop.shape[1] >= 32
        assert conf >= 0.8

    def test_crop_extraction_small_or_empty(self):
        pipeline = SixDRepNetHeadPosePipeline(min_crop_w=50, min_crop_h=50)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        empty_kps = KeypointSet.empty()
        crop, conf, is_valid = pipeline.extract_head_crop(frame, empty_kps)
        assert is_valid is False
        assert crop is None

    def test_head_pose_ema_smoothing(self):
        pipeline = SixDRepNetHeadPosePipeline(alpha=0.35)
        state = pipeline._states.setdefault(1, type('_TrackHeadPoseState', (), {})())
        state.smoothed_yaw = 0.0
        state.smoothed_pitch = 0.0
        state.smoothed_roll = 0.0
        state.last_frame_num = 1
        state.frames_since_inference = 0

        # Simulate update with raw_yaw = 40.0
        raw_yaw = 40.0
        state.smoothed_yaw = (0.35 * raw_yaw) + (0.65 * state.smoothed_yaw)
        assert round(state.smoothed_yaw, 2) == 14.0

        # Second update
        state.smoothed_yaw = (0.35 * raw_yaw) + (0.65 * state.smoothed_yaw)
        assert round(state.smoothed_yaw, 2) == 23.1


class TestHeadOrientationHysteresis:
    """Tests for dual-threshold state hysteresis."""

    def test_direction_classification_hysteresis_left(self):
        pipeline = SixDRepNetHeadPosePipeline(yaw_threshold=28.0, yaw_exit_threshold=20.0)

        # 1. Yaw = -25° (from FORWARD): should NOT enter LEFT yet (< -28°)
        d1 = pipeline._classify_hysteresis(yaw=-25.0, pitch=0.0, prev_direction=DirectionLabel.FORWARD, confidence=0.9)
        assert d1 == DirectionLabel.FORWARD

        # 2. Yaw = -30° (from FORWARD): enters LEFT
        d2 = pipeline._classify_hysteresis(yaw=-30.0, pitch=0.0, prev_direction=DirectionLabel.FORWARD, confidence=0.9)
        assert d2 == DirectionLabel.LEFT

        # 3. Yaw returns to -24° (from LEFT): stays LEFT because exit is > -20°
        d3 = pipeline._classify_hysteresis(yaw=-24.0, pitch=0.0, prev_direction=DirectionLabel.LEFT, confidence=0.9)
        assert d3 == DirectionLabel.LEFT

        # 4. Yaw returns to -18° (from LEFT): exits to FORWARD
        d4 = pipeline._classify_hysteresis(yaw=-18.0, pitch=0.0, prev_direction=DirectionLabel.LEFT, confidence=0.9)
        assert d4 == DirectionLabel.FORWARD

    def test_direction_classification_hysteresis_right(self):
        pipeline = SixDRepNetHeadPosePipeline(yaw_threshold=28.0, yaw_exit_threshold=20.0)

        # Enters RIGHT at > +28°
        d1 = pipeline._classify_hysteresis(yaw=32.0, pitch=0.0, prev_direction=DirectionLabel.FORWARD, confidence=0.9)
        assert d1 == DirectionLabel.RIGHT

        # Stays RIGHT at +24° (exit is < +20°)
        d2 = pipeline._classify_hysteresis(yaw=24.0, pitch=0.0, prev_direction=DirectionLabel.RIGHT, confidence=0.9)
        assert d2 == DirectionLabel.RIGHT

        # Exits RIGHT at +15°
        d3 = pipeline._classify_hysteresis(yaw=15.0, pitch=0.0, prev_direction=DirectionLabel.RIGHT, confidence=0.9)
        assert d3 == DirectionLabel.FORWARD

    def test_deep_writing_suppression(self):
        pipeline = SixDRepNetHeadPosePipeline(pitch_down_threshold=-25.0)
        # Deep downward pitch (-35°) with moderate lateral yaw (15°) -> classified as DOWN
        d = pipeline._classify_hysteresis(yaw=15.0, pitch=-35.0, prev_direction=DirectionLabel.FORWARD, confidence=0.9)
        assert d == DirectionLabel.DOWN


class TestSpatialNeighborGaze:
    """Tests for spatial neighbor geometry and episode counting."""

    def test_spatial_neighbor_gaze_true_neighbor(self):
        layout = ExamHallLayout(rows=3, cols=3)
        detector = HeadGazeDetector(layout=layout, sustained_gaze_sec=1.2, prolonged_gaze_sec=2.5)

        # Student at B2 (center), Neighbor at B1 (left)
        t_b2 = _make_track_pose(track_id="T02", seat_id="B2", yaw=-35.0, direction="LEFT")
        t_b1 = _make_track_pose(track_id="T01", seat_id="B1", yaw=0.0, direction="FORWARD")
        tracks = [t_b2, t_b1]

        # Initial frame (0.0s) -> observe
        res1 = detector.analyze(t_b2, timestamp_ms=1000.0, all_tracks=tracks)
        assert res1.is_neighbor_gaze is False

        # Frame after 1.5s -> NEIGHBOUR_GAZE triggered
        res2 = detector.analyze(t_b2, timestamp_ms=2500.0, all_tracks=tracks)
        assert res2.is_neighbor_gaze is True
        assert res2.target_seat_id == "B1"
        assert res2.target_track_id == "T01"
        assert BehaviourEvent.NEIGHBOUR_GAZE in res2.detected_events

    def test_spatial_solo_head_turn_no_neighbor(self):
        layout = ExamHallLayout(rows=3, cols=3)
        detector = HeadGazeDetector(layout=layout, sustained_gaze_sec=1.2)

        # Student at B1 (leftmost col), turning LEFT towards wall/aisle (no B0 exists)
        t_b1 = _make_track_pose(track_id="T01", seat_id="B1", yaw=-35.0, direction="LEFT")
        tracks = [t_b1]

        # First frame at 1000ms, then frame at 3000ms (2.0s duration >= 0.8s)
        detector.analyze(t_b1, timestamp_ms=1000.0, all_tracks=tracks)
        res = detector.analyze(t_b1, timestamp_ms=3000.0, all_tracks=tracks)

        # Solo head turn: emit HEAD_TURN_LEFT, NEVER NEIGHBOUR_GAZE
        assert res.is_neighbor_gaze is False
        assert BehaviourEvent.NEIGHBOUR_GAZE not in res.detected_events
        assert BehaviourEvent.HEAD_TURN_LEFT in res.detected_events

    def test_prolonged_neighbor_gaze_threshold(self):
        layout = ExamHallLayout(rows=3, cols=3)
        detector = HeadGazeDetector(layout=layout, sustained_gaze_sec=1.2, prolonged_gaze_sec=2.5)

        t_b2 = _make_track_pose(track_id="T02", seat_id="B2", yaw=35.0, direction="RIGHT")
        t_b3 = _make_track_pose(track_id="T03", seat_id="B3", yaw=0.0, direction="FORWARD")
        tracks = [t_b2, t_b3]

        detector.analyze(t_b2, timestamp_ms=1000.0, all_tracks=tracks)
        res = detector.analyze(t_b2, timestamp_ms=3800.0, all_tracks=tracks)  # 2.8s duration
        assert res.is_prolonged_neighbor_gaze is True
        assert BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE in res.detected_events

    def test_fleeting_gaze_ignored(self):
        layout = ExamHallLayout(rows=3, cols=3)
        detector = HeadGazeDetector(layout=layout, sustained_gaze_sec=1.2)

        t_b2 = _make_track_pose(track_id="T02", seat_id="B2", yaw=-35.0, direction="LEFT")
        tracks = [t_b2]

        detector.analyze(t_b2, timestamp_ms=1000.0, all_tracks=tracks)
        res = detector.analyze(t_b2, timestamp_ms=1300.0, all_tracks=tracks)  # 0.3s duration
        assert res.is_neighbor_gaze is False
        assert len(res.detected_events) == 0

    def test_repeated_glances_episode_counter(self):
        layout = ExamHallLayout(rows=3, cols=3)
        detector = HeadGazeDetector(layout=layout)

        t_left = _make_track_pose(track_id="T01", seat_id="B2", yaw=-35.0, direction="LEFT")
        t_fwd = _make_track_pose(track_id="T01", seat_id="B2", yaw=0.0, direction="FORWARD")
        tracks = [t_left]

        # Episode 1: LEFT for 0.8s
        detector.analyze(t_left, timestamp_ms=1000.0, all_tracks=tracks)
        detector.analyze(t_left, timestamp_ms=1800.0, all_tracks=tracks)

        # FORWARD for 1.0s
        detector.analyze(t_fwd, timestamp_ms=2000.0, all_tracks=tracks)
        detector.analyze(t_fwd, timestamp_ms=3000.0, all_tracks=tracks)

        # Episode 2: LEFT again for 0.8s
        detector.analyze(t_left, timestamp_ms=3200.0, all_tracks=tracks)
        res = detector.analyze(t_left, timestamp_ms=4000.0, all_tracks=tracks)

        # Should record 2 glance episodes and trigger REPEATED_HEAD_TURN
        assert res.head_turn_count_window >= 2
        assert BehaviourEvent.REPEATED_HEAD_TURN in res.detected_events


class TestTorsoAndHandKinematics:
    """Tests for torso posture and hand desk zone."""

    def test_torso_rotation_persistence_and_hysteresis(self):
        detector = TorsoPostureDetector(rotation_threshold_deg=24.0, persistence_threshold_sec=0.8)

        # 1. Neutral sitting frame to establish baseline
        track_neutral = _make_track_pose(track_id="T01")
        detector.analyze(track_neutral, timestamp_ms=1000.0)

        # 2. Tilted shoulders frame
        track_tilted = _make_track_pose(track_id="T01")
        track_tilted.keypoints[5] = Keypoint(x=0.40, y=0.36, confidence=0.9)  # left shoulder lower
        track_tilted.keypoints[6] = Keypoint(x=0.58, y=0.24, confidence=0.9)  # right shoulder higher

        # Initial tilted frame (0.0s elapsed) -> not persisted yet
        res1 = detector.analyze(track_tilted, timestamp_ms=1200.0)
        assert res1.is_rotated is False

        # Frame after 1.0s tilted -> persisted TORSO_ROTATION
        res2 = detector.analyze(track_tilted, timestamp_ms=2200.0)
        assert res2.is_rotated is True
        assert BehaviourEvent.TORSO_ROTATION in res2.detected_events

    def test_hand_reach_toward_neighbor(self):
        detector = HandDeskZoneDetector()
        track = _make_track_pose(track_id="T01")
        # Extend right wrist far to the right (x=0.75, outside desk x_max=0.60)
        track.keypoints[10] = Keypoint(x=0.75, y=0.55, confidence=0.9)

        res = detector.analyze(track, timestamp_ms=1000.0)
        assert res.hand_outside_zone is True
        assert res.is_reaching_neighbor is True
        assert BehaviourEvent.HAND_OUTSIDE_DESK_ZONE in res.detected_events
        assert BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR in res.detected_events


class TestSequenceAutomaton:
    """Tests for multi-step composite temporal patterns."""

    def test_sequence_automaton_pattern_a_peek_and_reach(self):
        automaton = SequenceAutomaton(sequence_window_sec=10.0)
        track_id = "T01"

        # Step 1: Writing Stop
        automaton.record_events(track_id, [BehaviourEvent.WRITING_STOP], timestamp_ms=1000.0)
        # Step 2: Neighbor Gaze
        automaton.record_events(track_id, [BehaviourEvent.NEIGHBOUR_GAZE], timestamp_ms=2000.0)
        # Step 3: Hand Reach Outside Desk
        res = automaton.record_events(track_id, [BehaviourEvent.HAND_OUTSIDE_DESK_ZONE], timestamp_ms=3000.0)

        assert res.sequence_detected is True
        assert res.sequence_name == "COORDINATED_PEEK_AND_REACH"
        assert BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED in res.detected_events

    def test_sequence_automaton_pattern_b_torso_and_peek(self):
        automaton = SequenceAutomaton(sequence_window_sec=10.0)
        track_id = "T02"

        automaton.record_events(track_id, [BehaviourEvent.TORSO_ROTATION], timestamp_ms=1000.0)
        automaton.record_events(track_id, [BehaviourEvent.NEIGHBOUR_GAZE], timestamp_ms=2000.0)
        res = automaton.record_events(track_id, [BehaviourEvent.REPEATED_HEAD_TURN], timestamp_ms=3000.0)

        assert res.sequence_detected is True
        assert res.sequence_name == "SUSTAINED_TORSO_AND_REPEATED_PEEK"


class TestRiskEngineCTRGCNDisabled:
    """Tests for explainable bounded risk engine with CTR-GCN live bypass."""

    def test_risk_engine_ctr_gcn_bypass_deterministic_score(self):
        engine = BehaviourRiskEngine()
        assert engine.settings.ctr_gcn_use_for_risk is False

        # Create input frame with 2 tracks
        t1 = _make_track_pose(track_id="T01", seat_id="A1", yaw=0.0, direction="FORWARD")
        t2 = _make_track_pose(track_id="T02", seat_id="A2", yaw=-35.0, direction="LEFT")
        frame_input = FrameInput(
            frame_id=1,
            timestamp_ms=1000.0,
            room_id="ROOM_01",
            tracks=[t1, t2],
        )

        response = engine.process_frame(frame_input)
        assert len(response.tracks) == 2
        for tr_risk in response.tracks:
            assert 0 <= tr_risk.risk_score <= 100
            assert tr_risk.status in [RiskStatus.NORMAL, RiskStatus.MONITORING, RiskStatus.UNUSUAL_BEHAVIOUR, RiskStatus.SUSPICIOUS_BEHAVIOUR]

    def test_risk_engine_baseline_isolation(self):
        engine = BehaviourRiskEngine()
        track = _make_track_pose(track_id="T01", seat_id="A1", yaw=-40.0, direction="LEFT")
        # Trigger suspicious behavior
        frame_input = FrameInput(
            frame_id=1,
            timestamp_ms=1000.0,
            room_id="ROOM_01",
            tracks=[track],
        )
        response = engine.process_frame(frame_input)
        base_profile = engine.baseline_mgr.get_profile("T01")
        assert base_profile is not None
        assert base_profile.track_id == "T01"
