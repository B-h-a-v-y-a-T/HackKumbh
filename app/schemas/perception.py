from pydantic import BaseModel, Field
from typing import Optional, List, Any

class Part1PerceptionInput(BaseModel):
    timestamp: float
    camera_id: str
    track_id: str
    seat_id: Optional[str] = None
    bbox: Optional[List[int]] = Field(default_factory=list)
    keypoints: Optional[List[Any]] = Field(default_factory=list)
    yaw: Optional[float] = 0.0
    pitch: Optional[float] = 0.0
    roll: Optional[float] = 0.0
    head_direction: Optional[str] = "FORWARD"
    head_confidence: float = 0.90
    hand_visibility: float = 0.90
    body_visibility: float = 0.90
    occlusion_score: float = 0.10
    visibility_score: float = 0.90
    writing_state: Optional[str] = "ACTIVE"
