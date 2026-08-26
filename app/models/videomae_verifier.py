"""
VideoMAE V2-L Temporal Verifier — Retrospective pipeline.

Identifies suspicious temporal windows by analyzing video frame sequences.
Uses HuggingFace transformers for the real implementation.
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional

import numpy as np

from app.models.base import TemporalVerifier
from app.schemas.common import TemporalWindow

logger = logging.getLogger(__name__)


class VideoMAEV2Verifier(TemporalVerifier):
    """
    Real VideoMAE V2-L implementation using HuggingFace transformers.

    Processes 16-frame clips and produces temporal anomaly scores
    to rank suspicious windows for expensive verification.
    """

    def __init__(self, model_name: str = "OpenGVLab/VideoMAEv2-Large") -> None:
        self._model_name_id = model_name
        self._model = None
        self._processor = None

    def load(self, device: str = "cpu") -> None:
        try:
            import torch
            from transformers import AutoConfig, AutoModel, VideoMAEImageProcessor

            logger.info(f"Loading VideoMAE V2-L from {self._model_name_id} on {device}")
            config = AutoConfig.from_pretrained(
                self._model_name_id, trust_remote_code=True
            )
            self._processor = VideoMAEImageProcessor.from_pretrained(self._model_name_id)
            self._model = AutoModel.from_pretrained(
                self._model_name_id, config=config, trust_remote_code=True
            )
            self._model.to(device)
            self._model.eval()
            self._device = device
            logger.info("VideoMAE V2-L loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load VideoMAE V2-L: {e}")
            raise

    def analyze(
        self,
        frames: List[np.ndarray],
        timestamps: Optional[List[float]] = None,
    ) -> List[TemporalWindow]:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        import torch

        windows = []
        # Process in 16-frame clips
        clip_size = 16
        for i in range(0, len(frames), clip_size):
            clip_frames = frames[i : i + clip_size]
            if len(clip_frames) < clip_size:
                # Pad with last frame if needed
                while len(clip_frames) < clip_size:
                    clip_frames.append(clip_frames[-1])

            # Convert BGR to RGB
            rgb_frames = [f[:, :, ::-1] for f in clip_frames]

            # Process through VideoMAE
            inputs = self._processor(rgb_frames, return_tensors="pt")
            inputs["pixel_values"] = inputs["pixel_values"].permute(0, 2, 1, 3, 4)
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)

            # Compute anomaly score from feature magnitude
            features = outputs.last_hidden_state
            anomaly_score = float(torch.norm(features, dim=-1).mean().cpu())
            # Normalize to 0-1 range (approximate)
            anomaly_score = min(1.0, max(0.0, anomaly_score / 10.0))

            # Determine time window
            start_t = timestamps[i] if timestamps and i < len(timestamps) else float(i)
            end_idx = min(i + clip_size - 1, len(frames) - 1)
            end_t = timestamps[end_idx] if timestamps and end_idx < len(timestamps) else float(end_idx)

            windows.append(TemporalWindow(
                window_start=round(start_t, 2),
                window_end=round(end_t, 2),
                temporal_anomaly_score=round(anomaly_score, 4),
                frame_count=len(clip_frames),
            ))

        return windows

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return f"VideoMAE-V2-L ({self._model_name_id})"


class MockVideoMAEV2Verifier(TemporalVerifier):
    """Mock VideoMAE V2-L for development without GPU."""

    def __init__(self) -> None:
        self._loaded = False
        self._rng = random.Random(123)

    def load(self, device: str = "cpu") -> None:
        logger.info("Loading MockVideoMAEV2Verifier (no GPU required)")
        self._loaded = True

    def analyze(
        self,
        frames: List[np.ndarray],
        timestamps: Optional[List[float]] = None,
    ) -> List[TemporalWindow]:
        if not self._loaded:
            raise RuntimeError("Mock model not loaded.")

        windows = []
        clip_size = 16
        num_clips = max(1, len(frames) // clip_size)

        for i in range(num_clips):
            start_t = timestamps[i * clip_size] if timestamps else float(i * clip_size)
            end_idx = min((i + 1) * clip_size - 1, len(frames) - 1)
            end_t = timestamps[end_idx] if timestamps else float(end_idx)

            # Generate realistic anomaly scores
            # Most windows are normal (low score), some are suspicious
            if self._rng.random() < 0.2:  # 20% chance of suspicious window
                score = round(self._rng.uniform(0.6, 0.95), 4)
            else:
                score = round(self._rng.uniform(0.05, 0.45), 4)

            windows.append(TemporalWindow(
                window_start=round(start_t, 2),
                window_end=round(end_t, 2),
                temporal_anomaly_score=score,
                frame_count=clip_size,
            ))

        return windows

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return "MockVideoMAE-V2-L (no GPU)"
