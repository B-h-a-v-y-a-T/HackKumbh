"""
Evidence Generator — Creates structured evidence events.

Every event generates structured evidence for human review.
human_review_required is ALWAYS true. No automatic verdicts.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Dict, List, Optional

from app.schemas.common import ObjectDetection, PoseEvidence, VerificationStatus
from app.schemas.evidence import EvidenceEvent

logger = logging.getLogger(__name__)

_alert_counter = 0


def generate_alert_id() -> str:
    """Generate a unique alert ID."""
    global _alert_counter
    _alert_counter += 1
    return f"A{_alert_counter:04d}"


class EvidenceGenerator:
    """Creates structured evidence events for human review."""

    def __init__(
        self,
        clip_pre_seconds: float = 3.0,
        clip_post_seconds: float = 3.0,
    ) -> None:
        self._clip_pre = clip_pre_seconds
        self._clip_post = clip_post_seconds

    def create_live_evidence(
        self,
        track_id: str,
        camera_id: str,
        timestamp: float,
        detections: List[ObjectDetection],
        seat_id: Optional[str] = None,
        image_quality: Optional[float] = None,
        trigger_events: Optional[List[str]] = None,
    ) -> EvidenceEvent:
        """Create evidence from live ROI detection."""
        max_conf = max((d.confidence for d in detections), default=0.0)
        primary_det = detections[0] if detections else None
        obj_cls = primary_det.object_class if primary_det else None
        obj_bbox = primary_det.bbox if primary_det else None
        alert_id = generate_alert_id()

        return EvidenceEvent(
            alert_id=alert_id,
            event_id=alert_id,
            track_ids=[track_id],
            track_id=track_id,
            seat_id=seat_id,
            camera_id=camera_id,
            seat_ids=[seat_id] if seat_id else [],
            start_time=timestamp,
            end_time=timestamp,
            object_class=obj_cls,
            object_confidence=max_conf,
            object_bbox=obj_bbox,
            events=trigger_events or [],
            objects=detections,
            verification_confidence=max_conf,
            status=VerificationStatus.NO_CHANGE,
            image_quality=image_quality,
            source="live",
            timestamp=time.time(),
            timestamp_iso=time.strftime("%H:%M:%S", time.localtime(time.time())),
            human_review_required=True,
        )

    def create_retrospective_evidence(
        self,
        track_ids: List[str],
        camera_id: str,
        start_time: float,
        end_time: float,
        detections: List[ObjectDetection],
        pose_evidence: Optional[PoseEvidence] = None,
        temporal_anomaly_score: float = 0.0,
        verification_confidence: float = 0.0,
        status: VerificationStatus = VerificationStatus.NO_CHANGE,
        seat_ids: Optional[List[str]] = None,
        events: Optional[List[str]] = None,
    ) -> EvidenceEvent:
        """Create evidence from retrospective verification."""
        alert_id = generate_alert_id()
        primary_det = detections[0] if detections else None
        obj_cls = primary_det.object_class if primary_det else None
        obj_bbox = primary_det.bbox if primary_det else None
        t_id = track_ids[0] if track_ids else None
        s_id = seat_ids[0] if seat_ids else None

        return EvidenceEvent(
            alert_id=alert_id,
            event_id=alert_id,
            track_ids=track_ids,
            track_id=t_id,
            seat_id=s_id,
            camera_id=camera_id,
            seat_ids=seat_ids or [],
            start_time=start_time,
            end_time=end_time,
            object_class=obj_cls,
            object_confidence=verification_confidence,
            object_bbox=obj_bbox,
            events=events or [],
            objects=detections,
            pose_confidence=pose_evidence.pose_confidence if pose_evidence else 0.0,
            verification_confidence=verification_confidence,
            temporal_anomaly_score=temporal_anomaly_score,
            status=status,
            pose_evidence=pose_evidence,
            source="retrospective",
            timestamp=time.time(),
            timestamp_iso=time.strftime("%H:%M:%S", time.localtime(time.time())),
            human_review_required=True,
        )

    def get_clip_time_range(
        self, start_time: float, end_time: float
    ) -> tuple:
        """Get the extended clip range for evidence (pre + post padding)."""
        clip_start = max(0, start_time - self._clip_pre)
        clip_end = end_time + self._clip_post
        return clip_start, clip_end
