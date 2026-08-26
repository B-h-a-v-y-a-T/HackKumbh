from sqlalchemy import Column, String, DateTime, Integer, Text
from datetime import datetime, timezone
from app.database.session import Base

class GroupInteraction(Base):
    __tablename__ = "group_interactions"

    id = Column(String, primary_key=True, index=True) # database primary key
    group_id = Column(String, nullable=False, index=True) # e.g. G3
    exam_id = Column(String, nullable=False, index=True)
    member_tracks = Column(Text, nullable=False) # JSON list e.g. ["T17", "T18", "T19"]
    group_risk = Column(Integer, default=0)
    pattern_description = Column(String, nullable=False) # e.g. "Possible coordinated behavioural pattern"
    window_start = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    window_end = Column(DateTime, default=lambda: datetime.now(timezone.utc))
