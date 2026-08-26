"""
SixDRepNet Head Pose Estimation Model.

Encapsulates the pretrained SixDRepNet (RepVGG backbone) for unconstrained 3D
head pose estimation (Yaw, Pitch, Roll). Operates with batched GPU inference,
FP16 half-precision, and robust fallback for edge/occluded crops.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms

try:
    from sixdrepnet.model import SixDRepNet
    import sixdrepnet.utils as sixd_utils
    HAS_SIXDREPNET = True
except ImportError:
    HAS_SIXDREPNET = False

from app.config import get_settings

logger = logging.getLogger(__name__)

# ImageNet normalization constants
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)


class SixDRepNetEstimator:
    """
    Batched 3D head pose estimator using pretrained SixDRepNet.
    
    Provides high-throughput batched inference on CUDA/FP16.
    """

    _instance: Optional["SixDRepNetEstimator"] = None

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        device: str = "auto",
        use_fp16: bool = True,
    ):
        settings = get_settings()
        self.checkpoint_path = checkpoint_path or settings.head_pose_checkpoint
        self.use_fp16 = use_fp16 and (torch.cuda.is_available() if device == "auto" or "cuda" in device else False)

        # Resolve device
        if device == "auto":
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model: Optional[nn.Module] = None
        self._is_ready = False

        self._initialize_model()

    @classmethod
    def get_instance(cls) -> "SixDRepNetEstimator":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_model(self):
        """Load model architecture and weights."""
        if not HAS_SIXDREPNET:
            logger.warning("SixDRepNet package not available; fallback to heuristic head pose.")
            return

        try:
            # SixDRepNet RepVGG backbone architecture
            self.model = SixDRepNet(
                backbone_name="RepVGG-B1g2",
                backbone_file="",
                deploy=True,
                pretrained=False,
            )

            # Ensure weights exist locally
            ckpt_path = Path(self.checkpoint_path)
            if not ckpt_path.exists():
                logger.info("Downloading SixDRepNet weights to %s...", ckpt_path)
                ckpt_path.parent.mkdir(parents=True, exist_ok=True)
                from torch.hub import load_state_dict_from_url
                state = load_state_dict_from_url(
                    "https://cloud.ovgu.de/s/Q67RnLDy6JKLRWm/download/6DRepNet_300W_LP_AFLW2000.pth",
                    model_dir=str(ckpt_path.parent),
                    progress=False,
                )
                torch.save(state, str(ckpt_path))
            else:
                state = torch.load(str(ckpt_path), map_location="cpu")

            self.model.load_state_dict(state)
            self.model.to(self.device)

            if self.use_fp16 and self.device.type == "cuda":
                self.model.half()

            self.model.eval()
            self._is_ready = True
            logger.info(
                "SixDRepNet loaded successfully on %s (fp16=%s)",
                self.device,
                self.use_fp16,
            )

            # Warmup pass
            dummy = torch.zeros(1, 3, 224, 224, device=self.device)
            if self.use_fp16 and self.device.type == "cuda":
                dummy = dummy.half()
            with torch.inference_mode():
                _ = self.model(dummy)

        except Exception as e:
            logger.error("Failed to load SixDRepNet model: %s", e)
            self.model = None
            self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready and self.model is not None

    def preprocess_crop(self, crop_bgr: np.ndarray) -> np.ndarray:
        """
        Preprocess a single face crop for SixDRepNet (224x224 RGB normalized).
        
        Args:
            crop_bgr: (H, W, 3) BGR image.
            
        Returns:
            (3, 224, 224) float32 array in CHW order.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return np.zeros((3, 224, 224), dtype=np.float32)

        # Convert to RGB
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        
        # Resize directly to 224x224 with high quality interpolation
        if crop_rgb.shape[0] != 224 or crop_rgb.shape[1] != 224:
            crop_rgb = cv2.resize(crop_rgb, (224, 224), interpolation=cv2.INTER_LINEAR)

        # Normalize with ImageNet mean and std
        norm_img = ((crop_rgb.astype(np.float32) / 255.0) - IMAGENET_MEAN) / IMAGENET_STD
        
        # HWC -> CHW
        return norm_img.transpose(2, 0, 1)

    def predict_batch(
        self,
        face_crops: List[Optional[np.ndarray]],
        return_matrices: bool = False,
    ):
        """
        Runs batched inference on a list of facial crop images.
            
        Returns:
            If return_matrices=False:
                Tuple of (pitch_deg, yaw_deg, roll_deg) as 1D float numpy arrays.
                Positive pitch = Up, Negative pitch = Down.
                Positive yaw = Right, Negative yaw = Left.
            If return_matrices=True:
                Tuple of (pitch_deg, yaw_deg, roll_deg, rotation_matrices)
                where rotation_matrices is a list of (3, 3) ndarray or None.
        """
        n_crops = len(face_crops)
        if n_crops == 0 or not self.is_ready:
            empty_p = np.zeros(n_crops, dtype=np.float32)
            empty_y = np.zeros(n_crops, dtype=np.float32)
            empty_r = np.zeros(n_crops, dtype=np.float32)
            if return_matrices:
                return empty_p, empty_y, empty_r, [None] * n_crops
            return empty_p, empty_y, empty_r

        # Preprocess all valid crops
        tensor_list = []
        valid_indices = []
        for i, crop in enumerate(face_crops):
            if crop is not None and crop.shape[0] >= 16 and crop.shape[1] >= 16:
                chw = self.preprocess_crop(crop)
                tensor_list.append(torch.from_numpy(chw))
                valid_indices.append(i)

        if not tensor_list:
            empty_p = np.zeros(n_crops, dtype=np.float32)
            empty_y = np.zeros(n_crops, dtype=np.float32)
            empty_r = np.zeros(n_crops, dtype=np.float32)
            if return_matrices:
                return empty_p, empty_y, empty_r, [None] * n_crops
            return empty_p, empty_y, empty_r

        batch_tensor = torch.stack(tensor_list).to(self.device)
        if self.use_fp16 and self.device.type == "cuda":
            batch_tensor = batch_tensor.half()

        with torch.inference_mode():
            rot_matrices = self.model(batch_tensor)  # (B, 3, 3)
            euler = sixd_utils.compute_euler_angles_from_rotation_matrices(rot_matrices) * (180.0 / np.pi)

        euler_cpu = euler.float().cpu().numpy()
        rot_matrices_cpu = rot_matrices.float().cpu().numpy()
        pred_pitch = euler_cpu[:, 0]
        # In 300W-LP dataset convention, positive yaw is subject-right (viewer-left).
        # We negate yaw so that positive yaw corresponds to viewer/image-right (+X)
        # and negative yaw corresponds to viewer/image-left (-X).
        pred_yaw = -euler_cpu[:, 1]
        pred_roll = euler_cpu[:, 2]

        out_pitch = np.zeros(n_crops, dtype=np.float32)
        out_yaw = np.zeros(n_crops, dtype=np.float32)
        out_roll = np.zeros(n_crops, dtype=np.float32)
        out_matrices: List[Optional[np.ndarray]] = [None] * n_crops

        for out_idx, orig_idx in enumerate(valid_indices):
            out_pitch[orig_idx] = float(pred_pitch[out_idx])
            out_yaw[orig_idx] = float(pred_yaw[out_idx])
            out_roll[orig_idx] = float(pred_roll[out_idx])
            out_matrices[orig_idx] = rot_matrices_cpu[out_idx]

        if return_matrices:
            return out_pitch, out_yaw, out_roll, out_matrices
        return out_pitch, out_yaw, out_roll
