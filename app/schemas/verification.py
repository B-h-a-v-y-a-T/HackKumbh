"""
Verification schemas for the retrospective pipeline.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import (
    JobStatus,
    ObjectDetection,
    PoseEvidence,
    TemporalWindow,
    VerificationStatus,
)


class VerificationRunRequest(BaseModel):
    """Request to run retrospective verification on a video segment."""
    video_path: str = Field(..., description="Path to video file")
    start_time: float = Field(0.0, ge=0.0, description="Start time in seconds")
    end_time: float = Field(..., gt=0.0, description="End time in seconds")
    camera_id: Optional[str] = Field(None, description="Camera identifier")
    track_ids: Optional[List[str]] = Field(
        None,
        description="Optional filter: only verify these track IDs"
    )
    roi_metadata: Optional[List[Dict]] = Field(
        None,
        description="Optional ROI metadata for specific tracks/seats"
    )
    priority: int = Field(0, ge=0, le=10, description="Job priority (0=normal, 10=highest)")


class VerificationJobResponse(BaseModel):
    """Status response for a verification job."""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress 0.0-1.0")
    video_path: Optional[str] = Field(None, description="Source video")
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    events_found: int = Field(0, description="Number of evidence events found so far")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    created_at: Optional[float] = Field(None, description="Job creation timestamp")
    completed_at: Optional[float] = Field(None, description="Job completion timestamp")
    result_data: Optional[Dict] = Field(None, description="Full results for the verification job (available when COMPLETED)")


class VerificationResult(BaseModel):
    """Result from the heavy retrospective verification of a suspicious window."""
    window: TemporalWindow
    object_detections: List[ObjectDetection] = Field(default_factory=list)
    pose_evidence: Optional[PoseEvidence] = None
    verification_confidence: float = Field(0.0, ge=0.0, le=1.0)
    verified_objects: List[str] = Field(
        default_factory=list,
        description="Object classes confirmed by high-accuracy detector"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Verification notes (e.g. 'lighting artifact', 'occlusion')"
    )


class LiveRetroComparison(BaseModel):
    """Comparison between live pipeline and retrospective pipeline results."""
    track_id: str
    time_window: str = Field(..., description="Time window as 'HH:MM:SS-HH:MM:SS'")
    live_risk: float = Field(0.0, ge=0.0, le=1.0)
    verified_risk: float = Field(0.0, ge=0.0, le=1.0)
    verification_status: VerificationStatus
    live_detections: List[ObjectDetection] = Field(default_factory=list)
    verified_detections: List[ObjectDetection] = Field(default_factory=list)
    pose_evidence: Optional[PoseEvidence] = None
    temporal_anomaly_score: float = Field(0.0, ge=0.0, le=1.0)


class Part3VerificationInput(BaseModel):
    """Input payload representing Part 3 contraband & heavy verification result."""
    verification_id: str = "V1"
    track_ids: List[str] = Field(default_factory=list)
    object_detected: Optional[str] = None
    verification_status: str = "CONFIRMED"
    verified_risk: float = 0.85
    verification_confidence: float = 0.92
    notes: Optional[str] = None

