"""Pose and Keypoint Schemas for Anonymous Monitoring."""
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field

COCO_KEYPOINTS = [
    "nose",            # 0
    "left_eye",        # 1
    "right_eye",       # 2
    "left_ear",        # 3
    "right_ear",       # 4
    "left_shoulder",   # 5
    "right_shoulder",  # 6
    "left_elbow",      # 7
    "right_elbow",     # 8
    "left_wrist",      # 9
    "right_wrist",     # 10
    "left_hip",        # 11
    "right_hip",       # 12
    "left_knee",       # 13
    "right_knee",      # 14
    "left_ankle",      # 15
    "right_ankle",     # 16
]

KEYPOINT_NAME_TO_INDEX: Dict[str, int] = {name: i for i, name in enumerate(COCO_KEYPOINTS)}


class Keypoint(BaseModel):
    """2D/3D Keypoint with detection confidence."""
    x: float = Field(..., description="Normalized or pixel X coordinate (0.0 - 1.0 or pixel)")
    y: float = Field(..., description="Normalized or pixel Y coordinate (0.0 - 1.0 or pixel)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence score")
    z: Optional[float] = Field(default=0.0, description="Optional depth/3D coordinate")


class BoundingBox(BaseModel):
    """Bounding Box for person or object."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = 1.0


class DeskZone(BaseModel):
    """Designated desk zone boundary for a specific seat in exam hall space."""
    seat_id: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    # Optional polygon coordinates [(x1,y1), (x2,y2), ...] if non-rectangular
    polygon: Optional[List[Tuple[float, float]]] = None
    row: Optional[int] = None
    col: Optional[int] = None

    def contains_point(self, x: float, y: float, margin: float = 0.02) -> bool:
        """Check if a coordinate (x, y) is inside the desk zone with boundary margin."""
        return (
            (self.x_min - margin) <= x <= (self.x_max + margin) and
            (self.y_min - margin) <= y <= (self.y_max + margin)
        )


class TrackPose(BaseModel):
    """Anonymous track pose observation at a specific frame."""
    track_id: str = Field(..., description="Anonymous track ID, e.g. T01, T17")
    seat_id: str = Field(..., description="Assigned seat identifier, e.g. A1, B4")
    keypoints: List[Keypoint] = Field(..., description="17 COCO keypoint detections")
    bbox: Optional[BoundingBox] = None
    desk_zone: Optional[DeskZone] = None
    is_writing_tool_detected: Optional[bool] = Field(default=True, description="Pen/pencil visibility flag")
    object_detections: Optional[List[Dict[str, Any]]] = Field(default=None, description="Part 3 object detections in interaction ROI")
    temporal_object_score: Optional[float] = Field(default=None, description="Multi-frame accumulated object confidence")
    additional_meta: Optional[Dict[str, Any]] = None

    def get_keypoint(self, name_or_idx: Any) -> Optional[Keypoint]:
        """Convenience method to retrieve keypoint by name or index."""
        if isinstance(name_or_idx, str):
            idx = KEYPOINT_NAME_TO_INDEX.get(name_or_idx)
            if idx is None or idx >= len(self.keypoints):
                return None
            return self.keypoints[idx]
        elif isinstance(name_or_idx, int):
            if 0 <= name_or_idx < len(self.keypoints):
                return self.keypoints[name_or_idx]
        return None


class InvigilatorState(BaseModel):
    """Invigilator / Proctor location and context."""
    invigilator_id: str = "PROCTOR_1"
    x: float
    y: float
    is_walking_in_aisle: bool = False
    is_making_announcement: bool = False


def filter_student_tracks(
    tracks: List[TrackPose],
    valid_seats: Optional[set[str]] = None,
) -> List[TrackPose]:
    """Keep only valid student tracks and remove duplicate seat / track entries.

    This prevents duplicate skeleton overlays and keeps the visualization to the
    actual exam students instead of invalid or repeated detections.
    """
    if tracks is None:
        return []

    valid_seats = valid_seats or set()
    seen_track_ids = set()
    seen_seat_ids = set()
    filtered: List[TrackPose] = []

    for tr in tracks:
        if not tr or not isinstance(tr, TrackPose):
            continue
        if not tr.track_id or not tr.seat_id:
            continue
        if valid_seats and tr.seat_id not in valid_seats:
            continue
        if len(tr.keypoints) < 17:
            continue
        if tr.track_id in seen_track_ids or tr.seat_id in seen_seat_ids:
            continue

        seen_track_ids.add(tr.track_id)
        seen_seat_ids.add(tr.seat_id)
        filtered.append(tr)

    return filtered


class FrameInput(BaseModel):
    """Single multi-person frame payload ingested by Behaviour Intelligence."""
    frame_id: int
    timestamp_ms: float
    room_id: str = "EXAM_HALL_A"
    tracks: List[TrackPose]
    invigilators: Optional[List[InvigilatorState]] = None
    exam_phase: Optional[str] = "IN_PROGRESS"  # START, IN_PROGRESS, FINAL_5_MIN
