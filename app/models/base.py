"""
Model abstraction layer.

All model implementations must conform to these interfaces.
The rest of the application depends on interfaces, NOT specific model implementations.
This allows individual models to be replaced without changing the API.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

import numpy as np

from app.schemas.common import ObjectDetection, PoseEvidence, TemporalWindow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract Base Classes (Interfaces)
# ---------------------------------------------------------------------------

class ObjectDetector(ABC):
    """Interface for object detection models (e.g. YOLO26-S, RT-DETRv4-L)."""

    @abstractmethod
    def load(self, device: str = "cpu") -> None:
        """Load model weights onto the specified device."""
        ...

    @abstractmethod
    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        classes: Optional[List[str]] = None,
    ) -> List[ObjectDetection]:
        """
        Run object detection on an image.

        Args:
            image: BGR image as numpy array (OpenCV format).
            confidence_threshold: Minimum confidence for detections.
            classes: Optional list of class names to filter.

        Returns:
            List of ObjectDetection results. Evidence only, not verdicts.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name."""
        ...


class TemporalVerifier(ABC):
    """Interface for temporal verification models (e.g. VideoMAE V2-L)."""

    @abstractmethod
    def load(self, device: str = "cpu") -> None:
        """Load model weights."""
        ...

    @abstractmethod
    def analyze(
        self,
        frames: List[np.ndarray],
        timestamps: Optional[List[float]] = None,
    ) -> List[TemporalWindow]:
        """
        Analyze a sequence of frames for temporal anomalies.

        Args:
            frames: List of BGR frames.
            timestamps: Optional timestamps for each frame.

        Returns:
            List of TemporalWindow with anomaly scores.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class HighAccuracyDetector(ABC):
    """Interface for high-accuracy object detection (e.g. RT-DETRv4-L)."""

    @abstractmethod
    def load(self, device: str = "cpu") -> None:
        ...

    @abstractmethod
    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.3,
    ) -> List[ObjectDetection]:
        """High-accuracy object detection for verification."""
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class PoseVerifier(ABC):
    """Interface for pose estimation models (e.g. ViTPose++-L)."""

    @abstractmethod
    def load(self, device: str = "cpu") -> None:
        ...

    @abstractmethod
    def predict(
        self,
        image: np.ndarray,
        bbox: Optional[List[int]] = None,
    ) -> PoseEvidence:
        """
        Run pose estimation on an image.

        Args:
            image: BGR image.
            bbox: Optional bounding box to focus on [x1, y1, x2, y2].

        Returns:
            PoseEvidence with head direction, torso rotation, etc.
            Missing landmarks are reported as UNKNOWN, NOT as suspicious.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """
    Singleton registry for all loaded models.

    Models are loaded once and cached. This avoids repeated model loading
    and ensures GPU memory is managed properly.
    """

    _instance: Optional[ModelRegistry] = None

    def __init__(self) -> None:
        self._detectors: Dict[str, ObjectDetector] = {}
        self._temporal_verifiers: Dict[str, TemporalVerifier] = {}
        self._high_accuracy_detectors: Dict[str, HighAccuracyDetector] = {}
        self._pose_verifiers: Dict[str, PoseVerifier] = {}
        self._device: str = "cpu"

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (useful for testing)."""
        cls._instance = None

    def set_device(self, device: str) -> None:
        self._device = device

    # --- Registration ---

    def register_detector(self, name: str, detector: ObjectDetector) -> None:
        self._detectors[name] = detector
        logger.info(f"Registered detector: {name} ({detector.model_name})")

    def register_temporal_verifier(self, name: str, verifier: TemporalVerifier) -> None:
        self._temporal_verifiers[name] = verifier
        logger.info(f"Registered temporal verifier: {name} ({verifier.model_name})")

    def register_high_accuracy_detector(self, name: str, detector: HighAccuracyDetector) -> None:
        self._high_accuracy_detectors[name] = detector
        logger.info(f"Registered high-accuracy detector: {name} ({detector.model_name})")

    def register_pose_verifier(self, name: str, verifier: PoseVerifier) -> None:
        self._pose_verifiers[name] = verifier
        logger.info(f"Registered pose verifier: {name} ({verifier.model_name})")

    # --- Retrieval ---

    def get_detector(self, name: str = "live") -> ObjectDetector:
        if name not in self._detectors:
            raise KeyError(f"Detector '{name}' not registered. Available: {list(self._detectors.keys())}")
        return self._detectors[name]

    def get_temporal_verifier(self, name: str = "videomae") -> TemporalVerifier:
        if name not in self._temporal_verifiers:
            raise KeyError(f"Temporal verifier '{name}' not registered.")
        return self._temporal_verifiers[name]

    def get_high_accuracy_detector(self, name: str = "rtdetr") -> HighAccuracyDetector:
        if name not in self._high_accuracy_detectors:
            raise KeyError(f"High-accuracy detector '{name}' not registered.")
        return self._high_accuracy_detectors[name]

    def get_pose_verifier(self, name: str = "vitpose") -> PoseVerifier:
        if name not in self._pose_verifiers:
            raise KeyError(f"Pose verifier '{name}' not registered.")
        return self._pose_verifiers[name]

    # --- Status ---

    def get_status(self) -> Dict[str, Any]:
        """Get status of all registered models."""
        status = {}
        for name, model in self._detectors.items():
            status[f"detector.{name}"] = {
                "model": model.model_name,
                "loaded": model.is_loaded(),
            }
        for name, model in self._temporal_verifiers.items():
            status[f"temporal.{name}"] = {
                "model": model.model_name,
                "loaded": model.is_loaded(),
            }
        for name, model in self._high_accuracy_detectors.items():
            status[f"high_accuracy.{name}"] = {
                "model": model.model_name,
                "loaded": model.is_loaded(),
            }
        for name, model in self._pose_verifiers.items():
            status[f"pose.{name}"] = {
                "model": model.model_name,
                "loaded": model.is_loaded(),
            }
        return status

    def load_all(self, device: Optional[str] = None) -> None:
        """Load all registered models."""
        dev = device or self._device
        for name, model in self._detectors.items():
            if not model.is_loaded():
                logger.info(f"Loading detector: {name}")
                model.load(dev)
        for name, model in self._temporal_verifiers.items():
            if not model.is_loaded():
                logger.info(f"Loading temporal verifier: {name}")
                model.load(dev)
        for name, model in self._high_accuracy_detectors.items():
            if not model.is_loaded():
                logger.info(f"Loading high-accuracy detector: {name}")
                model.load(dev)
        for name, model in self._pose_verifiers.items():
            if not model.is_loaded():
                logger.info(f"Loading pose verifier: {name}")
                model.load(dev)
