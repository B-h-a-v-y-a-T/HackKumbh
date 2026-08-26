from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime, timezone
from app.database.session import Base

class Evidence(Base):
    __tablename__ = "evidences"

    id = Column(String, primary_key=True, index=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=False, index=True)
    evidence_type = Column(String, nullable=False) # BEHAVIOURAL_TIMELINE, ROI_SKELETON, VERIFICATION_REPORT, CONTRABAND_CROP
    source = Column(String, nullable=False) # PART_1, PART_2, PART_3
    storage_reference = Column(String, nullable=True) # File path or object store key
    snapshot_url = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
