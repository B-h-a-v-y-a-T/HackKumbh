from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.privacy_service import PrivacyService
from app.models.audit_log import AuditLog
import json

router = APIRouter(prefix="/privacy", tags=["Privacy Management"])

@router.get("/status")
def get_privacy_status():
    return PrivacyService.get_privacy_audit_status()

@router.get("/audit")
def get_privacy_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(50).all()
    results = []
    for l in logs:
        results.append({
            "id": l.id,
            "timestamp": l.timestamp.isoformat(),
            "action": l.action,
            "actor": l.actor,
            "resource": l.resource,
            "metadata": json.loads(l.metadata_json) if l.metadata_json else {}
        })
    return results
