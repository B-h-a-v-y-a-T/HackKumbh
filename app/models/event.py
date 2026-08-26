from sqlalchemy import Column, String, DateTime, Float, Text
from datetime import datetime, timezone
from app.database.session import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    source = Column(String, nullable=False) # PART_1, PART_2, PART_3
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    exam_id = Column(String, nullable=False)
    camera_id = Column(String, nullable=True)
    track_ids = Column(Text, nullable=False) # JSON array of track_ids e.g. ["T17"]
    seat_ids = Column(Text, nullable=True) # JSON array of seat_ids e.g. ["B4"]
    event_type = Column(String, nullable=False, index=True) # NEIGHBOUR_GAZE, TORSO_ROTATE, UNUSUAL_HAND_MOVEMENT, PHONE_DETECTED, etc.
    severity = Column(String, default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    confidence = Column(Float, default=0.85)
    visibility_context = Column(Float, default=0.90)
    metadata_json = Column(Text, nullable=True) # Serialized additional JSON metadata
