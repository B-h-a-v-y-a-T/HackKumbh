"""
Image Quality Analysis and CLAHE Preprocessing.

Pipeline:
    Input ROI → exposure analysis → contrast analysis →
    saturation/clipping analysis → optional CLAHE → quality score

IMPORTANT: CLAHE cannot recover information already clipped by overexposure.
If severe overexposure is detected, confidence is reduced and evidence is
marked as low-quality.
"""

from __future__ import annotations

import logging
from typing import Tuple

import cv2
import numpy as np

from app.schemas.common import ImageQuality

logger = logging.getLogger(__name__)


class ImageQualityAnalyzer:
    """
    Assesses image quality of ROI crops for reliable detection.

    Analyzes exposure, contrast, saturation, and clipping to determine
    whether CLAHE should be applied and whether detection confidence
    should be reduced due to poor image quality.
    """

    def __init__(
        self,
        overexposure_threshold: float = 0.15,
        underexposure_threshold: float = 0.15,
        min_contrast_quality: float = 0.3,
        blur_threshold: float = 100.0,
    ) -> None:
        self._overexposure_threshold = overexposure_threshold
        self._underexposure_threshold = underexposure_threshold
        self._min_contrast_quality = min_contrast_quality
        self._blur_threshold = blur_threshold

    def analyze(self, image: np.ndarray) -> ImageQuality:
        """
        Perform comprehensive image quality analysis.

        Args:
            image: BGR image (ROI crop).

        Returns:
            ImageQuality with scores and flags.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Exposure analysis
        overexposure_ratio = self._check_overexposure(gray)
        underexposure_ratio = self._check_underexposure(gray)
        is_overexposed = overexposure_ratio > self._overexposure_threshold
        is_underexposed = underexposure_ratio > self._underexposure_threshold

        # Contrast analysis
        contrast_q = self._compute_contrast_quality(gray)

        # Blur/sharpness analysis
        blur_score = self._compute_blur_score(gray)

        # Clipping ratio (over + under)
        clipping = min(1.0, overexposure_ratio + underexposure_ratio)

        # Overall quality score (weighted combination)
        quality = self._compute_overall_quality(
            overexposure_ratio, underexposure_ratio,
            contrast_q, blur_score
        )

        return ImageQuality(
            image_quality=round(quality, 4),
            overexposure=is_overexposed,
            underexposure=is_underexposed,
            contrast_quality=round(contrast_q, 4),
            blur_score=round(blur_score, 4),
            clipping_ratio=round(clipping, 4),
            clahe_applied=False,
        )

    def _check_overexposure(self, gray: np.ndarray) -> float:
        """Ratio of pixels above 250 (near-white / clipped)."""
        total = gray.size
        clipped = np.sum(gray > 250)
        return float(clipped / total)

    def _check_underexposure(self, gray: np.ndarray) -> float:
        """Ratio of pixels below 5 (near-black / clipped)."""
        total = gray.size
        clipped = np.sum(gray < 5)
        return float(clipped / total)

    def _compute_contrast_quality(self, gray: np.ndarray) -> float:
        """
        Compute contrast quality using RMS contrast normalized to 0-1.
        Higher values mean better contrast.
        """
        std = float(np.std(gray))
        # Normalize: std of ~64 is good contrast, ~128 is max
        quality = min(1.0, std / 64.0)
        return quality

    def _compute_blur_score(self, gray: np.ndarray) -> float:
        """
        Compute sharpness using Laplacian variance.
        Returns 0-1 where 1 is sharp, 0 is blurry.
        """
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_32F).var())
        # Normalize: variance > threshold is considered sharp
        score = min(1.0, laplacian_var / self._blur_threshold)
        return score

    def _compute_overall_quality(
        self,
        overexposure: float,
        underexposure: float,
        contrast: float,
        blur: float,
    ) -> float:
        """Weighted combination of quality factors."""
        # Penalize heavily for overexposure (information is lost)
        exposure_penalty = 1.0 - min(1.0, (overexposure + underexposure) * 2)
        # Combine factors
        quality = (
            0.35 * exposure_penalty
            + 0.30 * contrast
            + 0.25 * blur
            + 0.10 * (1.0 - min(1.0, overexposure * 3))  # Extra overexposure penalty
        )
        return max(0.0, min(1.0, quality))


class CLAHEPreprocessor:
    """
    Applies CLAHE (Contrast Limited Adaptive Histogram Equalization).

    IMPORTANT: CLAHE improves LOCAL contrast but CANNOT recover information
    that has already been clipped by overexposure. If the sensor has
    saturated, those pixels contain no recoverable detail.

    Only applied when:
    - Contrast quality is low
    - Image is NOT severely overexposed (information already lost)
    """

    def __init__(
        self,
        clip_limit: float = 2.0,
        tile_grid_size: Tuple[int, int] = (8, 8),
        min_contrast_to_apply: float = 0.5,
        max_overexposure_to_apply: float = 0.10,
    ) -> None:
        self._clip_limit = clip_limit
        self._tile_grid_size = tile_grid_size
        self._min_contrast_threshold = min_contrast_to_apply
        self._max_overexposure = max_overexposure_to_apply
        self._clahe = cv2.createCLAHE(
            clipLimit=clip_limit, tileGridSize=tile_grid_size
        )

    def should_apply(self, quality: ImageQuality) -> bool:
        """Determine whether CLAHE should be applied based on quality analysis."""
        # Don't apply if overexposed — CLAHE cannot recover clipped information
        if quality.overexposure:
            logger.debug("Skipping CLAHE: overexposure detected (information already lost)")
            return False
        if quality.clipping_ratio > self._max_overexposure:
            logger.debug(f"Skipping CLAHE: clipping ratio {quality.clipping_ratio:.2f} too high")
            return False
        # Apply if contrast is low
        if quality.contrast_quality < self._min_contrast_threshold:
            return True
        return False

    def apply(self, image: np.ndarray) -> np.ndarray:
        """
        Apply CLAHE to improve local contrast.

        Works in LAB color space to preserve color relationships.
        """
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        channels = list(cv2.split(lab))
        channels[0] = self._clahe.apply(channels[0])
        lab = cv2.merge(channels)
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return result

    def process(
        self, image: np.ndarray, quality: ImageQuality
    ) -> Tuple[np.ndarray, ImageQuality]:
        """
        Conditionally apply CLAHE based on image quality.

        Returns the processed image and updated quality info.
        """
        if self.should_apply(quality):
            logger.debug("Applying CLAHE for contrast enhancement")
            processed = self.apply(image)
            # Update quality to reflect CLAHE was applied
            updated = quality.model_copy(update={"clahe_applied": True})
            return processed, updated
        return image, quality
