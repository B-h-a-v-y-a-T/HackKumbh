"""
Temporal Ranker — Ranks temporal windows by suspicion score.

Feeds sampled clips to VideoMAE V2-L, collects anomaly scores,
ranks windows, and selects top-K for expensive verification.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np

from app.models.base import ModelRegistry
from app.schemas.common import TemporalWindow

logger = logging.getLogger(__name__)


class TemporalRanker:
    """
    Ranks temporal windows by anomaly score for selective verification.

    Only the most suspicious windows are sent to expensive RT-DETR + ViTPose.
    """

    def __init__(
        self,
        top_k: int = 5,
        anomaly_threshold: float = 0.6,
        scan_window_seconds: float = 10.0,
        scan_stride_seconds: float = 5.0,
    ) -> None:
        self._top_k = top_k
        self._threshold = anomaly_threshold
        self._window_sec = scan_window_seconds
        self._stride_sec = scan_stride_seconds

    def rank_windows(
        self,
        windows: List[TemporalWindow],
    ) -> List[TemporalWindow]:
        """
        Rank windows by anomaly score and return top-K above threshold.

        Args:
            windows: All temporal windows with anomaly scores.

        Returns:
            Top-K windows sorted by descending anomaly score.
        """
        # Filter above threshold
        suspicious = [w for w in windows if w.temporal_anomaly_score >= self._threshold]

        # Sort by anomaly score descending
        suspicious.sort(key=lambda w: w.temporal_anomaly_score, reverse=True)

        # Return top-K
        selected = suspicious[: self._top_k]

        logger.info(
            f"Ranked {len(windows)} windows → {len(suspicious)} above threshold "
            f"→ selected top {len(selected)}"
        )
        return selected

    def compute_scan_windows(
        self,
        start_time: float,
        end_time: float,
    ) -> List[Tuple[float, float]]:
        """
        Compute overlapping scan windows for the given time range.

        Returns list of (window_start, window_end) tuples.
        """
        windows = []
        t = start_time
        while t + self._window_sec <= end_time:
            windows.append((t, t + self._window_sec))
            t += self._stride_sec
        # Include final partial window if significant
        if t < end_time and (end_time - t) > self._window_sec * 0.3:
            windows.append((t, end_time))
        return windows

    def scan_video_frames(
        self,
        all_frames: List[Tuple[float, np.ndarray]],
    ) -> List[TemporalWindow]:
        """
        Run temporal scanning on extracted video frames.

        Args:
            all_frames: List of (timestamp, frame) tuples.

        Returns:
            List of TemporalWindow with anomaly scores.
        """
        if not all_frames:
            return []

        registry = ModelRegistry.get_instance()
        temporal_model = registry.get_temporal_verifier("videomae")

        # Group frames into windows
        timestamps = [t for t, _ in all_frames]
        start_t = timestamps[0]
        end_t = timestamps[-1]
        scan_windows = self.compute_scan_windows(start_t, end_t)

        results = []
        for w_start, w_end in scan_windows:
            # Get frames in this window
            window_frames = [
                f for t, f in all_frames if w_start <= t <= w_end
            ]
            window_timestamps = [
                t for t, _ in all_frames if w_start <= t <= w_end
            ]

            if len(window_frames) < 2:
                continue

            # Run VideoMAE V2-L
            temporal_results = temporal_model.analyze(
                window_frames, window_timestamps
            )

            # Take the max anomaly score from the sub-windows
            if temporal_results:
                max_result = max(
                    temporal_results, key=lambda r: r.temporal_anomaly_score
                )
                results.append(TemporalWindow(
                    window_start=w_start,
                    window_end=w_end,
                    temporal_anomaly_score=max_result.temporal_anomaly_score,
                    frame_count=len(window_frames),
                ))

        return results

    def update_config(self, **kwargs) -> None:
        if "top_k" in kwargs:
            self._top_k = kwargs["top_k"]
        if "anomaly_threshold" in kwargs:
            self._threshold = kwargs["anomaly_threshold"]
        if "scan_window_seconds" in kwargs:
            self._window_sec = kwargs["scan_window_seconds"]
        if "scan_stride_seconds" in kwargs:
            self._stride_sec = kwargs["scan_stride_seconds"]
