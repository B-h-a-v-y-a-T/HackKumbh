from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.exam import Exam

router = APIRouter(prefix="/exams", tags=["Exams"])

@router.get("")
def list_exams(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    if not exams:
        return [{
            "id": "EXAM_001",
            "name": "Semester Final Examination - CS401",
            "start_time": "2026-08-19T09:00:00Z",
            "end_time": "2026-08-19T12:00:00Z",
            "status": "ACTIVE",
            "total_seats": 120,
            "total_cameras": 8,
            "description": "Final examination hall monitoring session."
        }]
    return exams

@router.get("/{exam_id}")
def get_exam(exam_id: str, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam and exam_id == "EXAM_001":
        return {
            "id": "EXAM_001",
            "name": "Semester Final Examination - CS401",
            "start_time": "2026-08-19T09:00:00Z",
            "end_time": "2026-08-19T12:00:00Z",
            "status": "ACTIVE",
            "total_seats": 120,
            "total_cameras": 8,
            "description": "Final examination hall monitoring session."
        }
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam
