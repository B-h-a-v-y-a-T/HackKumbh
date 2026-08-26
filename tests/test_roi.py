"""Tests for ROI validation and cropping."""

import numpy as np
import pytest
from app.roi.cropper import ROICropper


class TestROIValidation:
    def setup_method(self):
        self.cropper = ROICropper(detector_input_size=640)

    def test_valid_roi(self, sample_frame):
        roi = [720, 300, 1080, 780]
        validated = self.cropper.validate_roi(roi, sample_frame.shape)
        assert validated == roi

    def test_roi_clamped_to_frame(self, sample_frame):
        roi = [1800, 900, 2000, 1200]  # Extends beyond 1920x1080
        validated = self.cropper.validate_roi(roi, sample_frame.shape)
        assert validated[2] <= 1920
        assert validated[3] <= 1080

    def test_invalid_roi_zero_area(self, sample_frame):
        with pytest.raises(ValueError, match="Invalid ROI"):
            self.cropper.validate_roi([500, 500, 500, 500], sample_frame.shape)

    def test_invalid_roi_negative(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            self.cropper.validate_roi([50, 50, 30, 30], frame.shape)

    def test_roi_negative_coords_clamped(self, sample_frame):
        roi = [-10, -10, 100, 100]
        validated = self.cropper.validate_roi(roi, sample_frame.shape)
        assert validated[0] >= 0
        assert validated[1] >= 0


class TestROICropping:
    def setup_method(self):
        self.cropper = ROICropper(detector_input_size=640)

    def test_crop_from_original(self, sample_frame):
        """CRITICAL: crop must come from original high-res frame."""
        roi = [720, 300, 1080, 780]
        crop, validated = self.cropper.crop(sample_frame, roi, resize_to_detector=False)
        expected_w = roi[2] - roi[0]  # 360
        expected_h = roi[3] - roi[1]  # 480
        assert crop.shape == (expected_h, expected_w, 3)

    def test_crop_preserves_original_pixels(self, sample_frame):
        """Crop pixel values must match original frame."""
        roi = [100, 100, 200, 200]
        crop, _ = self.cropper.crop(sample_frame, roi, resize_to_detector=False)
        expected = sample_frame[100:200, 100:200]
        np.testing.assert_array_equal(crop, expected)

    def test_crop_resize_for_detector(self, sample_frame):
        roi = [720, 300, 1080, 780]
        crop, _ = self.cropper.crop(sample_frame, roi, resize_to_detector=True)
        assert crop.shape == (640, 640, 3)

    def test_crop_from_bytes(self):
        import cv2
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", frame)
        loaded = self.cropper.load_frame(buf.tobytes())
        assert loaded.shape[0] > 0

    def test_missing_frame_raises(self):
        with pytest.raises(FileNotFoundError):
            self.cropper.load_frame("nonexistent_frame.jpg")

    def test_empty_crop_raises(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            self.cropper.crop(frame, [50, 50, 50, 50])

    def test_multiple_crops(self, sample_frame):
        rois = [[100, 100, 300, 300], [500, 200, 800, 600]]
        results = self.cropper.crop_multiple(sample_frame, rois, resize_to_detector=False)
        assert len(results) == 2
