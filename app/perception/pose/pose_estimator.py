"""
Pose estimator for detailed 133-keypoint wholebody pose (hands, face).

In the fast path, YOLO provides 17 body keypoints. This module is the
OPTIONAL detailed path that runs rtmlib's RTMPose DIRECTLY (bypassing
rtmlib's built-in YOLOX detector) to get 133-keypoint wholebody output
including hands and face.

Only runs every N frames to avoid the performance penalty.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.perception.core.constants import TOTAL_KEYPOINTS
from app.perception.core.data_models import BoundingBox, KeypointSet

logger = logging.getLogger(__name__)


class PoseEstimator:
    """
    Optional detailed pose estimator using rtmlib RTMPose.

    Bypasses rtmlib's internal YOLOX detector — we pass YOLO bboxes
    directly to RTMPose, eliminating the redundant detection step.

    Frame skipping: only runs full 133-keypoint estimation every
    ``detail_interval`` frames, caching results between runs.

    Args:
        mode: rtmlib preset ("lightweight", "balanced", "performance").
        backend: "onnxruntime" or "opencv".
        device: "cpu" or "cuda".
        detail_interval: Run detailed pose every N frames (1 = every frame).
    """

    # RTMPose model URLs (pose model ONLY — no detector)
    POSE_MODELS = {
        "lightweight": {
            "url": "https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.zip",
            "input_size": (192, 256),
        },
        "balanced": {
            "url": "https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/rtmw-dw-x-l_simcc-cocktail14_270e-256x192_20231122.zip",
            "input_size": (192, 256),
        },
        "performance": {
            "url": "https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/rtmw-dw-x-l_simcc-cocktail14_270e-384x288_20231122.zip",
            "input_size": (288, 384),
        },
    }

    def __init__(
        self,
        mode: str = "lightweight",
        backend: str = "onnxruntime",
        device: str = "cpu",
        detail_interval: int = 5,
    ):
        self.mode = mode
        self.backend = backend
        self.device = device
        self.detail_interval = max(1, detail_interval)
        self._pose_model = None
        self._frame_count = 0
        self._cache: Dict[int, KeypointSet] = {}  # track_id → last detailed kps

    def _load_model(self):
        """Lazy-load only the RTMPose model (no YOLOX)."""
        try:
            from rtmlib import RTMPose

            model_cfg = self.POSE_MODELS.get(self.mode, self.POSE_MODELS["lightweight"])

            logger.info(
                "Loading RTMPose estimator (mode=%s, backend=%s, device=%s)",
                self.mode, self.backend, self.device,
            )

            self._pose_model = RTMPose(
                model_cfg["url"],
                model_input_size=model_cfg["input_size"],
                backend=self.backend,
                device=self.device,
            )

            logger.info("RTMPose estimator loaded.")
        except ImportError:
            logger.error("rtmlib not installed. Install with: pip install rtmlib")
            raise

    def should_run_this_frame(self) -> bool:
        """Check if detailed pose estimation should run on this frame."""
        self._frame_count += 1
        return (self._frame_count % self.detail_interval) == 1 or self.detail_interval == 1

    def estimate(
        self,
        frame: np.ndarray,
        bboxes: List[BoundingBox],
        track_ids: Optional[List[int]] = None,
    ) -> List[KeypointSet]:
        """
        Run 133-keypoint wholebody pose on detected persons.

        Passes YOLO bboxes directly to RTMPose — no redundant detection.

        Args:
            frame: BGR image.
            bboxes: Person bounding boxes from YOLO.
            track_ids: Optional track IDs for caching.

        Returns:
            List of KeypointSet (one per bbox).
        """
        if self._pose_model is None:
            self._load_model()

        if not bboxes:
            return []

        # Convert bboxes to format expected by RTMPose: list of [x1, y1, x2, y2]
        bbox_list = [[b.x1, b.y1, b.x2, b.y2] for b in bboxes]
        bbox_array = np.array(bbox_list, dtype=np.float32)

        try:
            keypoints, scores = self._pose_model(frame, bboxes=bbox_array)
        except Exception as e:
            logger.warning("RTMPose inference failed: %s", e)
            return [KeypointSet.empty() for _ in bboxes]

        results: List[KeypointSet] = []
        for i in range(len(bboxes)):
            if i < len(keypoints):
                kp = keypoints[i]   # (133, 2) or similar
                sc = scores[i]      # (133,) or similar
                n_kp = min(len(sc), TOTAL_KEYPOINTS)

                kps = KeypointSet.empty()
                kps.xy[:n_kp] = kp[:n_kp].astype(np.float32)
                kps.confidence[:n_kp] = sc[:n_kp].astype(np.float32)
                results.append(kps)

                # Cache by track ID
                if track_ids and i < len(track_ids):
                    self._cache[track_ids[i]] = kps
            else:
                results.append(KeypointSet.empty())

        return results

    def get_cached(self, track_id: int) -> Optional[KeypointSet]:
        """Get the last detailed keypoints for a track (from cache)."""
        return self._cache.get(track_id)

    def merge_yolo_with_detail(
        self,
        yolo_kps: KeypointSet,
        detail_kps: Optional[KeypointSet],
    ) -> KeypointSet:
        """
        Merge YOLO 17-point body keypoints with cached detailed hand/face keypoints.

        Uses YOLO body keypoints (always fresh) and detail hand/face keypoints
        (from cache) to produce a combined result.

        Args:
            yolo_kps: Fresh 17-point body keypoints from YOLO.
            detail_kps: Cached 133-point keypoints from RTMPose (may be None).

        Returns:
            Merged KeypointSet.
        """
        if detail_kps is None:
            return yolo_kps

        # Start with YOLO body keypoints (fresh, always current)
        merged = KeypointSet.empty()
        merged.xy[:17] = yolo_kps.xy[:17]
        merged.confidence[:17] = yolo_kps.confidence[:17]

        # Add hand/face/feet from cached detail (indices 17+)
        merged.xy[17:] = detail_kps.xy[17:]
        merged.confidence[17:] = detail_kps.confidence[17:]

        return merged

    def clear_cache(self):
        """Clear the keypoint cache."""
        self._cache.clear()

    @property
    def is_loaded(self) -> bool:
        return self._pose_model is not None
