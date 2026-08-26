"""
Evidence schemas.

Evidence is structured output for human review.
It NEVER produces an automatic cheating verdict.
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

from app.schemas.common import (
    ObjectDetection,
    PoseEvidence,
    VerificationStatus,
)


class EvidenceEvent(BaseModel):
    """
    A structured canonical evidence event for human review.

    Single source of truth across:
    - Live video overlay (tight object bounding box + label)
    - Right-side analysis / event feed & chat
    - Behaviour Risk Engine scoring
    - Invigilator alerts & audit log
    - Retrospective verification
    """
    alert_id: str = Field(..., description="Unique alert identifier, e.g. EVT-1042")
    event_id: Optional[str] = Field(None, description="Canonical event ID alias, e.g. EVT-1042")
    track_ids: List[str] = Field(..., description="Anonymous track identifiers involved")
    camera_id: str = Field(..., description="Camera identifier")
    seat_ids: List[str] = Field(default_factory=list, description="Seat identifiers involved")
    start_time: float = Field(..., description="Event start time (seconds from video start)")
    end_time: float = Field(..., description="Event end time (seconds from video start)")

    # Canonical Single Object Info
    track_id: Optional[str] = Field(None, description="Primary anonymous track identifier, e.g. T16")
    seat_id: Optional[str] = Field(None, description="Primary seat identifier, e.g. S26")
    object_class: Optional[str] = Field(None, description="Canonical object class (mobile_phone, paper_chit, prohibited_object, unknown_object)")
    object_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Consensus object detection confidence")
    object_bbox: Optional[List[int]] = Field(None, description="Tight bounding box in full frame coords [x1, y1, x2, y2]")
    behaviour_evidence: List[str] = Field(default_factory=list, description="Co-occurring behaviour events (e.g. HAND_OUTSIDE_DESK)")
    visibility: float = Field(1.0, ge=0.0, le=1.0, description="Overall visibility quality")
    risk_score: int = Field(0, ge=0, le=100, description="Calibrated risk score")
    persistence_sec: float = Field(0.0, description="Duration in seconds of temporal object persistence")
    detection_count: int = Field(0, description="Number of supporting frame detections")

    # Events and objects
    events: List[str] = Field(
        default_factory=list,
        description="Event types detected (e.g. NEIGHBOUR_GAZE, OBJECT_INTERACTION)"
    )
    objects: List[ObjectDetection] = Field(
        default_factory=list,
        description="Object detections associated with this event"
    )

    # Confidence scores
    pose_confidence: float = Field(0.0, ge=0.0, le=1.0)
    verification_confidence: float = Field(0.0, ge=0.0, le=1.0)
    temporal_anomaly_score: float = Field(0.0, ge=0.0, le=1.0)

    # Verification status (from live vs retrospective comparison or review state)
    status: Union[VerificationStatus, str] = Field(VerificationStatus.NO_CHANGE)

    # Pose evidence
    pose_evidence: Optional[PoseEvidence] = None

    # Quality information
    image_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    low_visibility: bool = Field(False)

    # Evidence clip reference (secure ID, not filesystem path)
    evidence_clip_id: Optional[str] = Field(
        None,
        description="Secure identifier for the evidence clip, if retention is enabled"
    )

    # Multi-part Unified Intelligence fields
    sources: List[str] = Field(default_factory=list, description="Evidence sources (e.g. BEHAVIOUR_ENGINE, ROI_VERIFIER)")
    group_id: Optional[str] = Field(None, description="Spatial group ID if part of a coordinated group event")
    behaviour_risk: Optional[float] = Field(None, description="Continuous risk score from Behaviour Intelligence")
    unified_risk: Optional[float] = Field(None, description="Unified composite risk score")

    # Neutral Factual Explanation & Timing
    text_summary: Optional[str] = Field(None, description="Factual neutral explanation for invigilator UI")
    timestamp_iso: Optional[str] = Field(None, description="Human readable timestamp string, e.g. 09:19:32")
    source: str = Field("live", description="Source pipeline: 'live' or 'retrospective'")
    timestamp: Optional[float] = Field(None, description="Event timestamp (Unix epoch)")
    human_review_required: bool = Field(
        True,
        description="Always true. This system never produces automatic verdicts."
    )

    def model_post_init(self, __context) -> None:
        """Ensure canonical aliases and factual summaries are consistent."""
        if not self.event_id and self.alert_id:
            self.event_id = self.alert_id
        if not self.track_id and self.track_ids:
            self.track_id = self.track_ids[0]
        if not self.seat_id and self.seat_ids:
            self.seat_id = self.seat_ids[0]
        if not self.text_summary and self.object_class:
            clean_cls = self.object_class.replace("_", " ").title()
            conf_pct = int(self.object_confidence * 100)
            trk = self.track_id or "Unknown"
            seat = f" / Seat {self.seat_id}" if self.seat_id else ""
            self.text_summary = f"{clean_cls} detected near {trk}{seat} (Confidence: {conf_pct}%). Human review required."


class EvidenceClip(BaseModel):
    """Metadata for a generated evidence clip."""
    clip_id: str = Field(..., description="Secure clip identifier")
    alert_id: str = Field(..., description="Associated alert ID")
    start_time: float = Field(..., description="Clip start time")
    end_time: float = Field(..., description="Clip end time")
    duration: float = Field(..., description="Clip duration in seconds")
    format: str = Field("mp4", description="Video format")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    created_at: float = Field(..., description="Creation timestamp")
    retention_expires_at: Optional[float] = Field(
        None, description="When this clip will be deleted"
    )


class EvidenceResponse(BaseModel):
    """Response when querying evidence by alert ID."""
    event: EvidenceEvent
    clip: Optional[EvidenceClip] = None
    comparison: Optional[dict] = Field(
        None,
        description="Live vs retrospective comparison if available"
    )
