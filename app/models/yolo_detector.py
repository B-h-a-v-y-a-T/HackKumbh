"""
YOLO26-S Object Detector — Live pipeline detector.

Uses Ultralytics YOLO26-S for fast, small-object-aware detection.
Supports COCO-pretrained weights and custom fine-tuned weights.
Includes a full mock implementation for development without GPU.
"""

from __future__ import annotations

import logging
import random
import time
from typing import List, Optional

import numpy as np

from app.models.base import ObjectDetector
from app.schemas.common import ObjectDetection

logger = logging.getLogger(__name__)

# COCO class ID for cell_phone = 67
COCO_PHONE_CLASS_ID = 67
COCO_PHONE_CLASS_NAME = "cell phone"

# Class-specific confidence thresholds
PHONE_CONFIDENCE_THRESHOLD = 0.60
CHIT_CONFIDENCE_THRESHOLD = 0.50
PROHIBITED_OBJECT_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_CONFIDENCE_THRESHOLD = 0.50
MIN_OBJECT_SIZE_PX = 12

# Standard semantic class names
CLASS_MOBILE_PHONE = "mobile_phone"
CLASS_PAPER_CHIT = "paper_chit"
CLASS_PROHIBITED_OBJECT = "prohibited_object"
CLASS_UNKNOWN_OBJECT = "unknown_object"
CLASS_LOW_CONFIDENCE_OBJECT = "low_confidence_object"

# Mapping from COCO classes to our exam-specific classes
COCO_TO_EXAM_CLASS = {
    "cell phone": CLASS_MOBILE_PHONE,
    "book": CLASS_PAPER_CHIT,
    "remote": CLASS_PROHIBITED_OBJECT,
    "scissors": CLASS_PROHIBITED_OBJECT,
}

# Our custom exam classes
EXAM_CLASSES = [CLASS_MOBILE_PHONE, CLASS_PAPER_CHIT, CLASS_PROHIBITED_OBJECT]

CLASS_THRESHOLDS = {
    CLASS_MOBILE_PHONE: PHONE_CONFIDENCE_THRESHOLD,
    CLASS_PAPER_CHIT: CHIT_CONFIDENCE_THRESHOLD,
    CLASS_PROHIBITED_OBJECT: PROHIBITED_OBJECT_CONFIDENCE_THRESHOLD,
    CLASS_UNKNOWN_OBJECT: 0.40,
    CLASS_LOW_CONFIDENCE_OBJECT: 0.30,
}


class YOLO26SDetector(ObjectDetector):
    """
    Real YOLO26-S detector using Ultralytics.

    When custom weights are provided, uses the fine-tuned model with
    exam-specific classes. Otherwise, maps COCO classes strictly and safely.
    Logs model.names on load for auditability.
    """

    def __init__(self, weights_path: Optional[str] = None) -> None:
        self._weights_path = weights_path or "yolo26s.pt"
        self._model = None
        self._is_custom = weights_path is not None and "yolo26" not in weights_path.lower()
        self._class_names_map = {}

    def load(self, device: str = "cpu") -> None:
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLO26-S from {self._weights_path} on {device}")
            self._model = YOLO(self._weights_path)
            self._model.to(device)

            # Audit and log model.names
            if hasattr(self._model, "names") and self._model.names:
                self._class_names_map = dict(self._model.names)
                logger.info(f"Loaded YOLO model.names audit: {self._class_names_map}")
            else:
                logger.info("YOLO model has no explicit names attribute; using standard registry")

            logger.info("YOLO26-S loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO26-S: {e}")
            raise

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: Optional[float] = None,
        classes: Optional[List[str]] = None,
        trigger: Optional[str] = None,
    ) -> List[ObjectDetection]:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        min_conf = confidence_threshold if confidence_threshold is not None else 0.25
        results = self._model(image, conf=min_conf, verbose=False)
        detections: List[ObjectDetection] = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = [int(x) for x in box.xyxy[0].tolist()]

                # Validate minimum object size to reject random noise
                bw = bbox[2] - bbox[0]
                bh = bbox[3] - bbox[1]
                if bw < MIN_OBJECT_SIZE_PX or bh < MIN_OBJECT_SIZE_PX:
                    continue

                raw_class_name = result.names.get(cls_id, f"class_{cls_id}").lower().strip()

                # Map raw/COCO class to canonical exam class
                if self._is_custom:
                    class_name = raw_class_name
                else:
                    class_name = COCO_TO_EXAM_CLASS.get(raw_class_name, raw_class_name)

                # Check class-specific threshold
                target_thresh = CLASS_THRESHOLDS.get(class_name, DEFAULT_CONFIDENCE_THRESHOLD)
                if conf < target_thresh:
                    # Do not force into phone — label as low confidence or unknown if borderline
                    if conf >= 0.30:
                        class_name = CLASS_LOW_CONFIDENCE_OBJECT
                    else:
                        continue

                # Filter by requested classes
                if classes and class_name not in classes:
                    continue

                # Only return exam-relevant or unknown classes
                if class_name in EXAM_CLASSES or class_name in (CLASS_UNKNOWN_OBJECT, CLASS_LOW_CONFIDENCE_OBJECT) or self._is_custom:
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
        return f"YOLO26-S ({self._weights_path})"


class MockYOLO26SDetector(ObjectDetector):
    """
    Mock YOLO26-S detector for development/testing without GPU.

    Produces accurate, class-consistent detections without biased false phone labeling.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._rng = random.Random(42)

    def load(self, device: str = "cpu") -> None:
        logger.info("Loading MockYOLO26SDetector (no GPU required)")
        self._loaded = True

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: Optional[float] = None,
        classes: Optional[List[str]] = None,
        trigger: Optional[str] = None,
    ) -> List[ObjectDetection]:
        if not self._loaded:
            raise RuntimeError("Mock model not loaded. Call load() first.")

        detections: List[ObjectDetection] = []
        h, w = image.shape[:2]

        # Trigger-informed realistic simulation
        # Paper/desk reach triggers generate paper_chit; phone triggers generate mobile_phone
        phone_prob = 0.05
        chit_prob = 0.05

        if trigger in ("HAND_OUTSIDE_DESK", "HAND_UNDER_DESK", "OBJECT_ALREADY_DETECTED"):
            chit_prob = 0.85
            phone_prob = 0.10
        elif trigger in ("UNUSUAL_HAND_MOVEMENT", "MANUAL_REVIEW_TRIGGER", "NEIGHBOUR_INTERACTION"):
            chit_prob = 0.70
            phone_prob = 0.15

        # Simulate paper chit detection
        if self._rng.random() < chit_prob:
            conf = round(self._rng.uniform(0.55, 0.88), 4)
            thresh = confidence_threshold if confidence_threshold is not None else CHIT_CONFIDENCE_THRESHOLD
            if conf >= thresh:
                cx = self._rng.randint(w // 4, 3 * w // 4)
                cy = self._rng.randint(h // 4, 3 * h // 4)
                bw = self._rng.randint(24, min(65, w // 4))
                bh = self._rng.randint(18, min(45, h // 4))
                detections.append(ObjectDetection(
                    object_class=CLASS_PAPER_CHIT,
                    confidence=conf,
                    bbox=[max(0, cx - bw // 2), max(0, cy - bh // 2),
                          min(w, cx + bw // 2), min(h, cy + bh // 2)],
                ))

        # Simulate phone detection (when phone is explicitly involved)
        if self._rng.random() < phone_prob:
            conf = round(self._rng.uniform(0.62, 0.94), 4)
            thresh = confidence_threshold if confidence_threshold is not None else PHONE_CONFIDENCE_THRESHOLD
            if conf >= thresh:
                cx = self._rng.randint(w // 4, 3 * w // 4)
                cy = self._rng.randint(h // 3, 2 * h // 3)
                bw = self._rng.randint(35, min(80, w // 3))
                bh = self._rng.randint(55, min(120, h // 3))
                detections.append(ObjectDetection(
                    object_class=CLASS_MOBILE_PHONE,
                    confidence=conf,
                    bbox=[max(0, cx - bw // 2), max(0, cy - bh // 2),
                          min(w, cx + bw // 2), min(h, cy + bh // 2)],
                ))

        # Filter by requested classes
        if classes:
            detections = [d for d in detections if d.object_class in classes]

        return detections

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return "MockYOLO26-S (no GPU)"
