"""
Live Perception API — REST endpoints for Part 1 & Part 4 functionality.

Provides:
  - System status
  - Source selection (mock/video/live)
  - Video upload
  - Scenario selection
  - MJPEG live stream feed
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])

# Paths
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


# ── Request Models ─────────────────────────────────────────────────────────
class SelectSourceRequest(BaseModel):
    mode: str  # "video", "live", "mock"
    video_path: Optional[str] = None
    camera_index: int = 0


class SelectScenarioRequest(BaseModel):
    scenario_id: str


# ── Status ─────────────────────────────────────────────────────────────────
@router.get("/status")
async def get_status():
    """System status including privacy guarantees."""
    from app.pipeline.worker import get_worker
    worker = get_worker()
    return {
        "status": "ONLINE",
        "system_name": "CopyCop — AI Examination Monitoring",
        "version": "1.0.0",
        "source_mode": worker.source_mode if worker else "mock",
        "privacy_guarantees": {
            "biometrics_stored": False,
            "face_recognition_enabled": False,
            "anonymous_tracking_only": True,
            "decision_maker": "Human Invigilator (Advisory Only)",
            "forbidden_labels": ["Cheating"],
        },
        "fps_actual": round(worker.fps_actual, 1) if worker else 0.0,
    }


# ── Source Selection ───────────────────────────────────────────────────────
@router.get("/source")
async def get_source():
    from app.pipeline.worker import get_worker
    worker = get_worker()
    return {
        "mode": worker.source_mode if worker else "mock",
        "video_path": worker.video_path if worker else None,
        "available_modes": ["video", "live", "mock"],
    }


@router.post("/source/select")
async def select_source(req: SelectSourceRequest):
    if req.mode not in ("video", "live", "mock", "client_live"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    from app.pipeline.worker import get_worker
    worker = get_worker()
    if worker:
        worker.set_source(req.mode, req.video_path)
    return {"status": "OK", "mode": req.mode, "video_path": req.video_path}


# ── Video Upload ───────────────────────────────────────────────────────────
@router.post("/video/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.endswith((".mp4", ".webm", ".mov", ".avi", ".mkv")):
        raise HTTPException(status_code=400, detail="Unsupported video format")
    dest = MEDIA_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    logger.info("Uploaded video: %s (%s bytes)", dest, dest.stat().st_size)
    return {
        "status": "uploaded",
        "filename": file.filename,
        "url": f"/media/{file.filename}",
        "size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
    }


@router.get("/videos/list")
async def list_videos():
    feeds = []
    for fname in sorted(os.listdir(MEDIA_DIR)):
        if fname.lower().endswith((".mp4", ".webm", ".mov", ".avi", ".mkv")):
            fpath = MEDIA_DIR / fname
            feeds.append({
                "filename": fname,
                "url": f"/media/{fname}",
                "size_mb": round(fpath.stat().st_size / (1024 * 1024), 2),
            })
    return {"videos": feeds}


# ── Scenarios ──────────────────────────────────────────────────────────────
@router.get("/scenarios")
async def list_scenarios():
    from app.behaviour.mock_generator.scenarios import SCENARIO_PRESETS
    from app.pipeline.worker import get_worker
    worker = get_worker()
    scenarios = [
        {
            "id": sc.id.value,
            "title": sc.title,
            "description": sc.description,
            "expected_outcome": sc.expected_outcome,
        }
        for sc in SCENARIO_PRESETS.values()
    ]
    current = worker.mock_generator.current_scenario.value if worker and hasattr(worker, "mock_generator") else "normal_exam"
    return {"scenarios": scenarios, "current": current}


@router.post("/scenarios/select")
async def select_scenario(req: SelectScenarioRequest):
    from app.behaviour.mock_generator.scenarios import ScenarioType, SCENARIO_PRESETS
    from app.pipeline.worker import get_worker
    try:
        scenario = ScenarioType(req.scenario_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown scenario")
    if scenario not in SCENARIO_PRESETS:
        raise HTTPException(status_code=400, detail="Unknown scenario")
    worker = get_worker()
    if worker and hasattr(worker, "mock_generator"):
        worker.mock_generator.set_scenario(scenario)
    return {"status": "OK", "scenario": req.scenario_id}


# ── MJPEG Stream ──────────────────────────────────────────────────────────
@router.get("/stream/feed")
async def stream_feed():
    """Streams the real-time annotated examination video feed."""
    from app.pipeline.worker import get_worker
    worker = get_worker()

    async def frame_generator():
        last_frame_id = -1
        while True:
            if worker:
                jpeg_bytes, packet, _ = worker.get_latest_frame()
                fid = packet.get("frame_id", 0) if packet else 0
                if jpeg_bytes is not None and fid != last_frame_id:
                    last_frame_id = fid
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                    )
            await asyncio.sleep(0.008)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
