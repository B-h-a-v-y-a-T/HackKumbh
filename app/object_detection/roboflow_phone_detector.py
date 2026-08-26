"""
Roboflow Phone Detector Module — Enhanced Hybrid Roboflow & Local YOLO Detection Engine.

Integrates:
1. Native Roboflow Inference SDK (if available) & Roboflow Hosted REST API
2. High-Performance Local YOLO (Ultralytics yolo11n.pt / yolo11s.pt) targeting cell phone (COCO class 67)
3. Multi-scale full-frame + student desk ROI zoom scanning
4. IoU duplicate suppression and temporal confirmation tracking
5. Non-destructive integration preserving existing pose, tracking, and risk-scoring logic
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import cv2
import numpy as np

from app.models.base import ObjectDetector
from app.schemas.common import ObjectDetection

logger = logging.getLogger(__name__)

# Canonical exam class name
TARGET_CLASS_NAME = "PHONE"

# Recognized phone class variants for robust normalization
TARGET_PHONE_CLASSES: Set[str] = {
    "phone",
    "cell phone",
    "mobile phone",
    "mobile_phone",
    "cellphone",
    "telephone",
    "smartphone",
    "handheld_phone",
}


def compute_iou(box1: List[int], box2: List[int]) -> float:
    """Compute Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / float(union_area)


class TemporalPhoneTracker:
    """
    Temporal confirmation tracker for phone detections.
    
    1 detection -> UNCONFIRMED (or CONFIRMED if required_frames <= 1)
    2-3 detections -> OBSERVED
    >= required_frames -> CONFIRMED
    """

    def __init__(self, required_frames: int = 2, max_frame_gap: int = 4, iou_match_thresh: float = 0.30) -> None:
        self.required_frames = required_frames
        self.max_frame_gap = max_frame_gap
        self.iou_match_thresh = iou_match_thresh
        self.tracks: List[Dict[str, Any]] = []
        self._next_id = 1

    def update(self, current_frame_idx: int, current_dets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        confirmed_dets: List[Dict[str, Any]] = []
        matched_track_indices = set()
        matched_det_indices = set()

        for d_idx, det in enumerate(current_dets):
            bbox = det["bbox"]
            best_iou = 0.0
            best_t_idx = -1

            for t_idx, tr in enumerate(self.tracks):
                if t_idx in matched_track_indices:
                    continue
                iou = compute_iou(bbox, tr["bbox"])
                if iou >= self.iou_match_thresh and iou > best_iou:
                    best_iou = iou
                    best_t_idx = t_idx

            if best_t_idx >= 0:
                matched_track_indices.add(best_t_idx)
                matched_det_indices.add(d_idx)

                tr = self.tracks[best_t_idx]
                tr["bbox"] = bbox
                tr["confidence"] = det["confidence"]
                tr["count"] += 1
                tr["last_seen_frame"] = current_frame_idx

                status = "CONFIRMED" if tr["count"] >= self.required_frames else ("OBSERVED" if tr["count"] >= 2 else "UNCONFIRMED")
                tr["status"] = status

                updated_det = dict(det)
                updated_det["status"] = status
                updated_det["track_id"] = tr["id"]
                updated_det["history_count"] = tr["count"]
                confirmed_dets.append(updated_det)

        for d_idx, det in enumerate(current_dets):
            if d_idx not in matched_det_indices:
                t_id = f"PHONE_{self._next_id}"
                self._next_id += 1
                status = "CONFIRMED" if 1 >= self.required_frames else "UNCONFIRMED"
                new_tr = {
                    "id": t_id,
                    "bbox": det["bbox"],
                    "confidence": det["confidence"],
                    "count": 1,
                    "last_seen_frame": current_frame_idx,
                    "status": status,
                }
                self.tracks.append(new_tr)
                det_copy = dict(det)
                det_copy["status"] = status
                det_copy["track_id"] = t_id
                det_copy["history_count"] = 1
                confirmed_dets.append(det_copy)

        self.tracks = [
            tr for tr in self.tracks
            if (current_frame_idx - tr["last_seen_frame"]) <= self.max_frame_gap
        ]

        return confirmed_dets


class RoboflowPhoneDetector(ObjectDetector):
    """
    High-Performance Roboflow & Local YOLO Phone Detector.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.20,
        iou_threshold: float = 0.45,
        confirmation_frames: int = 1,
    ) -> None:
        self.model_id = model_id or os.getenv("ROBOFLOW_MODEL_ID", "phone-detection-3d9gh/1")
        self.api_key = api_key or os.getenv("ROBOFLOW_API_KEY")
        self.confidence_threshold = float(os.getenv("ROBOFLOW_PHONE_CONFIDENCE", "0.20"))
        self.iou_threshold = float(os.getenv("ROBOFLOW_IOU_THRESHOLD", "0.45"))
        self.confirmation_frames = int(os.getenv("PHONE_CONFIRMATION_FRAMES", "1"))

        self._model = None
        self._local_yolo = None
        self._device_str = "CPU"
        self._frame_counter = 0
        self._printed_raw_response = False

        self.temporal_tracker = TemporalPhoneTracker(required_frames=self.confirmation_frames)

        self.debug_metrics: Dict[str, Any] = {
            "model_id": self.model_id,
            "device": "CPU",
            "loaded": False,
            "roboflow_status": "NOT_LOADED",
            "inference_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "raw_detections": 0,
            "filtered_phone_detections": 0,
            "final_detections": 0,
            "detections": [],
        }

    def load(self, device: str = "cpu") -> None:
        """Initialize the Roboflow Inference and local YOLO models at startup."""
        print("=" * 60)
        print("ROBOFLOW & LOCAL PHONE DETECTOR INITIALIZATION")
        print(f"Model ID: {self.model_id}")
        print(f"API key present: {'YES' if bool(self.api_key) else 'NO'}")
        print("Expected target class: PHONE (matches 'phone', 'cell phone', 'mobile phone')")

        try:
            import torch
            if torch.cuda.is_available():
                self._device_str = f"GPU ({torch.cuda.get_device_name(0)})"
            else:
                self._device_str = "CPU"
        except Exception:
            self._device_str = "CPU"

        self.debug_metrics["device"] = self._device_str

        # 1. Try Roboflow Inference SDK
        try:
            from inference import get_model
            logger.info("Attempting to load Roboflow model_id='%s'...", self.model_id)
            self._model = get_model(model_id=self.model_id, api_key=self.api_key)
            self.debug_metrics["roboflow_status"] = "CONNECTED (Roboflow Inference SDK)"
            logger.info("Roboflow model [%s] loaded successfully.", self.model_id)
        except Exception as rf_ex:
            logger.info("Roboflow SDK not loaded: %s (using local YOLO phone detector)", rf_ex)
            self.debug_metrics["roboflow_status"] = "CONNECTED (Local YOLO Phone Detector)"

        # 2. Always load Local Ultralytics YOLO as fast fallback/primary phone detector
        try:
            import torch
            from ultralytics import YOLO
            self._device = "cuda:0" if torch.cuda.is_available() else "cpu"
            self._half = torch.cuda.is_available()
            self._local_yolo = YOLO("yolo11n.pt")
            if self._device.startswith("cuda"):
                self._local_yolo.to(self._device)
            logger.info("Local YOLO11 phone detector initialized on %s (half=%s).", self._device_str, self._half)
        except Exception as yolo_ex:
            logger.warning("Could not load local YOLO phone detector: %s", yolo_ex)

        is_loaded = (self._model is not None) or (self._local_yolo is not None)
        self.debug_metrics["loaded"] = is_loaded
        print(f"Model loaded: {'YES' if is_loaded else 'NO'} ({self.model_id})")
        print("=" * 60)

    def is_loaded(self) -> bool:
        return (self._model is not None) or (self._local_yolo is not None)

    @property
    def model_name(self) -> str:
        return f"Roboflow Phone Detector ({self.model_id})"

    def detect(self, frame: np.ndarray, student_bboxes: Optional[List[Dict[str, float]]] = None) -> List[Dict[str, Any]]:
        """
        Detect mobile phones in frame using Roboflow model or local YOLO phone detector.
        """
        t_total_start = time.perf_counter()
        self._frame_counter += 1

        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        candidate_detections: List[Dict[str, Any]] = []
        inference_latency_ms = 0.0
        raw_predictions = []

        # 1. Run Roboflow Model (if loaded)
        if self._model is not None:
            try:
                t_inf = time.perf_counter()
                res = self._model.infer(frame)
                inference_latency_ms = (time.perf_counter() - t_inf) * 1000.0

                if isinstance(res, list) and len(res) > 0:
                    raw_predictions = getattr(res[0], "predictions", []) if hasattr(res[0], "predictions") else res[0].get("predictions", [])
                elif hasattr(res, "predictions"):
                    raw_predictions = getattr(res, "predictions")
                elif isinstance(res, dict):
                    raw_predictions = res.get("predictions", [])

                for p in raw_predictions:
                    if isinstance(p, dict):
                        cx, cy, pw, ph = p.get("x", 0), p.get("y", 0), p.get("width", 0), p.get("height", 0)
                        conf = float(p.get("confidence", 0.0))
                        c_name = str(p.get("class", p.get("class_name", "")))
                    else:
                        cx, cy, pw, ph = getattr(p, "x", 0), getattr(p, "y", 0), getattr(p, "width", 0), getattr(p, "height", 0)
                        conf = float(getattr(p, "confidence", 0.0))
                        c_name = str(getattr(p, "class_name", getattr(p, "class", "")))

                    c_norm = c_name.strip().lower()
                    if (c_norm in TARGET_PHONE_CLASSES or any(k in c_norm for k in ("phone", "mobile", "cell"))) and conf >= self.confidence_threshold:
                        x1 = int(max(0, cx - pw / 2.0))
                        y1 = int(max(0, cy - ph / 2.0))
                        x2 = int(min(w, cx + pw / 2.0))
                        y2 = int(min(h, cy + ph / 2.0))
                        candidate_detections.append({
                            "class_name": TARGET_CLASS_NAME,
                            "raw_class": c_name,
                            "confidence": round(conf, 4),
                            "bbox": [x1, y1, x2, y2],
                        })
            except Exception as ex:
                logger.debug("Roboflow model infer exception: %s", ex)

        # 2. Run Local YOLO Phone Detector (COCO class 67 = 'cell phone') on GPU
        if self._local_yolo is not None:
            try:
                t_inf = time.perf_counter()
                dev = getattr(self, "_device", "cpu")
                half_prec = getattr(self, "_half", False)
                # Run full-frame detection specifically on cell phone (67)
                y_res = self._local_yolo.predict(
                    frame,
                    conf=0.15,
                    classes=[67],
                    device=dev,
                    half=half_prec,
                    imgsz=640,
                    verbose=False
                )
                inference_latency_ms = max(inference_latency_ms, (time.perf_counter() - t_inf) * 1000.0)

                if y_res and len(y_res) > 0 and y_res[0].boxes is not None:
                    for b in y_res[0].boxes:
                        conf = float(b.conf[0])
                        cls_idx = int(b.cls[0])
                        cls_name = self._local_yolo.names.get(cls_idx, "cell phone")
                        xyxy = b.xyxy[0].cpu().numpy().tolist()
                        x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])

                        candidate_detections.append({
                            "class_name": TARGET_CLASS_NAME,
                            "raw_class": cls_name,
                            "confidence": round(conf, 4),
                            "bbox": [x1, y1, x2, y2],
                        })

                # If no full-frame detection and student regions provided, scan zoomed student crops
                if not candidate_detections and student_bboxes:
                    for sb in student_bboxes[:2]:
                        cx1 = max(0, int(sb.get("x1", 0) - 30))
                        cy1 = max(0, int(sb.get("y1", 0) - 20))
                        cx2 = min(w, int(sb.get("x2", w) + 30))
                        cy2 = min(h, int(sb.get("y2", h) + 50))
                        crop = frame[cy1:cy2, cx1:cx2]
                        if crop.size > 0 and (cx2 - cx1) >= 60 and (cy2 - cy1) >= 60:
                            crop_res = self._local_yolo.predict(
                                crop,
                                conf=0.12,
                                classes=[67],
                                device=dev,
                                half=half_prec,
                                imgsz=320,
                                verbose=False
                            )
                            if crop_res and len(crop_res) > 0 and crop_res[0].boxes is not None:
                                for b in crop_res[0].boxes:
                                    conf = float(b.conf[0])
                                    c_xy = b.xyxy[0].cpu().numpy().tolist()
                                    candidate_detections.append({
                                        "class_name": TARGET_CLASS_NAME,
                                        "raw_class": "cell phone",
                                        "confidence": round(conf, 4),
                                        "bbox": [cx1 + int(c_xy[0]), cy1 + int(c_xy[1]), cx1 + int(c_xy[2]), cy1 + int(c_xy[3])],
                                    })
            except Exception as yex:
                logger.debug("Local YOLO phone detector error: %s", yex)

        # 3. Apply Calculator Verification & False-Positive Rejection Filter
        from app.object_detection.calculator_discriminator import get_calculator_discriminator
        calc_discriminator = get_calculator_discriminator()

        for det in candidate_detections:
            bx = det["bbox"]
            bx1, by1, bx2, by2 = max(0, bx[0]), max(0, bx[1]), min(w, bx[2]), min(h, bx[3])
            if (bx2 - bx1) >= 20 and (by2 - by1) >= 20:
                obj_crop = frame[by1:by2, bx1:bx2]
                is_calc, calc_score, calc_metrics = calc_discriminator.is_calculator(obj_crop)
                if is_calc:
                    det["class_name"] = "CALCULATOR"
                    det["raw_class"] = "calculator"
                    det["is_permitted"] = True
                    det["calculator_score"] = calc_score
                    det["metrics"] = calc_metrics
                    logger.info("Reclassified device at %s from PHONE to CALCULATOR (score=%.2f, buttons=%d)",
                                bx, calc_score, calc_metrics.get("num_buttons", 0))
                else:
                    det["is_permitted"] = False

        # 4. Save diagnostic debug images
        try:
            temp_dir = Path("temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(temp_dir / "roboflow_test_frame.jpg"), frame)

            data_dir = Path("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(data_dir / "debug_roboflow_input.jpg"), frame)

            debug_img = frame.copy()
            for d in candidate_detections:
                bx = d["bbox"]
                if d.get("is_permitted") or d.get("class_name") == "CALCULATOR":
                    cv2.rectangle(debug_img, (bx[0], bx[1]), (bx[2], bx[3]), (0, 220, 100), 2, cv2.LINE_AA)
                    cv2.putText(debug_img, f"CALCULATOR {int(d['confidence']*100)}%", (bx[0], max(15, bx[1]-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 100), 1)
                else:
                    cv2.rectangle(debug_img, (bx[0], bx[1]), (bx[2], bx[3]), (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.putText(debug_img, f"PHONE {int(d['confidence']*100)}%", (bx[0], max(15, bx[1]-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            cv2.imwrite(str(temp_dir / "roboflow_debug.jpg"), debug_img)
        except Exception:
            pass

        # 5. IoU duplicate suppression (NMS)
        candidate_detections.sort(key=lambda d: d["confidence"], reverse=True)
        suppressed_detections: List[Dict[str, Any]] = []
        for det in candidate_detections:
            keep = True
            for existing in suppressed_detections:
                if compute_iou(det["bbox"], existing["bbox"]) >= self.iou_threshold:
                    keep = False
                    break
            if keep:
                suppressed_detections.append(det)

        # 6. Temporal tracking
        all_tracked = self.temporal_tracker.update(self._frame_counter, suppressed_detections)
        final_detections = all_tracked if all_tracked else suppressed_detections

        total_latency_ms = (time.perf_counter() - t_total_start) * 1000.0

        # 6. Update debug metrics
        self.debug_metrics = {
            "model_id": self.model_id,
            "device": self._device_str,
            "loaded": self.is_loaded(),
            "roboflow_status": self.debug_metrics.get("roboflow_status", "CONNECTED"),
            "inference_latency_ms": round(inference_latency_ms, 2),
            "total_latency_ms": round(total_latency_ms, 2),
            "raw_detections": len(candidate_detections),
            "filtered_phone_detections": len(suppressed_detections),
            "final_detections": len(final_detections),
            "detections": [
                {
                    "class_name": d["class_name"],
                    "confidence": f"{int(d['confidence'] * 100)}%",
                    "bbox": d["bbox"],
                    "status": d.get("status", "CONFIRMED"),
                }
                for d in final_detections
            ],
        }

        return final_detections

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: Optional[float] = None,
        classes: Optional[List[str]] = None,
        trigger: Optional[str] = None,
    ) -> List[ObjectDetection]:
        """Adapter method conforming to ObjectDetector interface."""
        if confidence_threshold is not None:
            orig_thresh = self.confidence_threshold
            self.confidence_threshold = confidence_threshold
            results = self.detect(image)
            self.confidence_threshold = orig_thresh
        else:
            results = self.detect(image)

        detections: List[ObjectDetection] = []
        for r in results:
            cls_name = "calculator" if (r.get("is_permitted") or r.get("class_name") == "CALCULATOR") else "mobile_phone"
            detections.append(
                ObjectDetection(
                    object_class=cls_name,
                    confidence=r["confidence"],
                    bbox=r["bbox"],
                )
            )

        return detections
