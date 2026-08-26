"""
Common schemas shared across the application.

All identifiers are anonymous (track_id, seat_id, camera_id).
No personal information is ever included.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TriggerType(str, Enum):
    """Behavioural triggers that increase ROI attention. NOT proof of misconduct."""
    HAND_OUTSIDE_DESK = "HAND_OUTSIDE_DESK"
    HAND_UNDER_DESK = "HAND_UNDER_DESK"
    UNUSUAL_HAND_MOVEMENT = "UNUSUAL_HAND_MOVEMENT"
    TORSO_ROTATION = "TORSO_ROTATION"
    NEIGHBOUR_INTERACTION = "NEIGHBOUR_INTERACTION"
    REPEATED_HEAD_TURN = "REPEATED_HEAD_TURN"
    OBJECT_ALREADY_DETECTED = "OBJECT_ALREADY_DETECTED"
    MANUAL_REVIEW_TRIGGER = "MANUAL_REVIEW_TRIGGER"


class ROIState(str, Enum):
    """Processing state for an ROI."""
    NORMAL = "NORMAL"
    ACTIVE = "ACTIVE"


class VerificationStatus(str, Enum):
    """Status from comparing live vs retrospective results."""
    NO_CHANGE = "NO_CHANGE"
    STRENGTHENED = "STRENGTHENED"
    WEAKENED = "WEAKENED"
    NEW_EVENT = "NEW_EVENT"
    CONFIRMED_EVIDENCE = "CONFIRMED_EVIDENCE"
    INSUFFICIENT_VISIBILITY = "INSUFFICIENT_VISIBILITY"


class JobStatus(str, Enum):
    """Status of an asynchronous verification job."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ObjectClass(str, Enum):
    """Detectable object classes."""
    MOBILE_PHONE = "mobile_phone"
    PAPER_CHIT = "paper_chit"
    PROHIBITED_OBJECT = "prohibited_object"


# ---------------------------------------------------------------------------
# Base Models
# ---------------------------------------------------------------------------

class BBox(BaseModel):
    """Bounding box in [x1, y1, x2, y2] format."""
    x1: int = Field(..., description="Left x coordinate")
    y1: int = Field(..., description="Top y coordinate")
    x2: int = Field(..., description="Right x coordinate")
    y2: int = Field(..., description="Bottom y coordinate")

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


class ObjectDetection(BaseModel):
    """A single object detection result. Evidence only — not a verdict."""
    object_class: str = Field(..., description="Detected object class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bbox: List[int] = Field(..., min_length=4, max_length=4, description="[x1, y1, x2, y2]")
    track_id: Optional[str] = Field(None, description="Anonymous track identifier")
    seat_id: Optional[str] = Field(None, description="Seat identifier")


class ImageQuality(BaseModel):
    """Image quality assessment for an ROI crop."""
    image_quality: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    overexposure: bool = Field(False, description="Severe overexposure detected")
    underexposure: bool = Field(False, description="Severe underexposure detected")
    contrast_quality: float = Field(..., ge=0.0, le=1.0, description="Contrast quality score")
    blur_score: float = Field(0.5, ge=0.0, le=1.0, description="Blur/sharpness score")
    clipping_ratio: float = Field(0.0, ge=0.0, le=1.0, description="Ratio of clipped pixels")
    clahe_applied: bool = Field(False, description="Whether CLAHE was applied")


class PoseEvidence(BaseModel):
    """Pose-based evidence from ViTPose++. Not identity information."""
    head_confidence: float = Field(0.0, ge=0.0, le=1.0)
    head_direction: str = Field("UNKNOWN", description="Estimated head direction or UNKNOWN")
    torso_rotation: float = Field(0.0, description="Estimated torso rotation in degrees")
    hand_visibility: float = Field(0.0, ge=0.0, le=1.0)
    pose_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall pose confidence")
    reason: Optional[str] = Field(None, description="Reason if visibility is low")


class TemporalWindow(BaseModel):
    """A time window with associated anomaly scoring."""
    window_start: float = Field(..., description="Start time in seconds")
    window_end: float = Field(..., description="End time in seconds")
    temporal_anomaly_score: float = Field(..., ge=0.0, le=1.0)
    frame_count: int = Field(0, description="Number of frames analyzed")


class PerformanceMetrics(BaseModel):
    """Performance metrics for a single inference request."""
    preprocessing_ms: float = Field(0.0, description="Preprocessing latency in milliseconds")
    inference_ms: float = Field(0.0, description="Model inference latency in milliseconds")
    postprocessing_ms: float = Field(0.0, description="Post-processing latency in milliseconds")
    total_ms: float = Field(0.0, description="Total request latency in milliseconds")
