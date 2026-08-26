from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.review import HumanReview

router = APIRouter(prefix="/reviews", tags=["Human Reviews"])

@router.get("")
def list_reviews(db: Session = Depends(get_db)):
    reviews = db.query(HumanReview).order_by(HumanReview.reviewed_at.desc()).all()
    return reviews
