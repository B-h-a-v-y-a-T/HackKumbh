from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text
from datetime import datetime, timezone
from app.database.session import Base

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, index=True)
    exam_id = Column(String, nullable=False, index=True)
    track_id = Column(String, nullable=False, index=True) # e.g. T17
    seat_id = Column(String, nullable=True, index=True) # e.g. B4
    risk_score = Column(Integer, default=0) # Current risk score
    peak_risk = Column(Integer, default=0) # Peak historical risk score
    priority = Column(String, default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String, default="ACTIVE") # ACTIVE, CONFIRMED_FOR_REVIEW, UNSURE, DISMISSED
    confidence = Column(Float, default=0.80)
    observed_behaviours = Column(Text, nullable=False) # JSON list of strings
    duration_sec = Column(Float, default=0.0)
    low_visibility_flag = Column(Boolean, default=False)
    verification_status = Column(String, default="LIVE_DETECTION") # LIVE_DETECTION, SECOND_PASS_CONFIRMED, SECOND_PASS_DISPROVED
    group_id = Column(String, nullable=True) # e.g. G3
    object_detected = Column(String, nullable=True) # e.g. PHONE, CHIT, NONE
    explainability_json = Column(Text, nullable=True) # Pre-computed structured explainability payload
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
