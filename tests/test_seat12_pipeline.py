"""
Regression tests for Part 3 Seat 12 Paper Chit Detection and Pipeline Integration.

Tests the full end-to-end pipeline:
Student/Track → Desk ROI → Behaviour Trigger → High-Resolution ROI Crop
→ Image Quality → YOLO Object Detection → Chit Evidence → Temporal Evidence
→ Risk Engine → Explainable Dashboard Telemetry
"""

import math
import numpy as np
import pytest
from pathlib import Path

from app.perception.core.data_models import (
    BoundingBox as P1BoundingBox,
    KeypointSet,
    StudentState,
    TrackingState,
    DeskROI,
)
from app.perception.spatial.desk_roi import DeskROIEstimator
from app.behaviour.schemas.pose import TrackPose, Keypoint, BoundingBox as P2BoundingBox, DeskZone, FrameInput
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode, RiskStatus
from app.behaviour.engine.risk_engine import BehaviourRiskEngine
from app.behaviour.roi_bridge import should_trigger_roi, get_trigger_for_events
from app.behaviour.adapter import pipeline_output_to_frame_input
from app.roi.cropper import ROICropper
from app.roi.quality import ImageQualityAnalyzer, CLAHEPreprocessor
from app.roi.temporal import TemporalSmoother
from app.models.yolo_detector import MockYOLO26SDetector
from app.schemas.common import TriggerType


def test_desk_roi_estimator_generates_comprehensive_interaction_workspace():
    """Test that DeskROIEstimator covers hands, desk surface, and lower interaction zone."""
    estimator = DeskROIEstimator()

    # Create keypoints mimicking a seated student (1280x720 frame)
    kps_data = np.zeros((17, 3), dtype=np.float32)
    # Head/Nose
    kps_data[0] = [640.0, 180.0, 0.95]
    # Shoulders
    kps_data[5] = [580.0, 240.0, 0.90]  # Left shoulder
    kps_data[6] = [700.0, 240.0, 0.90]  # Right shoulder
    # Elbows
    kps_data[7] = [560.0, 320.0, 0.85]
    kps_data[8] = [720.0, 320.0, 0.85]
    # Wrists resting on / near desk
    kps_data[9] = [590.0, 420.0, 0.88]  # Left wrist
    kps_data[10] = [680.0, 440.0, 0.85]  # Right wrist

    kps = KeypointSet(xy=kps_data[:, :2], confidence=kps_data[:, 2])
    person_bbox = P1BoundingBox(x1=540.0, y1=150.0, x2=740.0, y2=580.0, confidence=0.92)

    desk_roi = estimator.estimate(kps, person_bbox, img_w=1280, img_h=720)

    assert desk_roi is not None
    assert desk_roi.confidence >= 0.4
    roi_bbox = desk_roi.bbox

    # Ensure ROI covers shoulder level to below wrists/lap
    assert roi_bbox.y1 <= 245.0
    assert roi_bbox.y2 >= 480.0

    # Ensure horizontal padding provides broad desk workspace coverage
    assert roi_bbox.width >= 180.0
    assert roi_bbox.x1 < 580.0
    assert roi_bbox.x2 > 700.0


def test_roi_bridge_trigger_mapping():
    """Test that behaviour events correctly map to TriggerType and trigger ROI detection."""
    # Hand outside desk
    trigger = get_trigger_for_events([BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value])
    assert trigger == TriggerType.HAND_OUTSIDE_DESK

    # Paper chit detected
    trigger_chit = get_trigger_for_events([BehaviourEvent.PAPER_CHIT_DETECTED.value])
    assert trigger_chit == TriggerType.OBJECT_ALREADY_DETECTED

    # Reaching towards neighbour
    trigger_reach = get_trigger_for_events([BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value])
    assert trigger_reach == TriggerType.NEIGHBOUR_INTERACTION


def test_cropper_high_res_and_quality():
    """Test ROICropper and image quality analysis on native resolution frames."""
    cropper = ROICropper(detector_input_size=640)
    quality_analyzer = ImageQualityAnalyzer()
    clahe_proc = CLAHEPreprocessor()

    # Create dummy 1280x720 frame
    frame = np.full((720, 1280, 3), 120, dtype=np.uint8)
    cv2_rect_roi = [500, 200, 750, 500]

    crop, valid_roi = cropper.crop(frame, cv2_rect_roi, resize_to_detector=False)
    assert crop.shape[0] == 300
    assert crop.shape[1] == 250

    q_metric = quality_analyzer.analyze(crop)
    assert q_metric.image_quality >= 0.0
    assert not q_metric.overexposure

    enhanced, _ = clahe_proc.process(crop, q_metric)
    assert enhanced.shape == crop.shape

    det_input = cropper._resize_for_detector(enhanced)
    assert det_input.shape == (640, 640, 3)


def test_temporal_smoother_accumulation():
    """Test multi-frame evidence smoothing and evidence readiness."""
    smoother = TemporalSmoother(
        window_sizes={"paper_chit": 4},
        thresholds={"paper_chit": 0.40},
    )

    track_id = "T14"

    # Frame 1: Low observation
    s1, ready1 = smoother.update(track_id, "paper_chit", 0.35)
    assert not ready1

    # Frame 2: Strong observation
    s2, ready2 = smoother.update(track_id, "paper_chit", 0.75)
    assert ready2  # Smoothed >= 0.40 and length >= 2
    assert s2 >= 0.40

    # Frame 3: Sustained observation
    s3, ready3 = smoother.update(track_id, "paper_chit", 0.80)
    assert ready3
    assert s3 > s2


def test_behaviour_risk_engine_integrates_object_evidence():
    """Test that BehaviourRiskEngine ingests Part 3 object evidence and elevates risk with explainable reasons."""
    engine = BehaviourRiskEngine()

    # Mock normal track pose
    kps = [Keypoint(x=0.5, y=0.2 + i * 0.03, confidence=0.9) for i in range(17)]
    track = TrackPose(
        track_id="T14",
        seat_id="12",
        keypoints=kps,
        bbox=P2BoundingBox(x_min=0.4, y_min=0.2, x_max=0.6, y_max=0.8, confidence=0.95),
        desk_zone=DeskZone(seat_id="12", x_min=0.35, y_min=0.35, x_max=0.65, y_max=0.75),
        object_detections=[{
            "object_class": "paper_chit",
            "confidence": 0.82,
            "bbox": [550, 380, 600, 420],
        }],
        temporal_object_score=0.78,
    )

    # Process consecutive frames to verify leaky integrator attack
    for f_idx in range(1, 4):
        frame_in = FrameInput(
            frame_id=f_idx,
            timestamp_ms=1000.0 + (f_idx * 150.0),
            tracks=[track],
        )
        result = engine.process_frame(frame_in)

    assert len(result.tracks) == 1
    t_out = result.tracks[0]

    # Verify explainable reason codes
    assert ReasonCode.PAPER_CHIT_SUSPICION in t_out.reason_codes
    assert ReasonCode.CONTRABAND_ROI_EVIDENCE in t_out.reason_codes
    assert BehaviourEvent.PAPER_CHIT_DETECTED.value in t_out.events

    # Verify object evidence passed in payload
    assert t_out.object_evidence is not None
    assert t_out.temporal_object_score == 0.78

    # Verify risk status elevates to UNUSUAL or SUSPICIOUS (never Cheating)
    assert t_out.status in (RiskStatus.UNUSUAL_BEHAVIOUR, RiskStatus.SUSPICIOUS_BEHAVIOUR)
    assert t_out.risk_score >= 50


def test_clean_pipeline_without_contraband():
    """Test that a student behaving normally without contraband maintains a low normal risk score."""
    engine = BehaviourRiskEngine()

    kps = [Keypoint(x=0.5, y=0.2 + i * 0.03, confidence=0.9) for i in range(17)]
    track = TrackPose(
        track_id="T01",
        seat_id="01",
        keypoints=kps,
        bbox=P2BoundingBox(x_min=0.4, y_min=0.2, x_max=0.6, y_max=0.8, confidence=0.95),
        desk_zone=DeskZone(seat_id="01", x_min=0.35, y_min=0.35, x_max=0.65, y_max=0.75),
        object_detections=None,
        temporal_object_score=None,
    )

    frame_in = FrameInput(
        frame_id=1,
        timestamp_ms=1000.0,
        tracks=[track],
    )

    result = engine.process_frame(frame_in)
    t_out = result.tracks[0]

    assert t_out.risk_score < 25
    assert t_out.status == RiskStatus.NORMAL
    assert ReasonCode.PAPER_CHIT_SUSPICION not in t_out.reason_codes
