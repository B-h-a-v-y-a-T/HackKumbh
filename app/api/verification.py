"""
Verification API endpoints.

POST /verification/run       — Queue retrospective verification job
GET  /verification/{job_id}  — Check job status/progress/results
"""

from __future__ import annotations

import logging
import uuid

import json

from fastapi import APIRouter, HTTPException

from app.schemas.verification import VerificationJobResponse, VerificationRunRequest
from app.storage import database as db
from app.workers.verification_worker import get_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post("/run", response_model=VerificationJobResponse)
async def run_verification(request: VerificationRunRequest):
    """
    Queue a retrospective verification job.

    Returns immediately with a job_id. The verification runs
    asynchronously and never blocks live ROI detection.
    """
    job_id = f"V{uuid.uuid4().hex[:8].upper()}"

    worker = get_worker()
    await worker.submit_job(
        job_id=job_id,
        video_path=request.video_path,
        start_time=request.start_time,
        end_time=request.end_time,
        camera_id=request.camera_id,
        track_ids=request.track_ids,
        roi_metadata=request.roi_metadata,
    )

    return VerificationJobResponse(
        job_id=job_id,
        status="QUEUED",
        progress=0.0,
        video_path=request.video_path,
        start_time=request.start_time,
        end_time=request.end_time,
    )


@router.get("/{job_id}", response_model=VerificationJobResponse)
async def get_verification_status(job_id: str):
    """Get the status and progress of a verification job."""
    job = await db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return VerificationJobResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job.get("progress", 0.0),
        video_path=job.get("video_path"),
        start_time=job.get("start_time"),
        end_time=job.get("end_time"),
        events_found=job.get("events_found", 0),
        error_message=job.get("error_message"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
        result_data=json.loads(job["result_data"]) if job.get("result_data") else None,
    )
