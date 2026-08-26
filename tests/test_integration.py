"""
Integration tests for CopyCop Unified System.

Verifies end-to-end integration across all 4 parts:
  Part 1: Live Perception (StudentState, Keypoints, BBox, Tracking)
  Part 2: Behaviour Intelligence (RiskEngine, Detectors, Baseline, Spatial Groups)
  Part 3: High-Res ROI Detection & Retrospective Verification
  Part 4: Unified Risk Engine, WebSocket/API Orchestration & Invigilator Review
"""

import pytest
import numpy as np
import time

from app.perception.core.data_models import StudentState, BoundingBox, KeypointSet
from app.behaviour.schemas.pose import FrameInput, TrackPose, Keypoint, DeskZone
from app.behaviour.schemas.events import BehaviourEvent, TrackRiskOutput
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.behaviour.roi_bridge import get_trigger_for_events, should_trigger_roi, build_roi_request_params
from app.risk.unified_engine import UnifiedRiskEngine, UnifiedRiskScore
from app.schemas.common import TriggerType, VerificationStatus
from app.pipeline.worker import AsyncPipelineWorker


class TestPerceptionToBehaviourIntegration:
    """Test data flow from Part 1 perception schemas into Part 2 behaviour engine."""

    def test_mock_stream_generation_and_risk_analysis(self):
        worker = AsyncPipelineWorker(mock_mode=True)
        # Generate synthetic frame
        mock_frame = worker.mock_generator.generate_frame()
        assert isinstance(mock_frame, FrameInput)
        assert len(mock_frame.tracks) > 0

        # Process through behaviour risk engine
        analysis = worker.risk_engine.process_frame(mock_frame)
        assert analysis.frame_id == mock_frame.frame_id
        assert len(analysis.tracks) == len(mock_frame.tracks)

        for track_risk in analysis.tracks:
            assert isinstance(track_risk, TrackRiskOutput)
            assert 0 <= track_risk.risk_score <= 100
            assert 0.0 <= track_risk.confidence <= 1.0
            assert track_risk.status in ["NORMAL", "MONITORING", "UNUSUAL_BEHAVIOUR", "SUSPICIOUS_BEHAVIOUR"]


class TestBehaviourToROITriggerBridge:
    """Test conversion of Part 2 behaviour events into Part 3 ROI attention triggers."""

    def test_hand_outside_desk_trigger_mapping(self):
        events = [BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value]
        trigger = get_trigger_for_events(events)
        assert trigger == TriggerType.HAND_OUTSIDE_DESK

    def test_repeated_head_turn_trigger_mapping(self):
        events = [BehaviourEvent.REPEATED_HEAD_TURN.value]
        trigger = get_trigger_for_events(events)
        assert trigger == TriggerType.REPEATED_HEAD_TURN

    def test_torso_rotation_trigger_mapping(self):
        events = [BehaviourEvent.TORSO_ROTATION.value]
        trigger = get_trigger_for_events(events)
        assert trigger == TriggerType.TORSO_ROTATION

    def test_should_trigger_roi_threshold(self):
        # Low risk track -> should not trigger
        low_risk = TrackRiskOutput(
            track_id="T01",
            seat_id="A1",
            risk_score=15,
            confidence=0.9,
            events=[],
        )
        assert not should_trigger_roi(low_risk, risk_threshold=40)

        # High risk track -> should trigger
        high_risk = TrackRiskOutput(
            track_id="T02",
            seat_id="A2",
            risk_score=65,
            confidence=0.9,
            events=[BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value],
        )
        assert should_trigger_roi(high_risk, risk_threshold=40)

        # Parameter builder
        params = build_roi_request_params(high_risk, camera_id="CAM_01")
        assert params is not None
        assert params["track_id"] == "T02"
        assert params["camera_id"] == "CAM_01"
        assert params["trigger"] == TriggerType.NEIGHBOUR_INTERACTION


class TestUnifiedRiskEngine:
    """Test unified risk score combining behaviour, object, and retrospective evidence."""

    def test_unified_risk_computation_normal(self):
        engine = UnifiedRiskEngine()
        score = engine.compute(
            track_id="T10",
            seat_id="B2",
            camera_id="CAM_01",
            behaviour_risk_score=10,
            behaviour_events=[],
            behaviour_confidence=0.9,
            object_detections=[],
        )
        assert isinstance(score, UnifiedRiskScore)
        assert score.status == "NORMAL"
        assert score.combined_risk < 0.25
        assert score.human_review_required is True

    def test_unified_risk_computation_multi_source(self):
        engine = UnifiedRiskEngine()
        score = engine.compute(
            track_id="T17",
            seat_id="B4",
            camera_id="CAM_01",
            behaviour_risk_score=75,
            behaviour_events=["REPEATED_HEAD_TURN", "HAND_OUTSIDE_DESK_ZONE"],
            behaviour_confidence=0.88,
            object_detections=[{"object_class": "mobile_phone", "confidence": 0.85}],
            smoothed_confidences={"mobile_phone": 0.82},
            evidence_ready={"mobile_phone": True},
            retrospective_risk=0.78,
            verification_status=VerificationStatus.CONFIRMED_EVIDENCE,
        )
        assert score.combined_risk >= 0.70
        assert score.status == "HUMAN_REVIEW_REQUIRED"
        assert "BEHAVIOUR_ENGINE" in score.sources
        assert "ROI_VERIFIER" in score.sources
        assert "RETROSPECTIVE_VERIFIER" in score.sources
        assert score.human_review_required is True


class TestAsyncWorkerLifecycle:
    """Test AsyncPipelineWorker thread lifecycle and frame packet production."""

    def test_worker_start_and_telemetry(self):
        worker = AsyncPipelineWorker(mock_mode=True)
        worker.start()
        try:
            time.sleep(0.2)  # Allow worker loop to run a few iterations
            _, packet, fps = worker.get_latest_frame()
            assert packet is not None
            assert packet["type"] == "FRAME_TELEMETRY"
            assert "tracks" in packet
            assert "groups" in packet
            assert len(packet["tracks"]) > 0
        finally:
            worker.stop()
