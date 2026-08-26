"""
Test Suite: Object Classification, Confusion Matrix, Temporal Consensus & Calibrated Risk Engine.

Verifies:
1. Class-specific thresholds (Phone: 0.60, Chit: 0.50, Prohibited: 0.55).
2. Elimination of false phone bias on paper chits and weak signals.
3. Multi-frame temporal consensus and conflict resolution.
4. Immunity of risk engine to weak (0.05) detections.
5. Exponential risk decay when behavior normalizes.
6. Canonical Evidence Event consistency across pipeline and UI.
7. Clean visualizer overlay (no human bounding boxes).
"""

import time
import numpy as np
import pytest

from app.models.yolo_detector import (
    CLASS_MOBILE_PHONE,
    CLASS_PAPER_CHIT,
    CLASS_PROHIBITED_OBJECT,
    CLASS_UNKNOWN_OBJECT,
    CLASS_LOW_CONFIDENCE_OBJECT,
    PHONE_CONFIDENCE_THRESHOLD,
    CHIT_CONFIDENCE_THRESHOLD,
    PROHIBITED_OBJECT_CONFIDENCE_THRESHOLD,
    MockYOLO26SDetector,
)
from app.roi.consensus import TemporalConsensusTracker, compute_iou
from app.schemas.common import ObjectDetection, BBox
from app.schemas.evidence import EvidenceEvent
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.behaviour.schemas.pose import FrameInput, TrackPose, Keypoint
from app.behaviour.schemas.events import BehaviourEvent, RiskStatus
from app.perception.visualization.debug_visualizer import DebugVisualizer
from app.perception.core.data_models import PipelineOutput, StudentState, TrackingState


def make_dummy_keypoints():
    return [Keypoint(x=0.5, y=0.5, confidence=0.9) for _ in range(17)]


# ---------------------------------------------------------------------------
# 1. Class-Specific Thresholds & Mock Detector Mapping
# ---------------------------------------------------------------------------

def test_mock_detector_class_mapping():
    detector = MockYOLO26SDetector()
    detector.load("cpu")
    dummy_img = np.zeros((300, 300, 3), dtype=np.uint8)

    # Desk reach trigger should generate paper_chit, NOT mobile_phone
    chit_count = 0
    phone_count = 0
    for _ in range(50):
        dets = detector.predict(dummy_img, trigger="HAND_OUTSIDE_DESK")
        for d in dets:
            if d.object_class == CLASS_PAPER_CHIT:
                chit_count += 1
            elif d.object_class == CLASS_MOBILE_PHONE:
                phone_count += 1

    assert chit_count > 0, "Expected paper chit detections on desk reaching trigger"
    assert chit_count > phone_count, "Chit detections must dominate over phone on desk reaching"


def test_iou_computation():
    box1 = [10, 10, 50, 50]
    box2 = [10, 10, 50, 50]
    assert compute_iou(box1, box2) == 1.0

    box3 = [100, 100, 150, 150]
    assert compute_iou(box1, box3) == 0.0

    box4 = [30, 30, 70, 70]
    iou = compute_iou(box1, box4)
    assert 0.1 < iou < 0.5


# ---------------------------------------------------------------------------
# 2. Temporal Object Consensus Tracker
# ---------------------------------------------------------------------------

def test_temporal_consensus_class_agreement():
    tracker = TemporalConsensusTracker(window_sec=3.0)
    t0 = 100.0

    # Frame 1: Chit 0.72
    det1 = [ObjectDetection(object_class=CLASS_PAPER_CHIT, confidence=0.72, bbox=[100, 100, 140, 130])]
    res1 = tracker.update("T12", det1, t0, seat_id="S12")
    assert res1.consensus_class == CLASS_PAPER_CHIT
    assert not res1.is_confirmed  # needs >= 2 observations

    # Frame 2: Chit 0.78 after 0.8s
    det2 = [ObjectDetection(object_class=CLASS_PAPER_CHIT, confidence=0.78, bbox=[102, 101, 142, 131])]
    res2 = tracker.update("T12", det2, t0 + 0.8, seat_id="S12")
    assert res2.consensus_class == CLASS_PAPER_CHIT
    assert res2.is_confirmed
    assert res2.persistence_sec >= 0.8
    assert res2.mean_confidence >= 0.70


def test_temporal_consensus_conflict_resolution():
    tracker = TemporalConsensusTracker(window_sec=3.0)
    t0 = 200.0

    # Alternating classes: Frame 1 phone, Frame 2 chit
    det1 = [ObjectDetection(object_class=CLASS_MOBILE_PHONE, confidence=0.65, bbox=[100, 100, 150, 180])]
    det2 = [ObjectDetection(object_class=CLASS_PAPER_CHIT, confidence=0.62, bbox=[100, 100, 150, 180])]

    tracker.update("T05", det1, t0)
    res = tracker.update("T05", det2, t0 + 0.4)

    # Inconsistent / alternating detections should resolve to unknown_object with lower confidence
    assert res.consensus_class == "unknown_object"
    assert res.mean_confidence < 0.60


# ---------------------------------------------------------------------------
# 3. Calibrated Risk Engine & Zero-Risk on Weak Detections
# ---------------------------------------------------------------------------

def test_weak_detection_immunity():
    engine = BehaviourRiskEngine()
    
    # Track with very weak 0.05 detection (e.g. noise artifact)
    weak_obj = [{"object_class": "mobile_phone", "confidence": 0.05, "bbox": [10, 10, 40, 40]}]
    
    frame = FrameInput(
        frame_id=1,
        timestamp_ms=1000,
        tracks=[
            TrackPose(
                track_id="T01",
                seat_id="S01",
                keypoints=make_dummy_keypoints(),
                object_detections=weak_obj,
                temporal_object_score=0.05,
                additional_meta={"visibility_overall": 1.0},
            )
        ]
    )

    out = engine.process_frame(frame)
    track_out = out.tracks[0]
    
    # 0.05 detection must contribute ZERO to risk
    assert track_out.risk_score <= 10
    assert track_out.status == RiskStatus.NORMAL
    assert BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value not in track_out.events


def test_calibrated_chit_evidence_risk():
    engine = BehaviourRiskEngine()
    
    # Solid chit evidence with hand breach
    chit_obj = [{"object_class": "paper_chit", "confidence": 0.82, "bbox": [200, 300, 250, 340]}]
    
    frame = FrameInput(
        frame_id=1,
        timestamp_ms=1000,
        tracks=[
            TrackPose(
                track_id="T12",
                seat_id="S12",
                keypoints=make_dummy_keypoints(),
                object_detections=chit_obj,
                temporal_object_score=0.80,
                hand_outside_zone=True,
                additional_meta={"visibility_overall": 0.95},
            )
        ]
    )

    out = engine.process_frame(frame)
    track_out = out.tracks[0]

    assert BehaviourEvent.PAPER_CHIT_DETECTED.value in track_out.events
    assert track_out.risk_score >= 40  # Significant rise
    assert track_out.risk_score <= 90  # Bounded, not auto-100 on single frame


def test_risk_exponential_decay():
    engine = BehaviourRiskEngine()

    # Step 1: Raise risk with anomalous evidence
    frame1 = FrameInput(
        frame_id=1,
        timestamp_ms=1000,
        tracks=[
            TrackPose(
                track_id="T14",
                seat_id="S14",
                keypoints=make_dummy_keypoints(),
                hand_outside_zone=True,
                object_detections=[{"object_class": "paper_chit", "confidence": 0.85, "bbox": [100, 100, 150, 150]}],
                temporal_object_score=0.85,
            )
        ]
    )
    out1 = engine.process_frame(frame1)
    peak_risk = out1.tracks[0].risk_score
    assert peak_risk >= 50

    # Step 2: Behavior normalizes over 4 seconds
    frame2 = FrameInput(
        frame_id=40,
        timestamp_ms=5000,
        tracks=[
            TrackPose(
                track_id="T14",
                seat_id="S14",
                keypoints=make_dummy_keypoints(),
                hand_outside_zone=False,
                object_detections=[],
                temporal_object_score=0.0,
            )
        ]
    )
    out2 = engine.process_frame(frame2)
    decayed_risk = out2.tracks[0].risk_score

    assert decayed_risk < peak_risk, f"Risk should decay: {decayed_risk} < {peak_risk}"


# ---------------------------------------------------------------------------
# 4. Single Source of Truth Canonical Event
# ---------------------------------------------------------------------------

def test_canonical_evidence_event_structure():
    evt = EvidenceEvent(
        alert_id="EVT-1042",
        event_id="EVT-1042",
        track_ids=["T16"],
        camera_id="CAM_01",
        seat_ids=["S26"],
        start_time=12.4,
        end_time=14.0,
        track_id="T16",
        seat_id="S26",
        object_class="paper_chit",
        object_confidence=0.76,
        object_bbox=[320, 240, 360, 280],
        persistence_sec=1.6,
        detection_count=4,
        status="HUMAN_REVIEW_REQUIRED",
    )

    dump = evt.model_dump()
    assert dump["alert_id"] == "EVT-1042"
    assert dump["event_id"] == "EVT-1042"
    assert dump["track_id"] == "T16"
    assert dump["seat_id"] == "S26"
    assert dump["object_class"] == "paper_chit"
    assert dump["object_confidence"] == 0.76
    assert dump["object_bbox"] == [320, 240, 360, 280]
    assert "Paper Chit detected near T16 / Seat S26 (Confidence: 76%)" in dump["text_summary"]
    assert dump["human_review_required"] is True


# ---------------------------------------------------------------------------
# 5. Clean Visualizer Overlay (No Human Bounding Boxes)
# ---------------------------------------------------------------------------

def test_debug_visualizer_clean_overlay():
    vis = DebugVisualizer(enabled=True, show_bbox=False)
    assert vis.show_bbox is False, "show_bbox must be False for clean UI"

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    student = StudentState(
        track_id="T17",
        seat_id="S04",
        tracking_state=TrackingState.TRACKED,
        bbox=None,  # No bbox
        keypoints=None,
    )
    p_out = PipelineOutput(students=[student])

    class MockRisk:
        risk_score = 28
        object_evidence = [
            {"object_class": "paper_chit", "confidence": 0.76, "bbox": [500, 300, 540, 330]}
        ]

    canvas = vis.draw(frame, p_out, risk_by_track={"T17": MockRisk()})
    assert canvas is not None
    assert canvas.shape == (720, 1280, 3)
