from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime, timezone
from app.database.session import Base

class HumanReview(Base):
    __tablename__ = "human_reviews"

    id = Column(String, primary_key=True, index=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=False, index=True)
    decision = Column(String, nullable=False) # CONFIRM_FOR_REVIEW, DISMISS, UNSURE
    notes = Column(Text, nullable=True)
    reviewer_id = Column(String, default="Invigilator_Admin")
    reviewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
