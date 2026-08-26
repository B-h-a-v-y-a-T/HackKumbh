"""
ROI detection request/response schemas.

The ROI represents a student's interaction zone (upper body, hands, desk surface,
immediate surroundings). It is NOT just the hands — a phone can be lying on
the desk before a hand moves toward it.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    ImageQuality,
    ObjectDetection,
    PerformanceMetrics,
    TriggerType,
    ROIState,
)


class ROIDetectRequest(BaseModel):
    """
    Single-frame ROI detection request.

    The ROI must be defined in the coordinate space of the ORIGINAL
    high-resolution frame. The service crops from the original frame,
    never from a downsampled version.
    """
    camera_id: str = Field(..., description="Camera identifier")
    track_id: str = Field(..., description="Anonymous track identifier (e.g. T17)")
    seat_id: Optional[str] = Field(None, description="Seat identifier (e.g. B4)")
    frame_path: Optional[str] = Field(
        None,
        description="Path to the original high-resolution frame. "
                    "Can also be supplied via multipart upload."
    )
    roi: List[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[x1, y1, x2, y2] in original frame coordinates"
    )
    visibility: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Visibility score from upstream system"
    )
    occlusion_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Occlusion score from upstream system"
    )
    trigger: Optional[TriggerType] = Field(
        None,
        description="Behavioural trigger (increases attention, NOT proof of misconduct)"
    )
    timestamp: float = Field(..., description="Frame timestamp (Unix epoch)")

    # Optional upstream pose/visibility hints
    head_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    hand_visibility: Optional[float] = Field(None, ge=0.0, le=1.0)

    @field_validator("roi")
    @classmethod
    def validate_roi(cls, v: List[int]) -> List[int]:
        x1, y1, x2, y2 = v
        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"Invalid ROI: x2 must be > x1 and y2 must be > y1. Got [{x1}, {y1}, {x2}, {y2}]"
            )
        if x1 < 0 or y1 < 0:
            raise ValueError(f"ROI coordinates must be non-negative. Got [{x1}, {y1}, {x2}, {y2}]")
        return v


class ROIBatchRequest(BaseModel):
    """Batch of ROI detection requests for multiple students in one frame."""
    camera_id: str = Field(..., description="Camera identifier")
    frame_path: Optional[str] = Field(None, description="Path to the original high-resolution frame")
    timestamp: float = Field(..., description="Frame timestamp (Unix epoch)")
    requests: List[ROIDetectRequest] = Field(..., min_length=1, description="List of ROI requests")


class ROIDetectResponse(BaseModel):
    """Response from ROI detection."""
    camera_id: str
    track_id: str
    seat_id: Optional[str] = None
    timestamp: float
    roi: List[int]
    roi_state: ROIState = ROIState.NORMAL

    # Image quality assessment
    image_quality: Optional[ImageQuality] = None

    # Object detections (evidence, not verdicts)
    detections: List[ObjectDetection] = Field(default_factory=list)

    # Temporal smoothing results
    smoothed_confidences: dict = Field(
        default_factory=dict,
        description="Per-class smoothed confidence from temporal evidence"
    )
    evidence_ready: dict = Field(
        default_factory=dict,
        description="Per-class flag indicating temporal evidence threshold met"
    )

    # Performance
    metrics: Optional[PerformanceMetrics] = None

    # Visibility / quality warnings
    low_visibility: bool = Field(False, description="ROI has low visibility")
    quality_warnings: List[str] = Field(default_factory=list)
