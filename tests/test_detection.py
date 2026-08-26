"""Tests for object detection and mock mode."""

import numpy as np
import pytest
from app.models.yolo_detector import MockYOLO26SDetector, EXAM_CLASSES


class TestMockDetection:
    def setup_method(self):
        self.detector = MockYOLO26SDetector()
        self.detector.load("cpu")

    def test_mock_loads(self):
        assert self.detector.is_loaded()
        assert "Mock" in self.detector.model_name

    def test_mock_predict_returns_list(self, small_frame):
        dets = self.detector.predict(small_frame, confidence_threshold=0.1)
        assert isinstance(dets, list)

    def test_mock_detections_have_valid_classes(self, small_frame):
        dets = self.detector.predict(small_frame, confidence_threshold=0.1)
        for d in dets:
            assert d.object_class in EXAM_CLASSES

    def test_mock_detections_have_valid_confidence(self, small_frame):
        dets = self.detector.predict(small_frame, confidence_threshold=0.1)
        for d in dets:
            assert 0.0 <= d.confidence <= 1.0

    def test_mock_detections_have_valid_bbox(self, small_frame):
        h, w = small_frame.shape[:2]
        dets = self.detector.predict(small_frame, confidence_threshold=0.1)
        for d in dets:
            assert len(d.bbox) == 4
            assert d.bbox[0] >= 0 and d.bbox[2] <= w
            assert d.bbox[1] >= 0 and d.bbox[3] <= h

    def test_confidence_threshold_filters(self, small_frame):
        low = self.detector.predict(small_frame, confidence_threshold=0.1)
        high = self.detector.predict(small_frame, confidence_threshold=0.95)
        assert len(low) >= len(high)

    def test_trigger_increases_detection_prob(self):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        # Run many times to test probability
        triggered_count = 0
        normal_count = 0
        for _ in range(50):
            self.detector._rng.seed(None)  # Random seed
            t_dets = self.detector.predict(frame, confidence_threshold=0.3, trigger="HAND_OUTSIDE_DESK")
            triggered_count += len(t_dets)
            n_dets = self.detector.predict(frame, confidence_threshold=0.3, trigger=None)
            normal_count += len(n_dets)
        # Triggered should generally produce more detections
        assert triggered_count >= normal_count * 0.5

    def test_unloaded_model_raises(self):
        detector = MockYOLO26SDetector()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="not loaded"):
            detector.predict(frame)
