import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.event import Event
from typing import Optional, List

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("")
def list_events(
    source: Optional[str] = None,
    track_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    if source:
        query = query.filter(Event.source == source)
    if track_id:
        query = query.filter(Event.track_ids.like(f"%{track_id}%"))

    events = query.order_by(Event.timestamp.desc()).limit(limit).all()
    results = []
    for evt in events:
        results.append({
            "event_id": evt.id,
            "source": evt.source,
            "timestamp": evt.timestamp.isoformat(),
            "exam_id": evt.exam_id,
            "camera_id": evt.camera_id,
            "track_ids": json.loads(evt.track_ids) if evt.track_ids else [],
            "seat_ids": json.loads(evt.seat_ids) if evt.seat_ids else [],
            "event_type": evt.event_type,
            "severity": evt.severity,
            "confidence": evt.confidence,
            "visibility_context": evt.visibility_context,
            "metadata": json.loads(evt.metadata_json) if evt.metadata_json else {}
        })
    return results
