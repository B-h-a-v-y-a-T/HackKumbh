from sqlalchemy import Column, String, Float, ForeignKey
from app.database.session import Base

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, index=True)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    camera_name = Column(String, nullable=False)
    status = Column(String, default="ONLINE") # ONLINE, OFFLINE, DEGRADED
    coverage_score = Column(Float, default=0.95)
    location = Column(String, nullable=True)
