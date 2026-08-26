"""
StudentState schema definitions and converters.

Re-exports and bridges the canonical StudentState data structures from
app.perception.core.data_models into Pydantic models for API and serialization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.perception.core.constants import DirectionLabel, TrackingState, VisibilityLevel
from app.perception.core.data_models import StudentState as DataclassStudentState


class StudentStateModel(BaseModel):
    """Pydantic representation of the canonical anonymous StudentState."""

    track_id: str = Field(..., description="Anonymous track ID, e.g. T01")
    seat_id: str = Field("UNASSIGNED", description="Assigned seat identifier, e.g. B4")
    bbox: Optional[List[float]] = Field(None, description="[x1, y1, x2, y2] bounding box")
    keypoints: Optional[List[Dict[str, Any]]] = Field(None, description="17 COCO body keypoints")
    head_yaw_deg: Optional[float] = Field(0.0, description="Estimated head yaw angle in degrees")
    head_pitch_deg: Optional[float] = Field(0.0, description="Estimated head pitch angle in degrees")
    head_roll_deg: Optional[float] = Field(0.0, description="Estimated head roll angle in degrees")
    head_direction: str = Field("FORWARD", description="Head orientation label (LEFT, RIGHT, etc.)")
    torso_rotation_deg: Optional[float] = Field(0.0, description="Torso rotation angle")
    visibility_score: float = Field(1.0, ge=0.0, le=1.0, description="Overall student visibility")
    is_occluded: bool = Field(False, description="Occlusion flag")
    desk_roi: Optional[List[int]] = Field(None, description="Desk interaction zone [x1, y1, x2, y2]")
    tracking_state: str = Field("TRACKED", description="TRACKED, COASTING, LOST, REMOVED")
    frames_tracked: int = Field(0)
    frames_since_seen: int = Field(0)
    timestamp: float = Field(0.0)

    @classmethod
    def from_dataclass(cls, st: DataclassStudentState) -> StudentStateModel:
        """Construct from the core dataclass StudentState."""
        bbox_coords = st.bbox.to_xyxy() if st.bbox else None
        kp_list = [kp.to_dict() for kp in st.keypoints] if st.keypoints else None
        desk_box = st.desk_roi.bbox.to_xyxy_int() if st.desk_roi and st.desk_roi.bbox else None

        return cls(
            track_id=st.track_id,
            seat_id=st.seat_id,
            bbox=bbox_coords,
            keypoints=kp_list,
            head_yaw_deg=st.head_orientation.yaw_deg if st.head_orientation else 0.0,
            head_pitch_deg=st.head_orientation.pitch_deg if st.head_orientation else 0.0,
            head_roll_deg=st.head_orientation.roll_deg if st.head_orientation else 0.0,
            head_direction=st.head_orientation.direction.value if st.head_orientation else "FORWARD",
            torso_rotation_deg=st.body_geometry.torso_rotation_deg if st.body_geometry else 0.0,
            visibility_score=st.visibility.overall_score if st.visibility else 1.0,
            is_occluded=st.visibility.is_occluded if st.visibility else False,
            desk_roi=desk_box,
            tracking_state=st.tracking_state.value if hasattr(st.tracking_state, "value") else str(st.tracking_state),
            frames_tracked=st.frames_tracked,
            frames_since_seen=st.frames_since_seen,
            timestamp=st.timestamp,
        )
