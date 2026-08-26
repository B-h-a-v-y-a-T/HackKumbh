"""
Calculator Discriminator & False-Positive Rejection Engine.

Rule:
- An object with multiple buttons (keypad array with >= 6 buttons) is identified as a CALCULATOR.
- An object without multiple buttons (< 6 buttons, e.g. smooth smartphone screen / phone back) is identified as a PHONE.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CalculatorDiscriminator:
    """
    Discriminator that identifies whether a detected handheld object is a CALCULATOR
    (object with multiple physical buttons) or a PHONE (smooth touchscreen / flat device).
    """

    def __init__(self, min_buttons: int = 6) -> None:
        self.min_buttons = min_buttons

    def is_calculator(self, crop: np.ndarray) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Analyze an image crop of a detected handheld device.

        Args:
            crop: BGR or grayscale numpy array of the detected object box.

        Returns:
            Tuple of (is_calculator: bool, confidence_score: float, metrics: dict)
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
            return False, 0.0, {"reason": "crop_too_small", "num_buttons": 0}

        h, w = crop.shape[:2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

        # Standardize size for consistent contour analysis
        tw, th = 180, 320
        resized = cv2.resize(gray, (tw, th), interpolation=cv2.INTER_AREA)
        total_area = float(tw * th)

        # 1. Bilateral filter to smooth glass reflections while keeping sharp physical key edges
        blurred = cv2.bilateralFilter(resized, 9, 60, 60)

        # 2. Extract Keypad Button Shapes via Edge Detection + Morphology
        edges = cv2.Canny(blurred, 40, 130)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Adaptive thresholding for button shapes
        adapt = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 17, 4
        )
        combined = cv2.bitwise_or(edges_closed, cv2.morphologyEx(adapt, cv2.MORPH_OPEN, kernel))

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        button_candidates: List[Dict[str, Any]] = []

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            box_area = bw * bh
            area_ratio = box_area / total_area
            aspect_ratio = bw / float(bh) if bh > 0 else 0

            # Button criteria:
            # - Area ratio between 0.15% and 5.5% of total device face
            # - Aspect ratio between 0.35 and 3.5
            # - Minimum pixel dimensions >= 6x5
            if 0.0015 <= area_ratio <= 0.055 and 0.35 <= aspect_ratio <= 3.5:
                if bw >= 6 and bh >= 5:
                    # Deduplicate overlapping boxes
                    overlap = False
                    for existing in button_candidates:
                        if abs(existing["x"] - bx) < 6 and abs(existing["y"] - by) < 6:
                            overlap = True
                            break
                    if not overlap:
                        button_candidates.append({
                            "x": bx,
                            "y": by,
                            "w": bw,
                            "h": bh,
                            "cx": bx + bw / 2.0,
                            "cy": by + bh / 2.0,
                            "area_ratio": area_ratio,
                        })

        num_buttons = len(button_candidates)

        # 3. Rule: An object with multiple buttons (>= 6) is a CALCULATOR.
        # An object without multiple buttons (< 6) is a PHONE.
        is_calc = (num_buttons >= self.min_buttons)
        calc_score = min(1.0, 0.50 + (num_buttons / 25.0) * 0.50) if is_calc else 0.0

        metrics = {
            "num_buttons": num_buttons,
            "min_buttons_required": self.min_buttons,
            "calc_score": round(calc_score, 3),
            "is_calculator": is_calc,
        }

        return is_calc, round(calc_score, 3), metrics


# Singleton helper instance
_default_discriminator: Optional[CalculatorDiscriminator] = None


def get_calculator_discriminator() -> CalculatorDiscriminator:
    """Get or create singleton CalculatorDiscriminator instance."""
    global _default_discriminator
    if _default_discriminator is None:
        _default_discriminator = CalculatorDiscriminator(min_buttons=6)
    return _default_discriminator

