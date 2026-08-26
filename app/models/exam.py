from sqlalchemy import Column, String, DateTime, Integer, Text
from datetime import datetime
from app.database.session import Base

class Exam(Base):
    __tablename__ = "exams"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="ACTIVE") # SCHEDULED, ACTIVE, COMPLETED, PAUSED
    total_seats = Column(Integer, default=120)
    total_cameras = Column(Integer, default=8)
    description = Column(Text, nullable=True)
