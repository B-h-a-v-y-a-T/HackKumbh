"""
Evidence API endpoint.

GET /evidence/{alert_id} — Retrieve structured evidence by alert ID
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException

from app.schemas.evidence import EvidenceResponse
from app.storage import database as db

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/", response_model=List[Dict[str, Any]])
async def list_evidence_events(camera_id: Optional[str] = None, limit: int = 100):
    """
    List all generated evidence events.
    Includes time windows, objects, and seat numbers involved.
    """
    events = await db.list_evidence(camera_id=camera_id, limit=limit)
    return events


@router.get("/{alert_id}")
async def get_evidence(alert_id: str):
    """
    Retrieve structured evidence by alert ID.

    Evidence always includes human_review_required=True.
    This system never produces automatic cheating verdicts.
    """
    evidence = await db.get_evidence(alert_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {alert_id}")

    return {
        "event": evidence,
        "human_review_required": True,
        "note": "This is evidence for human review. No automatic verdict is produced.",
    }
