from pydantic import BaseModel, Field
from typing import Optional, List

class Part2BehaviourInput(BaseModel):
    timestamp: float
    track_id: str
    seat_id: Optional[str] = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: str = "LOW" # LOW, MEDIUM, HIGH, CRITICAL
    events: List[str] = Field(default_factory=list) # e.g. ["NEIGHBOUR_GAZE", "TORSO_ROTATE"]
    duration_sec: float = 0.0
    baseline_deviation: float = 0.0
    group_id: Optional[str] = None
    group_members: Optional[List[str]] = None
    group_risk: Optional[int] = 0
    confidence: float = 0.85
