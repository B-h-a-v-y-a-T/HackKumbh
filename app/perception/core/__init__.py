"""CopyCop core sub-package — data models, constants, enums."""

from app.perception.core.constants import (
    BodyPart,
    DirectionLabel,
    FrameStatus,
    StreamStatus,
    TrackingState,
    VisibilityLevel,
)
from app.perception.core.data_models import (
    BodyGeometry,
    BoundingBox,
    DeskROI,
    Detection,
    FrameHealth,
    FrameMeta,
    HeadOrientation,
    KeypointSet,
    PipelineOutput,
    SeatInfo,
    StudentState,
    TrackedObject,
    VisibilityInfo,
)

__all__ = [
    "BodyPart",
    "DirectionLabel",
    "FrameStatus",
    "StreamStatus",
    "TrackingState",
    "VisibilityLevel",
    "BodyGeometry",
    "BoundingBox",
    "DeskROI",
    "Detection",
    "FrameHealth",
    "FrameMeta",
    "HeadOrientation",
    "KeypointSet",
    "PipelineOutput",
    "SeatInfo",
    "StudentState",
    "TrackedObject",
    "VisibilityInfo",
]
