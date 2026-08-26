"""
Unit and Integration Tests for RoboflowPhoneDetector.

Verifies:
1. Native python interface initialization and loading
2. Detection output format [class_name, confidence, bbox]
3. IoU duplicate suppression
4. Temporal confirmation history (UNCONFIRMED -> OBSERVED -> CONFIRMED)
5. Debug section telemetry metrics
6. Diagnostic logging and input frame saving on no-detection
7. ModelRegistry integration
"""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

# Ensure inference module is mockable even if not installed
if "inference" not in sys.modules:
    mock_inference_mod = MagicMock()
    sys.modules["inference"] = mock_inference_mod

from app.models.base import ModelRegistry
from app.object_detection.roboflow_phone_detector import (
    RoboflowPhoneDetector,
    TemporalPhoneTracker,
    compute_iou,
)


def test_compute_iou():
    box1 = [10, 10, 50, 50]
    box2 = [10, 10, 50, 50]
    assert compute_iou(box1, box2) == 1.0

    box3 = [100, 100, 150, 150]
    assert compute_iou(box1, box3) == 0.0

    box4 = [30, 10, 70, 50]
    iou = compute_iou(box1, box4)
    assert 0.0 < iou < 1.0


def test_temporal_phone_tracker():
    tracker = TemporalPhoneTracker(required_frames=3, max_frame_gap=2, iou_match_thresh=0.35)

    det = [{"class_name": "PHONE", "confidence": 0.90, "bbox": [10, 10, 50, 50]}]

    # Frame 1: UNCONFIRMED
    res1 = tracker.update(1, det)
    assert len(res1) == 1
    assert res1[0]["status"] == "UNCONFIRMED"

    # Frame 2: OBSERVED
    res2 = tracker.update(2, det)
    assert len(res2) == 1
    assert res2[0]["status"] == "OBSERVED"

    # Frame 3: CONFIRMED
    res3 = tracker.update(3, det)
    assert len(res3) == 1
    assert res3[0]["status"] == "CONFIRMED"


@patch("inference.get_model")
def test_roboflow_detector_detect_and_iou(mock_get_model):
    # Mock Roboflow Inference model output with duplicate phone predictions
    mock_model = MagicMock()

    class MockPred:
        def __init__(self, x, y, w, h, conf, cls_name):
            self.x = x
            self.y = y
            self.width = w
            self.height = h
            self.confidence = conf
            self.class_name = cls_name

    # Two overlapping predictions for same phone (one higher confidence)
    pred1 = MockPred(100, 100, 40, 40, 0.92, "mobile_phone")
    pred2 = MockPred(102, 101, 38, 42, 0.81, "mobile_phone")

    mock_res = MagicMock()
    mock_res.predictions = [pred1, pred2]
    mock_model.infer.return_value = [mock_res]
    mock_get_model.return_value = mock_model

    detector = RoboflowPhoneDetector(
        model_id="test-phone-model/1",
        api_key="test-api-key",
        confidence_threshold=0.45,
        iou_threshold=0.45,
        confirmation_frames=1,  # Instantly confirm for single-frame test
    )
    detector.load("cpu")

    assert detector.is_loaded() is True
    assert "test-phone-model/1" in detector.model_name

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = detector.detect(frame)

    # IoU suppression should leave only 1 highest-confidence PHONE box
    assert len(results) == 1
    assert results[0]["class_name"] == "PHONE"
    assert results[0]["confidence"] == 0.92
    assert results[0]["bbox"] == [80, 80, 120, 120]

    # Check debug metrics panel
    metrics = detector.debug_metrics
    assert metrics["model_id"] == "test-phone-model/1"
    assert metrics["raw_detections"] == 2
    assert metrics["filtered_phone_detections"] == 1
    assert metrics["final_detections"] == 1


@patch("inference.get_model")
def test_roboflow_detector_no_detection_diagnostic(mock_get_model, tmp_path):
    mock_model = MagicMock()
    mock_res = MagicMock()
    mock_res.predictions = []
    mock_model.infer.return_value = [mock_res]
    mock_get_model.return_value = mock_model

    detector = RoboflowPhoneDetector(
        model_id="test-phone-model/1",
        api_key="test-api-key",
        confidence_threshold=0.45,
    )
    detector.load("cpu")

    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    results = detector.detect(frame)

    assert len(results) == 0
    assert detector.debug_metrics["final_detections"] == 0

    # Diagnostic frame file should be written to data/debug_roboflow_input.jpg
    debug_file = Path("data/debug_roboflow_input.jpg")
    assert debug_file.exists()


def test_model_registry_roboflow_registration():
    registry = ModelRegistry.get_instance()
    detector = RoboflowPhoneDetector(model_id="test-model/1")
    registry.register_detector("live", detector)

    fetched = registry.get_detector("live")
    assert isinstance(fetched, RoboflowPhoneDetector)
    assert fetched.model_id == "test-model/1"
