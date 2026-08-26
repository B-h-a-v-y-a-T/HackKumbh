"""
Video Analysis REST API Router.

Provides endpoints for asynchronous uploaded video processing,
progress monitoring, and event timeline retrieval.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.pipeline.video_analyzer import VideoAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["Unified Video Analysis"])


class StartAnalysisRequest(BaseModel):
    video_filename: str = Field(..., description="Name of video file in media/ directory")
    start_time_sec: float = Field(0.0, ge=0.0, description="Start timestamp offset in seconds")
    end_time_sec: Optional[float] = Field(None, ge=0.0, description="End timestamp offset in seconds (optional)")
    sample_fps: float = Field(15.0, ge=1.0, le=60.0, description="Inference sampling FPS")


@router.post("/analyze")
def start_video_analysis(req: StartAnalysisRequest):
    """
    Start an asynchronous full-AI analysis job on an uploaded examination video.
    Executes Skeleton Detection + Multi-Person Tracking + Behaviour Engine + High-Res ROI Object Detection.
    """
    service = VideoAnalysisService.get_instance()
    try:
        job_id = service.start_job(
            video_filename=req.video_filename,
            start_time_sec=req.start_time_sec,
            end_time_sec=req.end_time_sec,
            sample_fps=req.sample_fps,
        )
        return {
            "status": "QUEUED",
            "job_id": job_id,
            "video_filename": req.video_filename,
            "message": f"Analysis job started for '{req.video_filename}'."
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to start video analysis job: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/jobs")
def list_analysis_jobs():
    """List all previous and active video analysis jobs."""
    service = VideoAnalysisService.get_instance()
    return {"jobs": service.list_jobs()}


@router.get("/analyze/{job_id}")
def get_job_status(job_id: str):
    """Get live progress, current timestamp, inference FPS, or completed report for a job."""
    service = VideoAnalysisService.get_instance()
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")
    return job


@router.get("/analyze/results/{video_filename}")
def get_video_analysis_results(video_filename: str):
    """Retrieve full analysis report, event timeline, and tracked students for a video."""
    service = VideoAnalysisService.get_instance()
    results = service.get_results_for_video(video_filename)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results found for '{video_filename}'. Start an analysis job first."
        )
    return results
