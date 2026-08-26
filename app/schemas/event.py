from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class NormalizedEvent(BaseModel):
    event_id: str
    source: str # PART_1, PART_2, PART_3, MOCK
    timestamp: str # ISO 8601 string
    exam_id: str = "EXAM_001"
    camera_id: Optional[str] = "CAM_01"
    track_ids: List[str] = Field(default_factory=list)
    seat_ids: List[str] = Field(default_factory=list)
    event_type: str
    severity: str = "LOW" # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float = 0.85
    risk_score: Optional[float] = None
    duration_sec: Optional[float] = None
    evidence_references: List[str] = Field(default_factory=list)
    visibility_context: float = 0.90
    occlusion_score: Optional[float] = None
    group_id: Optional[str] = None
    group_members: List[str] = Field(default_factory=list)
    human_review_status: Optional[str] = "UNVERIFIED"
    metadata: Dict[str, Any] = Field(default_factory=dict)
