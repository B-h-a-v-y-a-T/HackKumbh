"""Tests for image quality analysis and CLAHE preprocessing."""

import numpy as np
import pytest
from app.roi.quality import ImageQualityAnalyzer, CLAHEPreprocessor


class TestImageQuality:
    def setup_method(self):
        self.analyzer = ImageQualityAnalyzer()

    def test_normal_image_quality(self, small_frame):
        q = self.analyzer.analyze(small_frame)
        assert 0.0 <= q.image_quality <= 1.0
        assert 0.0 <= q.contrast_quality <= 1.0
        assert not q.clahe_applied

    def test_overexposure_detected(self, overexposed_frame):
        q = self.analyzer.analyze(overexposed_frame)
        assert q.overexposure is True
        assert q.clipping_ratio > 0.1

    def test_underexposure_detected(self, dark_frame):
        q = self.analyzer.analyze(dark_frame)
        assert q.underexposure is True

    def test_low_contrast_detected(self, low_contrast_frame):
        q = self.analyzer.analyze(low_contrast_frame)
        assert q.contrast_quality < 0.3

    def test_quality_score_range(self, small_frame):
        q = self.analyzer.analyze(small_frame)
        assert 0.0 <= q.image_quality <= 1.0
        assert 0.0 <= q.blur_score <= 1.0


class TestCLAHE:
    def setup_method(self):
        self.clahe = CLAHEPreprocessor()
        self.analyzer = ImageQualityAnalyzer()

    def test_clahe_not_applied_overexposed(self, overexposed_frame):
        q = self.analyzer.analyze(overexposed_frame)
        assert q.overexposure
        result, updated_q = self.clahe.process(overexposed_frame, q)
        assert not updated_q.clahe_applied

    def test_clahe_applied_low_contrast(self, low_contrast_frame):
        q = self.analyzer.analyze(low_contrast_frame)
        if q.contrast_quality < 0.5:
            result, updated_q = self.clahe.process(low_contrast_frame, q)
            assert updated_q.clahe_applied
            assert result.shape == low_contrast_frame.shape

    def test_clahe_preserves_shape(self, small_frame):
        result = self.clahe.apply(small_frame)
        assert result.shape == small_frame.shape

    def test_should_apply_logic(self):
        from app.schemas.common import ImageQuality
        q_low = ImageQuality(image_quality=0.3, contrast_quality=0.2, overexposure=False)
        assert self.clahe.should_apply(q_low) is True

        q_over = ImageQuality(image_quality=0.3, contrast_quality=0.2, overexposure=True)
        assert self.clahe.should_apply(q_over) is False

        q_good = ImageQuality(image_quality=0.8, contrast_quality=0.8, overexposure=False)
        assert self.clahe.should_apply(q_good) is False
