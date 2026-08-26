"""
Compatibility module for app.behaviour.models.
Re-exports all schemas and event definitions from app.behaviour.schemas.
"""

from app.behaviour.schemas.events import (
    BehaviourEvent,
    ReasonCode,
    RiskStatus,
    TrackRiskOutput,
    GroupEventOutput,
    InvigilatorDecision,
    FrameAnalysisResponse,
)
from app.behaviour.schemas.pose import (
    Keypoint,
    BoundingBox,
    DeskZone,
    TrackPose,
    InvigilatorState,
    FrameInput,
)

__all__ = [
    "BehaviourEvent",
    "ReasonCode",
    "RiskStatus",
    "TrackRiskOutput",
    "GroupEventOutput",
    "InvigilatorDecision",
    "FrameAnalysisResponse",
    "Keypoint",
    "BoundingBox",
    "DeskZone",
    "TrackPose",
    "InvigilatorState",
    "FrameInput",
]
