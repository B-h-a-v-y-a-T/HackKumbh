"""
Unified Risk Engine — Combines evidence from ALL four parts.

Produces ONE explainable risk representation with evidence sources:
  - Part 2: Behaviour risk (head turning, torso rotation, spatial groups, etc.)
  - Part 3: Object evidence (phone/chit detection confidence, temporal smoothing)
  - Retrospective verification results

Never produces an automatic cheating verdict. The final decision
is always made by the human invigilator.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import VerificationStatus

logger = logging.getLogger(__name__)


class UnifiedRiskScore(BaseModel):
    """Combined risk representation with explainable evidence sources."""

    alert_id: str = Field(default_factory=lambda: f"A{uuid.uuid4().hex[:6].upper()}")
    track_id: str = Field(..., description="Anonymous track identifier")
    seat_id: str = Field(default="UNASSIGNED")
    camera_id: str = Field(default="CAM_01")
    timestamp: float = Field(default_factory=time.time)

    # Risk components
    behaviour_risk: float = Field(0.0, ge=0.0, le=1.0, description="From Part 2 behaviour engine (0-100 mapped to 0-1)")
    object_evidence_risk: float = Field(0.0, ge=0.0, le=1.0, description="From Part 3 object detection")
    retrospective_risk: float = Field(0.0, ge=0.0, le=1.0, description="From retrospective verification")

    # Combined risk
    combined_risk: float = Field(0.0, ge=0.0, le=1.0, description="Weighted combination of all risk sources")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall confidence of the risk assessment")

    # Evidence
    event_types: List[str] = Field(default_factory=list, description="All detected event types across all parts")
    sources: List[str] = Field(default_factory=list, description="Evidence sources contributing")
    group_id: Optional[str] = Field(None, description="Spatial group ID if in coordinated event")

    # Verification
    verification_status: VerificationStatus = Field(VerificationStatus.NO_CHANGE)

    # Status classification (never CHEATING)
    status: str = Field("NORMAL", description="NORMAL/MONITORING/UNUSUAL_BEHAVIOUR/SUSPICIOUS_BEHAVIOUR/HUMAN_REVIEW_REQUIRED")

    # Human review
    human_review_required: bool = Field(True, description="Always true. This system never produces automatic verdicts.")


class UnifiedRiskEngine:
    """
    Combines risk from behaviour (Part 2), object detection (Part 3),
    and retrospective verification into a single explainable score.

    Weights:
      - behaviour_weight: 0.35 (behavioural patterns)
      - object_weight: 0.45 (object detection evidence)
      - retrospective_weight: 0.20 (retrospective verification)
    """

    def __init__(
        self,
        behaviour_weight: float = 0.35,
        object_weight: float = 0.45,
        retrospective_weight: float = 0.20,
    ):
        self.behaviour_weight = behaviour_weight
        self.object_weight = object_weight
        self.retrospective_weight = retrospective_weight

        # Track risk history for temporal analysis
        self._risk_history: Dict[str, List[float]] = {}

    def compute(
        self,
        track_id: str,
        seat_id: str = "UNASSIGNED",
        camera_id: str = "CAM_01",
        # Part 2 inputs
        behaviour_risk_score: int = 0,
        behaviour_events: Optional[List[str]] = None,
        behaviour_confidence: float = 0.0,
        group_id: Optional[str] = None,
        # Part 3 inputs
        object_detections: Optional[List[Dict[str, Any]]] = None,
        smoothed_confidences: Optional[Dict[str, float]] = None,
        evidence_ready: Optional[Dict[str, bool]] = None,
        # Retrospective inputs
        retrospective_risk: float = 0.0,
        verification_status: VerificationStatus = VerificationStatus.NO_CHANGE,
    ) -> UnifiedRiskScore:
        """
        Compute a unified risk score from all evidence sources.
        """
        behaviour_events = behaviour_events or []
        object_detections = object_detections or []
        smoothed_confidences = smoothed_confidences or {}
        evidence_ready = evidence_ready or {}

        # Normalize behaviour risk from 0-100 to 0-1
        behaviour_norm = min(behaviour_risk_score / 100.0, 1.0)

        # Compute object evidence risk (max of smoothed confidences where evidence is ready)
        object_risk = 0.0
        if smoothed_confidences:
            ready_confs = [
                smoothed_confidences[cls]
                for cls, ready in evidence_ready.items()
                if ready and cls in smoothed_confidences
            ]
            if ready_confs:
                object_risk = max(ready_confs)
            else:
                # Fall back to raw detection confidences
                det_confs = [d.get("confidence", 0.0) for d in object_detections if d]
                if det_confs:
                    object_risk = max(det_confs) * 0.7  # Lower weight for unsmoothed

        # Compute combined risk
        combined = (
            self.behaviour_weight * behaviour_norm
            + self.object_weight * object_risk
            + self.retrospective_weight * retrospective_risk
        )

        # Boost if multiple sources agree
        sources: List[str] = []
        if behaviour_norm > 0.25:
            sources.append("BEHAVIOUR_ENGINE")
        if object_risk > 0.3:
            sources.append("ROI_VERIFIER")
        if retrospective_risk > 0.3:
            sources.append("RETROSPECTIVE_VERIFIER")

        if len(sources) >= 2:
            combined = min(combined * 1.15, 1.0)  # Multi-source boost
        if len(sources) >= 3:
            combined = min(combined * 1.10, 1.0)

        # Confidence from sources
        confidence = max(behaviour_confidence, object_risk, retrospective_risk)
        if len(sources) >= 2:
            confidence = min(confidence * 1.1, 0.98)

        # Collect all event types
        event_types = list(set(behaviour_events))
        for det in object_detections:
            obj_class = det.get("object_class", "")
            if obj_class:
                event_types.append(f"OBJECT_{obj_class.upper()}")

        # Status classification
        if combined < 0.25:
            status = "NORMAL"
        elif combined < 0.50:
            status = "MONITORING"
        elif combined < 0.75:
            status = "UNUSUAL_BEHAVIOUR"
        else:
            status = "HUMAN_REVIEW_REQUIRED"

        # Track history
        if track_id not in self._risk_history:
            self._risk_history[track_id] = []
        self._risk_history[track_id].append(combined)
        if len(self._risk_history[track_id]) > 100:
            self._risk_history[track_id] = self._risk_history[track_id][-100:]

        return UnifiedRiskScore(
            track_id=track_id,
            seat_id=seat_id,
            camera_id=camera_id,
            behaviour_risk=round(behaviour_norm, 4),
            object_evidence_risk=round(object_risk, 4),
            retrospective_risk=round(retrospective_risk, 4),
            combined_risk=round(combined, 4),
            confidence=round(confidence, 4),
            event_types=event_types,
            sources=sources,
            group_id=group_id,
            verification_status=verification_status,
            status=status,
        )

    def reset_track(self, track_id: str) -> None:
        """Reset risk history for a track."""
        self._risk_history.pop(track_id, None)
