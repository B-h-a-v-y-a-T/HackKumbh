"""
ViTPose++-L Pose Verifier — Retrospective pipeline.

Provides pose-based evidence (head direction, torso rotation, hand position).
Missing landmarks are reported as UNKNOWN, never as suspicious.
Does NOT perform identity recognition.
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional

import numpy as np

from app.models.base import PoseVerifier
from app.schemas.common import PoseEvidence

logger = logging.getLogger(__name__)

HEAD_DIRECTIONS = ["FORWARD", "LEFT", "RIGHT", "DOWN", "UP", "BEHIND", "UNKNOWN"]


class ViTPoseVerifier(PoseVerifier):
    """
    Real ViTPose++ implementation using HuggingFace transformers.

    Extracts pose keypoints and computes pose-based evidence.
    Missing landmarks → UNKNOWN, NOT suspicious.
    """

    def __init__(self, model_name: str = "nielsr/vitpose-base") -> None:
        self._model_name_id = model_name
        self._model = None
        self._processor = None

    def load(self, device: str = "cpu") -> None:
        try:
            from transformers import AutoProcessor, VitPoseForPoseEstimation
            logger.info(f"Loading ViTPose from {self._model_name_id} on {device}")
            self._processor = AutoProcessor.from_pretrained(self._model_name_id)
            self._model = VitPoseForPoseEstimation.from_pretrained(self._model_name_id)
            self._model.to(device)
            self._model.eval()
            self._device = device
            logger.info("ViTPose loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ViTPose: {e}")
            raise

    def predict(
        self,
        image: np.ndarray,
        bbox: Optional[List[int]] = None,
    ) -> PoseEvidence:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        import torch
        from PIL import Image

        # Convert BGR to RGB
        rgb = image[:, :, ::-1]
        pil_image = Image.fromarray(rgb)

        # Prepare bounding box for the processor
        person_bbox = bbox if bbox else [0, 0, image.shape[1], image.shape[0]]
        boxes = [[[person_bbox]]]

        try:
            inputs = self._processor(pil_image, boxes=boxes, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)

            # Extract keypoints
            keypoints = outputs.pose_estimation_results
            if keypoints is not None and len(keypoints) > 0:
                kps = keypoints[0]  # First person
                # Estimate head direction from nose/eye keypoints
                head_dir = self._estimate_head_direction(kps)
                torso_rot = self._estimate_torso_rotation(kps)
                hand_vis = self._estimate_hand_visibility(kps)
                pose_conf = float(torch.mean(kps[:, 2]).cpu()) if kps.dim() > 1 else 0.5

                return PoseEvidence(
                    head_confidence=min(1.0, max(0.0, pose_conf)),
                    head_direction=head_dir,
                    torso_rotation=torso_rot,
                    hand_visibility=hand_vis,
                    pose_confidence=min(1.0, max(0.0, pose_conf)),
                )
            else:
                return PoseEvidence(
                    head_confidence=0.0,
                    head_direction="UNKNOWN",
                    reason="NO_KEYPOINTS_DETECTED",
                )
        except Exception as e:
            logger.warning(f"Pose estimation failed: {e}")
            return PoseEvidence(
                head_confidence=0.0,
                head_direction="UNKNOWN",
                reason=f"ESTIMATION_FAILED: {str(e)[:100]}",
            )

    def _estimate_head_direction(self, keypoints) -> str:
        """Estimate head direction from keypoints. Returns UNKNOWN if insufficient data."""
        try:
            # COCO keypoint order: nose=0, left_eye=1, right_eye=2
            nose = keypoints[0]
            left_eye = keypoints[1]
            right_eye = keypoints[2]

            if nose[2] < 0.3 or left_eye[2] < 0.3 or right_eye[2] < 0.3:
                return "UNKNOWN"

            eye_center_x = (left_eye[0] + right_eye[0]) / 2
            diff = float(nose[0] - eye_center_x)

            if abs(diff) < 5:
                return "FORWARD"
            elif diff > 15:
                return "RIGHT"
            elif diff < -15:
                return "LEFT"
            else:
                return "FORWARD"
        except (IndexError, RuntimeError):
            return "UNKNOWN"

    def _estimate_torso_rotation(self, keypoints) -> float:
        """Estimate torso rotation in degrees."""
        try:
            # COCO: left_shoulder=5, right_shoulder=6
            ls = keypoints[5]
            rs = keypoints[6]
            if ls[2] < 0.3 or rs[2] < 0.3:
                return 0.0
            dx = float(rs[0] - ls[0])
            dy = float(rs[1] - ls[1])
            import math
            angle = math.degrees(math.atan2(dy, dx))
            return round(angle, 2)
        except (IndexError, RuntimeError):
            return 0.0

    def _estimate_hand_visibility(self, keypoints) -> float:
        """Estimate hand visibility from wrist keypoints."""
        try:
            # COCO: left_wrist=9, right_wrist=10
            lw = keypoints[9]
            rw = keypoints[10]
            vis = (float(lw[2]) + float(rw[2])) / 2
            return min(1.0, max(0.0, vis))
        except (IndexError, RuntimeError):
            return 0.0

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return f"ViTPose++ ({self._model_name_id})"


class MockViTPoseVerifier(PoseVerifier):
    """Mock ViTPose++ for development without GPU."""

    def __init__(self) -> None:
        self._loaded = False
        self._rng = random.Random(789)

    def load(self, device: str = "cpu") -> None:
        logger.info("Loading MockViTPoseVerifier (no GPU required)")
        self._loaded = True

    def predict(
        self,
        image: np.ndarray,
        bbox: Optional[List[int]] = None,
    ) -> PoseEvidence:
        if not self._loaded:
            raise RuntimeError("Mock model not loaded.")

        # Generate realistic pose evidence
        head_conf = round(self._rng.uniform(0.5, 0.98), 4)
        pose_conf = round(self._rng.uniform(0.6, 0.95), 4)

        # Simulate low visibility sometimes
        if self._rng.random() < 0.15:
            return PoseEvidence(
                head_confidence=0.0,
                head_direction="UNKNOWN",
                hand_visibility=round(self._rng.uniform(0.0, 0.3), 4),
                pose_confidence=round(self._rng.uniform(0.1, 0.3), 4),
                reason="LOW_VISIBILITY",
            )

        head_dir = self._rng.choice(HEAD_DIRECTIONS[:6])  # Exclude UNKNOWN for normal
        torso_rot = round(self._rng.uniform(-30, 30), 2)
        hand_vis = round(self._rng.uniform(0.5, 1.0), 4)

        return PoseEvidence(
            head_confidence=head_conf,
            head_direction=head_dir,
            torso_rotation=torso_rot,
            hand_visibility=hand_vis,
            pose_confidence=pose_conf,
        )

    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return "MockViTPose++ (no GPU)"
