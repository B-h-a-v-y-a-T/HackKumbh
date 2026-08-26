from sqlalchemy import Column, String, Float, Integer, ForeignKey
from app.database.session import Base

class Seat(Base):
    __tablename__ = "seats"

    id = Column(String, primary_key=True, index=True)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    seat_label = Column(String, nullable=False, index=True) # e.g. B4
    row = Column(String, nullable=False) # e.g. B
    column = Column(Integer, nullable=False) # e.g. 4
    visibility_status = Column(String, default="GOOD") # GOOD, PARTIAL, POOR, BLIND_SPOT
    visibility_score = Column(Float, default=0.90) # 0.0 to 1.0
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=True)
