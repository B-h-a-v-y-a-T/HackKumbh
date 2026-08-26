"""
Person detection with integrated pose estimation and tracking.

Uses YOLO11s-pose to get detection + 17 body keypoints + ByteTrack tracking
in a SINGLE forward pass. This is the performance-critical fast path.

Replaces the old architecture that ran 3 separate models.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.perception.core.data_models import BoundingBox, Detection, KeypointSet

logger = logging.getLogger(__name__)


class PersonDetector:
    """
    YOLO-based person detector with integrated pose estimation and tracking.

    Uses yolo11s-pose.pt which outputs:
    - Person bounding boxes
    - 17 COCO body keypoints per person
    - ByteTrack track IDs (when using .track())

    All in a single forward pass (~30ms on CPU).

    Args:
        model_name: YOLO model filename (default: yolo11s-pose.pt).
        confidence: Min detection confidence.
        device: "auto", "cpu", or "cuda:0".
        imgsz: Input image size for YOLO.
        half: Use FP16 inference (GPU only).
    """

    def __init__(
        self,
        model_name: str = "yolo11s-pose.pt",
        confidence: float = 0.5,
        device: str = "auto",
        imgsz: int = 640,
        half: bool = False,
    ):
        self.model_name = model_name
        self.confidence = confidence
        if device == "auto" or device == "cuda":
            try:
                import torch
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            except Exception:
                self.device = "cpu"
        else:
            self.device = device
        self.imgsz = imgsz if imgsz != 640 else (640 if "cuda" in str(self.device) else 480)
        try:
            import torch
            if not str(self.device).startswith("cuda"):
                torch.set_num_threads(min(4, os.cpu_count() or 4))
        except Exception:
            pass
        if device == "auto" or device == "cuda" or str(self.device).startswith("cuda"):
            try:
                import torch
                if torch.cuda.is_available():
                    torch.backends.cudnn.benchmark = True
                    half = True
            except Exception:
                pass
        self.half = half
        self._model = None

    def _load_model(self):
        """Lazy-load the YOLO model on first use."""
        try:
            from ultralytics import YOLO

            logger.info(
                "Loading person detector: %s (device=%s)",
                self.model_name, self.device,
            )
            self._model = YOLO(self.model_name)
            try:
                self._model.to(self.device)
            except Exception:
                pass

            # Warm up with a dummy frame
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(
                dummy, verbose=False, device=self.device, imgsz=self.imgsz,
            )
            logger.info("Person detector loaded and warmed up on %s.", self.device)
        except ImportError:
            logger.error(
                "ultralytics not installed. Install with: pip install ultralytics"
            )
            raise
        except Exception as e:
            logger.error("Failed to load YOLO model '%s': %s",
                         self.model_name, e)
            raise

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect persons in a frame (detection only, no pose or tracking).

        Args:
            frame: BGR image (H, W, 3) uint8.

        Returns:
            List of Detection objects with bounding boxes.
        """
        if self._model is None:
            self._load_model()

        device = self.device
        predict_kwargs = {
            "classes": [0],
            "conf": self.confidence,
            "device": device,
            "verbose": False,
            "imgsz": self.imgsz,
        }

        results = self._model.predict(frame, **predict_kwargs)

        detections: List[Detection] = []
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                for i in range(len(boxes)):
                    bbox = BoundingBox(
                        x1=float(boxes[i, 0]),
                        y1=float(boxes[i, 1]),
                        x2=float(boxes[i, 2]),
                        y2=float(boxes[i, 3]),
                        confidence=float(confs[i]),
                    )
                    detections.append(Detection(bbox=bbox))

        return detections

    def detect_with_tracking(
        self,
        frame: np.ndarray,
        tracker_config: str = "bytetrack.yaml",
        persist: bool = True,
    ) -> Tuple[List[Detection], List[int]]:
        """
        Detect persons AND run built-in tracking in one pass.

        Args:
            frame: BGR image.
            tracker_config: Tracker YAML config filename.
            persist: Keep tracks across calls.

        Returns:
            (detections, track_ids) — parallel lists.
        """
        if self._model is None:
            self._load_model()

        device = self.device
        track_kwargs = {
            "classes": [0],
            "conf": self.confidence,
            "device": device,
            "verbose": False,
            "imgsz": self.imgsz,
            "tracker": tracker_config,
            "persist": persist,
        }
        if self.half:
            track_kwargs["half"] = True

        results = self._model.track(frame, **track_kwargs)

        detections: List[Detection] = []
        track_ids: List[int] = []

        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()

                ids = None
                if result.boxes.id is not None:
                    ids = result.boxes.id.int().cpu().numpy()

                for i in range(len(boxes)):
                    bbox = BoundingBox(
                        x1=float(boxes[i, 0]),
                        y1=float(boxes[i, 1]),
                        x2=float(boxes[i, 2]),
                        y2=float(boxes[i, 3]),
                        confidence=float(confs[i]),
                    )
                    detections.append(Detection(bbox=bbox))
                    track_ids.append(int(ids[i]) if ids is not None else -1)

        return detections, track_ids

    def detect_pose_track(
        self,
        frame: np.ndarray,
        tracker_config: str = "bytetrack.yaml",
        persist: bool = True,
    ) -> Tuple[List[Detection], List[int], List[KeypointSet]]:
        """
        Detect + track + estimate 17 body keypoints in ONE forward pass.

        This is the primary fast-path method. Uses YOLO pose model to get
        bounding boxes, track IDs, and 17 COCO body keypoints simultaneously.

        Args:
            frame: BGR image (H, W, 3) uint8.
            tracker_config: ByteTrack config filename.
            persist: Keep tracks across calls.

        Returns:
            (detections, track_ids, keypoints) — parallel lists.
            keypoints[i] is a KeypointSet with 17 body keypoints populated.
        """
        if self._model is None:
            self._load_model()

        device = self.device
        track_kwargs = {
            "conf": self.confidence,
            "device": device,
            "verbose": False,
            "imgsz": self.imgsz,
            "tracker": tracker_config,
            "persist": persist,
        }
        if self.half:
            track_kwargs["half"] = True

        results = self._model.track(frame, **track_kwargs)

        detections: List[Detection] = []
        track_ids: List[int] = []
        keypoints_list: List[KeypointSet] = []

        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()

                # Track IDs
                ids = None
                if result.boxes.id is not None:
                    ids = result.boxes.id.int().cpu().numpy()

                # Keypoints from pose model (17 COCO keypoints)
                kps_data = None
                if result.keypoints is not None and result.keypoints.data is not None:
                    kps_data = result.keypoints.data.cpu().numpy()
                    # Shape: (num_persons, 17, 3) where [:, :, 2] is confidence

                for i in range(len(boxes)):
                    # BBox
                    bbox = BoundingBox(
                        x1=float(boxes[i, 0]),
                        y1=float(boxes[i, 1]),
                        x2=float(boxes[i, 2]),
                        y2=float(boxes[i, 3]),
                        confidence=float(confs[i]),
                    )
                    detections.append(Detection(bbox=bbox))

                    # Track ID
                    track_ids.append(int(ids[i]) if ids is not None else -1)

                    # Keypoints → KeypointSet
                    if kps_data is not None and i < len(kps_data):
                        xy = kps_data[i, :, :2].astype(np.float32)   # (17, 2)
                        conf = kps_data[i, :, 2].astype(np.float32)  # (17,)
                        keypoints_list.append(KeypointSet.from_yolo_17(xy, conf))
                    else:
                        keypoints_list.append(KeypointSet.empty())

        return detections, track_ids, keypoints_list

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
