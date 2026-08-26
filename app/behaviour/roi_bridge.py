"""
ROI Trigger Bridge — Connects Part 2 Behaviour Events to Part 3 ROI Detection.

Converts behaviour risk events into TriggerType calls for the existing ROI
trigger manager, activating high-resolution object detection when needed.

This bridge is the critical integration point between Parts 2 and 3.
A behaviour event is NOT proof of cheating — it merely tells the object
detector to spend more computation on a student's interaction zone.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.behaviour.schemas.events import BehaviourEvent, TrackRiskOutput
from app.schemas.common import TriggerType

logger = logging.getLogger(__name__)

# Mapping from Part 2 BehaviourEvent → Part 3 TriggerType
_EVENT_TO_TRIGGER: Dict[str, TriggerType] = {
    BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value: TriggerType.HAND_OUTSIDE_DESK,
    BehaviourEvent.UNUSUAL_HAND_MOVEMENT.value: TriggerType.UNUSUAL_HAND_MOVEMENT,
    BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value: TriggerType.NEIGHBOUR_INTERACTION,
    BehaviourEvent.TORSO_ROTATION.value: TriggerType.TORSO_ROTATION,
    BehaviourEvent.TORSO_ROTATION_LEFT.value: TriggerType.TORSO_ROTATION,
    BehaviourEvent.TORSO_ROTATION_RIGHT.value: TriggerType.TORSO_ROTATION,
    BehaviourEvent.NEIGHBOUR_GAZE.value: TriggerType.NEIGHBOUR_INTERACTION,
    BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value: TriggerType.NEIGHBOUR_INTERACTION,
    BehaviourEvent.REPEATED_HEAD_TURN.value: TriggerType.REPEATED_HEAD_TURN,
    BehaviourEvent.COORDINATED_HAND_EXCHANGE.value: TriggerType.NEIGHBOUR_INTERACTION,
    BehaviourEvent.CHAIN_INFORMATION_FLOW.value: TriggerType.NEIGHBOUR_INTERACTION,
    BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED.value: TriggerType.MANUAL_REVIEW_TRIGGER,
    BehaviourEvent.PAPER_CHIT_DETECTED.value: TriggerType.OBJECT_ALREADY_DETECTED,
    BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value: TriggerType.OBJECT_ALREADY_DETECTED,
}


def get_trigger_for_events(active_events: List[str]) -> Optional[TriggerType]:
    """
    Given a list of active behaviour event strings, return the highest-priority
    TriggerType that should be sent to the ROI trigger system.

    Returns None if no events map to a trigger (normal behaviour).
    """
    # Priority order (highest priority first)
    priority = [
        BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value,
        BehaviourEvent.PAPER_CHIT_DETECTED.value,
        BehaviourEvent.CHAIN_INFORMATION_FLOW.value,
        BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED.value,
        BehaviourEvent.COORDINATED_HAND_EXCHANGE.value,
        BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value,
        BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value,
        BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value,
        BehaviourEvent.UNUSUAL_HAND_MOVEMENT.value,
        BehaviourEvent.TORSO_ROTATION.value,
        BehaviourEvent.REPEATED_HEAD_TURN.value,
        BehaviourEvent.NEIGHBOUR_GAZE.value,
    ]

    for event_name in priority:
        if event_name in active_events:
            trigger = _EVENT_TO_TRIGGER.get(event_name)
            if trigger:
                return trigger

    return None


def should_trigger_roi(track_risk: TrackRiskOutput, risk_threshold: int = 30) -> bool:
    """
    Determine whether a track's risk level or behaviour warrants triggering the ROI detector.

    Args:
        track_risk: The risk output from the behaviour engine.
        risk_threshold: Minimum risk score to trigger ROI detection.

    Returns:
        True if ROI detection should be activated for this track.
    """
    if track_risk.risk_score >= risk_threshold:
        return True

    # High-priority trigger events
    trigger_events = {
        BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value,
        BehaviourEvent.UNUSUAL_HAND_MOVEMENT.value,
        BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value,
        BehaviourEvent.COORDINATED_HAND_EXCHANGE.value,
        BehaviourEvent.CHAIN_INFORMATION_FLOW.value,
        BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED.value,
        BehaviourEvent.PAPER_CHIT_DETECTED.value,
        BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value,
        BehaviourEvent.TORSO_ROTATION.value,
        BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value,
    }
    return bool(set(track_risk.events) & trigger_events)


def build_roi_request_params(
    track_risk: TrackRiskOutput,
    camera_id: str,
    desk_roi: Optional[List[int]] = None,
    visibility: float = 1.0,
    occlusion: float = 0.0,
    timestamp: float = 0.0,
) -> Optional[dict]:
    """
    Build ROI detection request parameters from behaviour risk output.

    Returns None if no trigger is warranted.
    """
    if not should_trigger_roi(track_risk):
        return None

    trigger = get_trigger_for_events(track_risk.events)
    if trigger is None:
        trigger = TriggerType.MANUAL_REVIEW_TRIGGER

    roi = desk_roi or [0, 0, 640, 480]

    return {
        "camera_id": camera_id,
        "track_id": track_risk.track_id,
        "seat_id": track_risk.seat_id,
        "roi": roi,
        "visibility": visibility,
        "occlusion_score": occlusion,
        "trigger": trigger,
        "timestamp": timestamp,
    }
