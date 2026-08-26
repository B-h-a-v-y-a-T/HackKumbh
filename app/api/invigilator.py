"""
Invigilator API — Human-in-the-loop decision recording and audit log.

The invigilator (human proctor) is ALWAYS the final decision-maker.
This system never produces automatic cheating verdicts.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/invigilator", tags=["invigilator"])

# In-memory audit log (also persisted to database in production)
_audit_log: List[dict] = []


class InvigilatorDecisionRequest(BaseModel):
    """Human invigilator action."""
    action_id: str = Field(..., description="Unique action identifier")
    track_id: Optional[str] = Field(None, description="Anonymous track identifier")
    group_id: Optional[str] = Field(None, description="Group identifier")
    action_type: str = Field(
        ...,
        description="ACKNOWLEDGE, MARK_NATURAL, FLAG_IN_PERSON, DISMISS, ESCALATE"
    )
    notes: Optional[str] = Field(None, description="Invigilator notes")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)


@router.post("/decision")
async def record_decision(decision: InvigilatorDecisionRequest):
    """Record an invigilator's decision in the audit log."""
    entry = decision.model_dump()
    _audit_log.append(entry)

    # Also persist to database
    try:
        from app.storage import database as db
        await db.save_invigilator_decision(entry)
    except Exception as e:
        logger.warning("Could not persist decision to database: %s", e)

    logger.info(
        "Invigilator action: %s  track=%s  group=%s",
        decision.action_type, decision.track_id, decision.group_id,
    )
    return {"status": "RECORDED", "total": len(_audit_log)}


@router.get("/decisions")
async def get_decisions():
    """Retrieve the invigilator audit log."""
    return {"audit_log": _audit_log}


@router.get("/decisions/count")
async def get_decision_count():
    """Get the count of decisions by type."""
    from collections import Counter
    counts = Counter(d.get("action_type", "UNKNOWN") for d in _audit_log)
    return {"counts": dict(counts), "total": len(_audit_log)}
