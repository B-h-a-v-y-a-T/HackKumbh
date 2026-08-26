"""
RT-DETR V4-L High-Accuracy Object Detector — Retrospective pipeline.

Used for high-accuracy verification of suspicious temporal windows
identified by VideoMAE V2-L. Confirms or rejects object detections.
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional

import numpy as np

from app.models.base import HighAccuracyDetector
from app.schemas.common import ObjectDetection

logger = logging.getLogger(__name__)


class RTDETRVerifier(HighAccuracyDetector):
    """
    Real RT-DETR implementation using Ultralytics.

    Falls back to RT-DETR-L weights. The interface is ready for
    RT-DETRv4-L weights when publicly available.
    """

    def __init__(self, weights_path: str = "rtdetr-l.pt") -> None:
        self._weights_path = weights_path
        self._model = None

    def load(self, device: str = "cpu") -> None:
        try:
            from ultralytics import RTDETR
            logger.info(f"Loading RT-DETR from {self._weights_path} on {device}")
            self._model = RTDETR(self._weights_path)
            self._model.to(device)
            logger.info("RT-DETR loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load RT-DETR: {e}")
            raise

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.3,
    ) -> List[ObjectDetection]:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        results = self._model(image, conf=confidence_threshold, verbose=False)
        detections = []

        # Map COCO cell phone to our class
        coco_to_exam = {"cell phone": "mobile_phone"}

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = [int(x) for x in box.xyxy[0].tolist()]
                class_name = result.names.get(cls_id, f"class_{cls_id}")
                class_name = coco_to_exam.get(class_name, class_name)

                detections.append(ObjectDetection(
                    object_class=class_name,
                    confidence=round(conf, 4),
                    bbox=bbox,
                ))

        return detections

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return f"RT-DETR-L ({self._weights_path})"


class MockRTDETRVerifier(HighAccuracyDetector):
    """Mock RT-DETR for development without GPU."""

    def __init__(self) -> None:
        self._loaded = False
        self._rng = random.Random(456)

    def load(self, device: str = "cpu") -> None:
        logger.info("Loading MockRTDETRVerifier (no GPU required)")
        self._loaded = True

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.3,
    ) -> List[ObjectDetection]:
        if not self._loaded:
            raise RuntimeError("Mock model not loaded.")

        detections = []
        h, w = image.shape[:2]

        # Higher accuracy detector — produce confident results
        if self._rng.random() < 0.55:
            conf = round(self._rng.uniform(0.75, 0.98), 4)
            if conf >= confidence_threshold:
                cx = self._rng.randint(w // 4, 3 * w // 4)
                cy = self._rng.randint(h // 3, 2 * h // 3)
                detections.append(ObjectDetection(
                    object_class="mobile_phone",
                    confidence=conf,
                    bbox=[max(0, cx - 40), max(0, cy - 60),
                          min(w, cx + 40), min(h, cy + 60)],
                ))

        if self._rng.random() < 0.25:
            conf = round(self._rng.uniform(0.65, 0.95), 4)
            if conf >= confidence_threshold:
                cx = self._rng.randint(w // 4, 3 * w // 4)
                cy = self._rng.randint(h // 4, 3 * h // 4)
                detections.append(ObjectDetection(
                    object_class="paper_chit",
                    confidence=conf,
                    bbox=[max(0, cx - 25), max(0, cy - 15),
                          min(w, cx + 25), min(h, cy + 15)],
                ))

        return detections

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return "MockRT-DETR-L (no GPU)"
