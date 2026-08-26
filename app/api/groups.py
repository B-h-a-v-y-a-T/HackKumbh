import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.group import GroupInteraction
from app.integrations.mock_simulator import simulator

router = APIRouter(prefix="/groups", tags=["Group Intelligence"])

@router.get("")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(GroupInteraction).order_by(GroupInteraction.window_end.desc()).all()
    if not groups:
        if simulator.current_stage == 0:
            return []
        # Fallback default group for initial display
        return [{
            "id": "GRP_001",
            "group_id": "G3",
            "exam_id": "EXAM_001",
            "member_tracks": ["T17", "T18", "T19"],
            "group_risk": 84,
            "pattern_description": "Possible coordinated behavioural pattern across adjacent seats (B4, B5, B6).",
            "window_start": "2026-08-19T10:42:18Z",
            "window_end": "2026-08-19T10:42:27Z"
        }]

    results = []
    for g in groups:
        results.append({
            "id": g.id,
            "group_id": g.group_id,
            "exam_id": g.exam_id,
            "member_tracks": json.loads(g.member_tracks) if g.member_tracks else [],
            "group_risk": g.group_risk,
            "pattern_description": g.pattern_description,
            "window_start": g.window_start.isoformat(),
            "window_end": g.window_end.isoformat()
        })
    return results
