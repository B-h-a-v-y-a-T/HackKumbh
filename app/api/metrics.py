"""
Metrics, Models, and Config API endpoints.

GET  /metrics        — Performance and resource metrics
GET  /models         — Loaded models and status
POST /models/reload  — Hot-reload models
GET  /config         — Current configuration
PUT  /config         — Update runtime configuration
"""

from __future__ import annotations

import logging
import time

import psutil
from fastapi import APIRouter

from app.config import get_settings
from app.models.base import ModelRegistry
from app.workers.verification_worker import get_worker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

_request_count = 0
_total_latency = 0.0


def record_request(latency_ms: float) -> None:
    global _request_count, _total_latency
    _request_count += 1
    _total_latency += latency_ms


@router.get("/metrics")
async def get_metrics():
    """Performance and resource metrics."""
    worker = get_worker()
    process = psutil.Process()
    mem = process.memory_info()

    gpu_info = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info = {
                "device": torch.cuda.get_device_name(0),
                "memory_allocated_mb": round(torch.cuda.memory_allocated(0) / 1e6, 1),
                "memory_reserved_mb": round(torch.cuda.memory_reserved(0) / 1e6, 1),
                "utilization": "N/A",
            }
    except Exception:
        pass

    return {
        "requests_total": _request_count,
        "avg_latency_ms": round(_total_latency / max(1, _request_count), 2),
        "active_verification_jobs": worker.active_jobs,
        "queued_verification_jobs": worker.queue_size,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_rss_mb": round(mem.rss / 1e6, 1),
        "memory_vms_mb": round(mem.vms / 1e6, 1),
        "gpu": gpu_info,
    }


@router.get("/models")
async def get_models():
    """Loaded models and their status."""
    registry = ModelRegistry.get_instance()
    settings = get_settings()
    return {
        "mock_mode": settings.mock_mode,
        "device": settings.model_device,
        "models": registry.get_status(),
    }


@router.post("/models/reload")
async def reload_models():
    """Hot-reload all models."""
    settings = get_settings()
    registry = ModelRegistry.get_instance()
    try:
        registry.load_all(settings.model_device)
        return {"status": "ok", "models": registry.get_status()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/config")
async def get_config():
    """Current runtime configuration."""
    settings = get_settings()
    return settings.model_dump()


@router.put("/config")
async def update_config(updates: dict):
    """
    Update runtime configuration.

    Only updates in-memory settings. Does not modify .env file.
    """
    settings = get_settings()
    applied = {}
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
            applied[key] = value
        else:
            logger.warning(f"Unknown config key: {key}")

    return {"status": "ok", "applied": applied}
