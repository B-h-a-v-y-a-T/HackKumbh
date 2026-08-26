from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime, timezone
from app.database.session import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    action = Column(String, nullable=False) # REVIEW_ALERT, SIMULATION_START, INTEGRATION_INGEST, PRIVACY_ENFORCE
    actor = Column(String, default="SYSTEM")
    resource = Column(String, nullable=True) # e.g. Alert A104
    metadata_json = Column(Text, nullable=True)
