from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ExplainabilityFactor(BaseModel):
    title: str
    description: str

class AlertExplainability(BaseModel):
    summary: str
    observed_points: List[str]
    confidence_score: float
    reduced_confidence_reasons: List[str]
    recommendation: str

class AlertResponse(BaseModel):
    id: str
    exam_id: str
    track_id: str
    seat_id: Optional[str]
    risk_score: int
    peak_risk: int
    priority: str
    status: str
    confidence: float
    observed_behaviours: List[str]
    duration_sec: float
    low_visibility_flag: bool
    verification_status: str
    group_id: Optional[str]
    object_detected: Optional[str]
    explainability: Optional[AlertExplainability]
    created_at: str
    updated_at: str

class AlertReviewRequest(BaseModel):
    decision: str # CONFIRM_FOR_REVIEW, DISMISS, UNSURE
    notes: Optional[str] = ""
    reviewer_id: Optional[str] = "Invigilator_Admin"
