"""
ROI Detection API endpoints.

POST /roi/detect  — Single-frame ROI detection (Mode A)
POST /roi/batch   — Batch ROI detection for multiple students
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.models.base import ModelRegistry
from app.roi.cropper import ROICropper
from app.roi.quality import CLAHEPreprocessor, ImageQualityAnalyzer
from app.roi.temporal import TemporalSmoother
from app.roi.trigger import TriggerManager
from app.schemas.common import ObjectDetection, PerformanceMetrics
from app.schemas.roi import ROIBatchRequest, ROIDetectRequest, ROIDetectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roi", tags=["roi"])

# Shared pipeline components (initialized on first use)
_cropper: Optional[ROICropper] = None
_quality: Optional[ImageQualityAnalyzer] = None
_clahe: Optional[CLAHEPreprocessor] = None
_trigger_mgr: Optional[TriggerManager] = None
_temporal: Optional[TemporalSmoother] = None


def _get_components():
    """Lazy-initialize pipeline components."""
    global _cropper, _quality, _clahe, _trigger_mgr, _temporal
    settings = get_settings()
    if _cropper is None:
        _cropper = ROICropper(detector_input_size=settings.detector_input_size)
    if _quality is None:
        _quality = ImageQualityAnalyzer()
    if _clahe is None:
        _clahe = CLAHEPreprocessor()
    if _trigger_mgr is None:
        _trigger_mgr = TriggerManager(
            active_duration=settings.roi_active_duration_seconds,
            cooldown_duration=settings.roi_cooldown_seconds,
        )
    if _temporal is None:
        _temporal = TemporalSmoother(
            window_sizes={
                "mobile_phone": settings.temporal_window_phone,
                "paper_chit": settings.temporal_window_chit,
            },
            thresholds={
                "mobile_phone": settings.temporal_threshold_phone,
                "paper_chit": settings.temporal_threshold_chit,
            },
        )
    return _cropper, _quality, _clahe, _trigger_mgr, _temporal


async def _run_detection(request: ROIDetectRequest, frame_data: Optional[bytes] = None) -> ROIDetectResponse:
    """Core detection pipeline shared by single and batch endpoints."""
    t_start = time.perf_counter()
    settings = get_settings()
    cropper, quality_analyzer, clahe_proc, trigger_mgr, temporal = _get_components()
    registry = ModelRegistry.get_instance()
    detector = registry.get_detector("live")

    warnings = []

    # 1. Load frame from original high-resolution source
    t_pre = time.perf_counter()
    try:
        if frame_data:
            frame = cropper.load_frame(frame_data)
        elif request.frame_path:
            frame = cropper.load_frame(request.frame_path)
        else:
            raise HTTPException(status_code=400, detail="No frame provided (frame_path or upload required)")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Frame not found: {request.frame_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Crop ROI from ORIGINAL high-resolution frame
    try:
        crop, validated_roi = cropper.crop(frame, request.roi, resize_to_detector=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ROI: {e}")

    # 3. Image quality analysis
    img_quality = quality_analyzer.analyze(crop)

    # 4. Visibility-aware processing
    low_vis = False
    if request.visibility < 0.3 or request.occlusion_score > 0.7:
        low_vis = True
        warnings.append("LOW_VISIBILITY: detection confidence reduced")

    if img_quality.overexposure:
        warnings.append("OVEREXPOSURE: information may be lost, confidence reduced")
    if img_quality.underexposure:
        warnings.append("UNDEREXPOSURE: image very dark")

    # 5. Optional CLAHE preprocessing
    crop, img_quality = clahe_proc.process(crop, img_quality)

    # 6. Resize for detector
    detector_input = cropper._resize_for_detector(crop)
    t_pre_end = time.perf_counter()

    # 7. Run YOLO26-S
    t_inf = time.perf_counter()
    conf_threshold = settings.default_object_confidence
    if hasattr(detector, 'predict') and hasattr(detector.predict, '__func__'):
        # Check if mock detector accepts trigger param
        try:
            detections = detector.predict(
                detector_input,
                confidence_threshold=conf_threshold,
                trigger=request.trigger.value if request.trigger else None,
            )
        except TypeError:
            detections = detector.predict(detector_input, confidence_threshold=conf_threshold)
    else:
        detections = detector.predict(detector_input, confidence_threshold=conf_threshold)
    t_inf_end = time.perf_counter()

    # 8. Apply class-specific confidence thresholds
    filtered = []
    for det in detections:
        class_thresh = settings.get_confidence_threshold(det.object_class)
        if det.confidence >= class_thresh:
            det.track_id = request.track_id
            det.seat_id = request.seat_id
            filtered.append(det)

    # Reduce confidence if low visibility
    if low_vis:
        for det in filtered:
            det.confidence = round(det.confidence * 0.6, 4)

    # 9. Process trigger
    roi_state = await trigger_mgr.process_trigger(request.track_id, request.trigger)

    # 10. Temporal smoothing
    det_tuples = [(d.object_class, d.confidence) for d in filtered]
    smoothing_results = temporal.update_batch(
        request.track_id, det_tuples,
        all_classes=["mobile_phone", "paper_chit", "prohibited_object"],
    )
    smoothed_confs = {cls: round(v[0], 4) for cls, v in smoothing_results.items()}
    evidence_ready = {cls: v[1] for cls, v in smoothing_results.items()}

    t_end = time.perf_counter()

    return ROIDetectResponse(
        camera_id=request.camera_id,
        track_id=request.track_id,
        seat_id=request.seat_id,
        timestamp=request.timestamp,
        roi=validated_roi,
        roi_state=roi_state,
        image_quality=img_quality,
        detections=filtered,
        smoothed_confidences=smoothed_confs,
        evidence_ready=evidence_ready,
        low_visibility=low_vis,
        quality_warnings=warnings,
        metrics=PerformanceMetrics(
            preprocessing_ms=round((t_pre_end - t_pre) * 1000, 2),
            inference_ms=round((t_inf_end - t_inf) * 1000, 2),
            total_ms=round((t_end - t_start) * 1000, 2),
        ),
    )


@router.post("/detect", response_model=ROIDetectResponse)
async def detect_roi(request: ROIDetectRequest):
    """
    Single-frame ROI detection (Mode A).

    Crops the ROI from the ORIGINAL high-resolution frame,
    runs image quality analysis, optional CLAHE, YOLO26-S detection,
    and temporal smoothing.
    """
    return await _run_detection(request)


@router.post("/detect/upload", response_model=ROIDetectResponse)
async def detect_roi_upload(
    camera_id: str,
    track_id: str,
    roi: str,
    timestamp: float,
    file: UploadFile = File(...),
    seat_id: Optional[str] = None,
    visibility: float = 1.0,
    trigger: Optional[str] = None,
):
    """ROI detection with multipart frame upload."""
    from app.schemas.common import TriggerType
    roi_list = [int(x.strip()) for x in roi.split(",")]
    trigger_enum = TriggerType(trigger) if trigger else None

    request = ROIDetectRequest(
        camera_id=camera_id,
        track_id=track_id,
        seat_id=seat_id,
        roi=roi_list,
        visibility=visibility,
        trigger=trigger_enum,
        timestamp=timestamp,
    )
    frame_data = await file.read()
    return await _run_detection(request, frame_data=frame_data)


@router.post("/batch")
async def detect_batch(request: ROIBatchRequest):
    """Batch ROI detection for multiple students in one frame."""
    results = []
    for roi_req in request.requests:
        if not roi_req.frame_path:
            roi_req.frame_path = request.frame_path
        try:
            result = await _run_detection(roi_req)
            results.append(result)
        except HTTPException as e:
            results.append({"track_id": roi_req.track_id, "error": e.detail})
    return {"camera_id": request.camera_id, "timestamp": request.timestamp, "results": results}
