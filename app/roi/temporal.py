"""
Temporal Smoothing — Per-track, per-class evidence accumulation.

Prevents one corrupted frame from creating strong evidence.
Different events have different persistence requirements:
  - High-confidence phone detection → can become evidence quickly
  - Behavioural patterns → require longer persistence

Thresholds are configurable per event/class.
Does NOT apply a universal 2.5-3 second rule.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TemporalSmoother:
    """
    Maintains a sliding window of detection confidences per-track, per-class.

    Produces smoothed confidence and an evidence-readiness flag based on
    configurable window sizes and thresholds per class.
    """

    def __init__(
        self,
        window_sizes: Optional[Dict[str, int]] = None,
        thresholds: Optional[Dict[str, float]] = None,
        default_window_size: int = 5,
        default_threshold: float = 0.6,
    ) -> None:
        """
        Args:
            window_sizes: Per-class sliding window size (number of frames).
            thresholds: Per-class minimum smoothed confidence for evidence.
            default_window_size: Default window if class not specified.
            default_threshold: Default threshold if class not specified.
        """
        self._window_sizes = window_sizes or {
            "mobile_phone": 5,
            "paper_chit": 5,
            "prohibited_object": 5,
        }
        self._thresholds = thresholds or {
            "mobile_phone": 0.6,
            "paper_chit": 0.5,
            "prohibited_object": 0.6,
        }
        self._default_window = default_window_size
        self._default_threshold = default_threshold

        # Storage: track_id → class → deque of confidences
        self._history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(deque)
        )

    def update(
        self,
        track_id: str,
        object_class: str,
        confidence: float,
    ) -> Tuple[float, bool]:
        """
        Add a new confidence observation and compute smoothed result.

        Args:
            track_id: Anonymous track identifier.
            object_class: Detection class name.
            confidence: Detection confidence (0-1). Use 0.0 for no detection.

        Returns:
            Tuple of (smoothed_confidence, evidence_ready).
        """
        window_size = self._window_sizes.get(object_class, self._default_window)
        threshold = self._thresholds.get(object_class, self._default_threshold)

        history = self._history[track_id][object_class]
        history.append(confidence)

        # Keep only the window
        while len(history) > window_size:
            history.popleft()

        # Compute smoothed confidence (weighted average, recent frames weighted more)
        smoothed = self._weighted_average(list(history))
        evidence_ready = smoothed >= threshold and len(history) >= 2

        return round(smoothed, 4), evidence_ready

    def update_batch(
        self,
        track_id: str,
        detections: List[Tuple[str, float]],
        all_classes: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[float, bool]]:
        """
        Update temporal smoothing for multiple classes at once.

        For classes in all_classes that have no detection in this frame,
        a 0.0 confidence is recorded (no detection in this frame).

        Args:
            track_id: Anonymous track ID.
            detections: List of (object_class, confidence) tuples.
            all_classes: All classes to track (records 0.0 for missing ones).

        Returns:
            Dict of class → (smoothed_confidence, evidence_ready).
        """
        detected_classes = {d[0] for d in detections}
        results = {}

        # Record detections
        for obj_class, conf in detections:
            smoothed, ready = self.update(track_id, obj_class, conf)
            results[obj_class] = (smoothed, ready)

        # Record absence for tracked classes
        if all_classes:
            for cls in all_classes:
                if cls not in detected_classes:
                    smoothed, ready = self.update(track_id, cls, 0.0)
                    results[cls] = (smoothed, ready)

        return results

    def get_smoothed(self, track_id: str) -> Dict[str, float]:
        """Get all smoothed confidences for a track."""
        if track_id not in self._history:
            return {}
        result = {}
        for cls, history in self._history[track_id].items():
            if len(history) > 0:
                result[cls] = round(self._weighted_average(list(history)), 4)
        return result

    def get_evidence_ready(self, track_id: str) -> Dict[str, bool]:
        """Get evidence readiness for all classes of a track."""
        if track_id not in self._history:
            return {}
        result = {}
        for cls, history in self._history[track_id].items():
            threshold = self._thresholds.get(cls, self._default_threshold)
            smoothed = self._weighted_average(list(history))
            result[cls] = smoothed >= threshold and len(history) >= 2
        return result

    def clear_track(self, track_id: str) -> None:
        """Clear all history for a track."""
        if track_id in self._history:
            del self._history[track_id]

    def clear_all(self) -> None:
        """Clear all temporal history."""
        self._history.clear()

    @staticmethod
    def _weighted_average(values: List[float]) -> float:
        """
        Compute weighted average where recent values are weighted more.

        Uses linearly increasing weights: [1, 2, 3, ..., n].
        """
        if not values:
            return 0.0
        n = len(values)
        weights = list(range(1, n + 1))
        total_weight = sum(weights)
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        return weighted_sum / total_weight

    def update_config(
        self,
        window_sizes: Optional[Dict[str, int]] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        """Update temporal smoothing configuration."""
        if window_sizes:
            self._window_sizes.update(window_sizes)
        if thresholds:
            self._thresholds.update(thresholds)
