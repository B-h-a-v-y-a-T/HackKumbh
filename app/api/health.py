"""
Health API endpoint.
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import get_settings
from app.models.base import ModelRegistry

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/health")
async def health_check():
    """Service health check with model status and uptime."""
    settings = get_settings()
    registry = ModelRegistry.get_instance()

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "mock_mode": settings.mock_mode,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "model_device": settings.model_device,
        "models": registry.get_status(),
    }
