import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.alert import Alert
from app.models.review import HumanReview
from app.models.audit_log import AuditLog
from app.models.event import Event
from app.schemas.alert import AlertReviewRequest
from app.core.websocket_manager import manager
from typing import Optional
from datetime import datetime, timezone

router = APIRouter(prefix="/alerts", tags=["Alerts"])

def _format_alert(a: Alert, db: Optional[Session] = None):
    explainability = json.loads(a.explainability_json) if a.explainability_json else None
    behaviours = json.loads(a.observed_behaviours) if a.observed_behaviours else []
    
    latest_review = None
    if db:
        rev = db.query(HumanReview).filter(HumanReview.alert_id == a.id).order_by(HumanReview.reviewed_at.desc()).first()
        if rev:
            latest_review = {
                "id": rev.id,
                "decision": rev.decision,
                "notes": rev.notes,
                "reviewer_id": rev.reviewer_id,
                "reviewed_at": rev.reviewed_at.isoformat()
            }

    return {
        "id": a.id,
        "exam_id": a.exam_id,
        "track_id": a.track_id,
        "seat_id": a.seat_id,
        "risk_score": a.risk_score,
        "peak_risk": a.peak_risk,
        "priority": a.priority,
        "status": a.status,
        "confidence": a.confidence,
        "observed_behaviours": behaviours,
        "duration_sec": round(a.duration_sec, 1),
        "low_visibility_flag": a.low_visibility_flag,
        "verification_status": a.verification_status,
        "group_id": a.group_id,
        "object_detected": a.object_detected,
        "explainability": explainability,
        "latest_review": latest_review,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat()
    }

@router.get("")
def list_alerts(priority: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Alert)
    if priority:
        query = query.filter(Alert.priority == priority.upper())
    if status:
        query = query.filter(Alert.status == status.upper())

    alerts = query.order_by(Alert.updated_at.desc()).all()
    return [_format_alert(a, db) for a in alerts]

@router.get("/{alert_id}")
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _format_alert(alert, db)

@router.post("/{alert_id}/review")
async def review_alert(alert_id: str, payload: AlertReviewRequest, db: Session = Depends(get_db)):
    """
    Submits human invigilator review decision: CONFIRM_FOR_REVIEW, DISMISS, UNSURE.
    Persists HumanReview, AuditLog, and Human Review Event. Updates alert status.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    decision = payload.decision.upper()
    if decision not in ["CONFIRM_FOR_REVIEW", "DISMISS", "UNSURE"]:
        raise HTTPException(status_code=400, detail="Decision must be CONFIRM_FOR_REVIEW, DISMISS, or UNSURE")

    # Clear lifecycle mapping:
    # CONFIRM_FOR_REVIEW -> CONFIRMED_FOR_REVIEW
    # DISMISS -> DISMISSED
    # UNSURE -> UNSURE
    if decision == "CONFIRM_FOR_REVIEW":
        alert.status = "CONFIRMED_FOR_REVIEW"
    elif decision == "DISMISS":
        alert.status = "DISMISSED"
    else:
        alert.status = "UNSURE"

    now_dt = datetime.now(timezone.utc)
    alert.updated_at = now_dt

    # 1. Save HumanReview record
    review_record = HumanReview(
        id=f"REV_{int(now_dt.timestamp() * 1000)}",
        alert_id=alert.id,
        decision=decision,
        notes=payload.notes or "",
        reviewer_id=payload.reviewer_id,
        reviewed_at=now_dt
    )
    db.add(review_record)

    # 2. Save Audit Log
    audit = AuditLog(
        id=f"AUD_{int(now_dt.timestamp() * 1000)}",
        timestamp=now_dt,
        action=f"REVIEW_ALERT_{decision}",
        actor=payload.reviewer_id,
        resource=f"Alert {alert.id} (Track {alert.track_id})",
        metadata_json=json.dumps({"decision": decision, "notes": payload.notes})
    )
    db.add(audit)

    # 3. Save Human Review Event into events table for Ticker & Timeline synchronization
    summary_msg = f"Invigilator decision: {decision}. Note: '{payload.notes}'" if payload.notes else f"Invigilator decision: {decision}"
    evt_severity = "LOW" if decision == "DISMISS" else ("HIGH" if decision == "CONFIRM_FOR_REVIEW" else "MEDIUM")
    
    review_evt = Event(
        id=f"EVT_REV_{int(now_dt.timestamp() * 1000)}",
        source="HUMAN_REVIEW",
        exam_id=alert.exam_id,
        camera_id=alert.seat_id,
        track_ids=json.dumps([alert.track_id]),
        seat_ids=json.dumps([alert.seat_id]) if alert.seat_id else json.dumps([]),
        event_type=f"HUMAN_REVIEW_{decision}",
        severity=evt_severity,
        confidence=1.0,
        visibility_context=1.0,
        metadata_json=json.dumps({
            "decision": decision,
            "notes": payload.notes,
            "reviewer_id": payload.reviewer_id,
            "alert_id": alert.id,
            "summary": summary_msg,
            "details": summary_msg
        }),
        timestamp=now_dt
    )
    db.add(review_evt)

    db.commit()
    db.refresh(alert)

    formatted_alert = _format_alert(alert, db)
    formatted_evt = {
        "event_id": review_evt.id,
        "source": review_evt.source,
        "timestamp": review_evt.timestamp.isoformat(),
        "exam_id": review_evt.exam_id,
        "camera_id": review_evt.camera_id,
        "track_ids": [alert.track_id],
        "seat_ids": [alert.seat_id] if alert.seat_id else [],
        "event_type": review_evt.event_type,
        "severity": review_evt.severity,
        "confidence": 1.0,
        "visibility_context": 1.0,
        "metadata": {
            "decision": decision,
            "notes": payload.notes,
            "summary": summary_msg
        }
    }

    # Broadcast WebSocket updates
    await manager.broadcast({
        "type": "ALERT_REVIEWED",
        "alert_id": alert.id,
        "alert": formatted_alert,
        "status": alert.status,
        "decision": decision,
        "notes": payload.notes
    })

    await manager.broadcast({
        "type": "EVENT_NEW",
        "data": formatted_evt
    })

    return {
        "status": "success",
        "alert": formatted_alert,
        "alert_id": alert.id,
        "new_status": alert.status,
        "decision": decision,
        "notes": payload.notes
    }

