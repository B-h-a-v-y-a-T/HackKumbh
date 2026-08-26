from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.coverage_service import CoverageService

router = APIRouter(prefix="/coverage", tags=["Camera Coverage & Pre-exam Report"])

@router.get("")
def get_coverage_report(exam_id: str = "EXAM_001", db: Session = Depends(get_db)):
    return CoverageService.get_coverage_report(db, exam_id)
