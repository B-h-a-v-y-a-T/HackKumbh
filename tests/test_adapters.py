import pytest
from app.schemas.perception import Part1PerceptionInput
from app.schemas.behaviour import Part2BehaviourInput
from app.schemas.verification import Part3VerificationInput
from app.integrations.part1_adapter import Part1Adapter
from app.integrations.part2_adapter import Part2Adapter
from app.integrations.part3_adapter import Part3Adapter

def test_part1_adapter():
    inp = Part1PerceptionInput(
        timestamp=1724074812.42,
        camera_id="CAM_01",
        track_id="T17",
        seat_id="B4",
        head_direction="RIGHT",
        head_confidence=0.91,
        hand_visibility=0.83,
        body_visibility=0.94,
        occlusion_score=0.12,
        visibility_score=0.87,
        writing_state="ACTIVE"
    )
    norm = Part1Adapter.adapt(inp)
    assert norm.source == "PART_1"
    assert norm.track_ids == ["T17"]
    assert norm.seat_ids == ["B4"]
    assert norm.event_type == "HEAD_TURNING_RIGHT"
    assert norm.confidence == 0.91

def test_part2_adapter():
    inp = Part2BehaviourInput(
        timestamp=1724074812.42,
        track_id="T17",
        seat_id="B4",
        risk_score=78,
        risk_level="HIGH",
        events=["NEIGHBOUR_GAZE", "TORSO_ROTATE"],
        duration_sec=8.4,
        confidence=0.88
    )
    norm = Part2Adapter.adapt(inp)
    assert norm.source == "PART_2"
    assert norm.severity == "HIGH"
    assert norm.track_ids == ["T17"]
    assert norm.metadata["risk_score"] == 78

def test_part3_adapter():
    inp = Part3VerificationInput(
        verification_id="V104",
        alert_id="A104",
        track_ids=["T17", "T18"],
        verified_events=["REPEATED_NEIGHBOUR_GAZE", "OBJECT_INTERACTION"],
        object_detected="PHONE",
        verification_confidence=0.94,
        live_risk=0.31,
        verified_risk=0.81,
        verification_status="CONFIRMED"
    )
    norm = Part3Adapter.adapt(inp)
    assert norm.source == "PART_3"
    assert norm.severity == "CRITICAL"
    assert norm.metadata["object_detected"] == "PHONE"
