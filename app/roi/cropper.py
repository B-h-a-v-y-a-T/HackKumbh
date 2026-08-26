"""
ROI Cropper — Crops from the ORIGINAL high-resolution frame.

CRITICAL: This module crops from the original frame, NEVER from a
downsampled version. A wide-angle 1080p/4K exam camera may contain
many students, and a phone or chit occupies very few pixels. Cropping
from the original preserves maximum useful information for detection.

Pipeline:
    1920x1080 frame → student/desk ROI → 300x450 original pixels
    → resize to detector input size → YOLO26-S
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ROICropper:
    """
    Crops ROIs from original high-resolution frames.

    The ROI represents the student's interaction zone: upper body,
    hands, desk surface, and immediate surroundings. NOT just hands.
    """

    def __init__(self, detector_input_size: int = 640) -> None:
        self._detector_input_size = detector_input_size

    def load_frame(self, source: Union[str, Path, bytes, np.ndarray]) -> np.ndarray:
        """
        Load a frame from various sources.

        Args:
            source: File path, raw bytes, or numpy array (BGR).

        Returns:
            BGR numpy array at original resolution.
        """
        if isinstance(source, np.ndarray):
            return source

        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Frame not found: {path}")
            frame = cv2.imread(str(path))
            if frame is None:
                raise ValueError(f"Could not read image: {path}")
            return frame

        if isinstance(source, bytes):
            arr = np.frombuffer(source, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Could not decode image from bytes")
            return frame

        raise TypeError(f"Unsupported source type: {type(source)}")

    def validate_roi(
        self, roi: List[int], frame_shape: Tuple[int, ...]
    ) -> List[int]:
        """
        Validate and clamp ROI to frame boundaries.

        Args:
            roi: [x1, y1, x2, y2] in original frame coordinates.
            frame_shape: (height, width, channels).

        Returns:
            Validated and clamped ROI.

        Raises:
            ValueError: If ROI is invalid (zero or negative area).
        """
        x1, y1, x2, y2 = roi
        h, w = frame_shape[:2]

        # Clamp to frame boundaries
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"Invalid ROI after clamping: [{x1}, {y1}, {x2}, {y2}] "
                f"for frame of size {w}x{h}"
            )

        return [x1, y1, x2, y2]

    def crop(
        self,
        frame: np.ndarray,
        roi: List[int],
        resize_to_detector: bool = True,
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Crop ROI from the ORIGINAL high-resolution frame.

        This is the core operation that preserves pixel information.
        The crop is taken directly from the original frame, then
        optionally resized to the detector's input size.

        Args:
            frame: Original high-resolution BGR frame.
            roi: [x1, y1, x2, y2] in original frame coordinates.
            resize_to_detector: If True, resize crop to detector input size.

        Returns:
            Tuple of (cropped image, validated ROI).
        """
        validated_roi = self.validate_roi(roi, frame.shape)
        x1, y1, x2, y2 = validated_roi

        # CROP FROM ORIGINAL — this is the critical operation
        crop = frame[y1:y2, x1:x2].copy()

        if crop.size == 0:
            raise ValueError(f"Empty crop for ROI {validated_roi}")

        logger.debug(
            f"Cropped ROI {validated_roi} from {frame.shape[1]}x{frame.shape[0]} → "
            f"{crop.shape[1]}x{crop.shape[0]} original pixels"
        )

        if resize_to_detector:
            crop = self._resize_for_detector(crop)

        return crop, validated_roi

    def _resize_for_detector(self, crop: np.ndarray) -> np.ndarray:
        """
        Resize crop to detector input size while maintaining aspect ratio.
        Uses letterbox padding to avoid distortion.
        """
        h, w = crop.shape[:2]
        target = self._detector_input_size
        scale = min(target / w, target / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Letterbox padding
        canvas = np.full((target, target, 3), 114, dtype=np.uint8)
        top = (target - new_h) // 2
        left = (target - new_w) // 2
        canvas[top : top + new_h, left : left + new_w] = resized

        return canvas

    def crop_multiple(
        self,
        frame: np.ndarray,
        rois: List[List[int]],
        resize_to_detector: bool = True,
    ) -> List[Tuple[np.ndarray, List[int]]]:
        """Crop multiple ROIs from the same original frame."""
        results = []
        for roi in rois:
            try:
                crop, validated = self.crop(frame, roi, resize_to_detector)
                results.append((crop, validated))
            except (ValueError, IndexError) as e:
                logger.warning(f"Skipping invalid ROI {roi}: {e}")
        return results

    def get_crop_info(
        self, frame_shape: Tuple[int, ...], roi: List[int]
    ) -> dict:
        """Get information about the crop without actually cropping."""
        validated = self.validate_roi(roi, frame_shape)
        x1, y1, x2, y2 = validated
        crop_w = x2 - x1
        crop_h = y2 - y1
        frame_h, frame_w = frame_shape[:2]
        return {
            "original_frame_size": [frame_w, frame_h],
            "roi": validated,
            "crop_size": [crop_w, crop_h],
            "crop_pixels": crop_w * crop_h,
            "frame_coverage": round((crop_w * crop_h) / (frame_w * frame_h), 4),
            "detector_input_size": self._detector_input_size,
        }
