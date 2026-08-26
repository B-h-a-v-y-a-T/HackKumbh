from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from datetime import datetime, timezone
from app.database.session import Base

class AnonymousTrack(Base):
    __tablename__ = "anonymous_tracks"

    id = Column(String, primary_key=True, index=True) # database primary key
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    track_id = Column(String, nullable=False, index=True) # e.g. T17 (ANONYMOUS ONLY)
    current_seat = Column(String, nullable=True) # e.g. B4
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    active = Column(Boolean, default=True)
