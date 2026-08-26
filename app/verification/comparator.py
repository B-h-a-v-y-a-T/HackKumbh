"""
Live vs Retrospective Comparator.

Compares live pipeline results with retrospective results for the same
track/time window. Produces VerificationStatus.

Never produces a cheating verdict. Only comparison data for human review.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.schemas.common import ObjectDetection, VerificationStatus

logger = logging.getLogger(__name__)


class LiveRetroComparator:
    """
    Compares live pipeline results with retrospective results.

    Allowed statuses:
        NO_CHANGE, STRENGTHENED, WEAKENED, NEW_EVENT,
        CONFIRMED_EVIDENCE, INSUFFICIENT_VISIBILITY
    """

    def __init__(
        self,
        strengthened_threshold: float = 0.3,
        weakened_threshold: float = -0.2,
        new_event_threshold: float = 0.6,
    ) -> None:
        self._strengthen_thresh = strengthened_threshold
        self._weaken_thresh = weakened_threshold
        self._new_event_thresh = new_event_threshold

    def compare(
        self,
        live_risk: float,
        verified_risk: float,
        live_detections: Optional[List[ObjectDetection]] = None,
        verified_detections: Optional[List[ObjectDetection]] = None,
        temporal_anomaly_score: float = 0.0,
        visibility_ok: bool = True,
    ) -> dict:
        """
        Compare live and retrospective results.

        Returns comparison dict with status and scores.
        """
        if not visibility_ok:
            return {
                "live_risk": round(live_risk, 4),
                "verified_risk": round(verified_risk, 4),
                "verification_status": VerificationStatus.INSUFFICIENT_VISIBILITY,
                "risk_delta": 0.0,
            }

        delta = verified_risk - live_risk

        # Determine status
        if live_risk < 0.1 and verified_risk >= self._new_event_thresh:
            status = VerificationStatus.NEW_EVENT
        elif delta >= self._strengthen_thresh:
            status = VerificationStatus.STRENGTHENED
        elif delta <= self._weaken_thresh:
            status = VerificationStatus.WEAKENED
        elif live_risk >= 0.5 and verified_risk >= 0.5:
            status = VerificationStatus.CONFIRMED_EVIDENCE
        else:
            status = VerificationStatus.NO_CHANGE

        # Check for new objects found in retrospective
        if verified_detections and not live_detections:
            if any(d.confidence > self._new_event_thresh for d in verified_detections):
                status = VerificationStatus.NEW_EVENT

        return {
            "live_risk": round(live_risk, 4),
            "verified_risk": round(verified_risk, 4),
            "verification_status": status,
            "risk_delta": round(delta, 4),
            "temporal_anomaly_score": round(temporal_anomaly_score, 4),
        }

    def format_time_window(self, start: float, end: float) -> str:
        """Format time window as HH:MM:SS-HH:MM:SS."""
        def fmt(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{fmt(start)}-{fmt(end)}"
