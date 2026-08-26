"""
Privacy Retention — Configurable cleanup of raw video and evidence.

Default: raw video NOT retained, evidence retained for 24 hours.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RetentionManager:
    """Manages data retention policies for privacy compliance."""

    def __init__(
        self,
        raw_video_retention_enabled: bool = False,
        evidence_retention_enabled: bool = True,
        evidence_retention_hours: int = 24,
        evidence_storage_path: str = "data/evidence",
    ) -> None:
        self._raw_retention = raw_video_retention_enabled
        self._evidence_retention = evidence_retention_enabled
        self._evidence_hours = evidence_retention_hours
        self._evidence_path = Path(evidence_storage_path)
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def raw_video_retention_enabled(self) -> bool:
        return self._raw_retention

    @property
    def evidence_retention_enabled(self) -> bool:
        return self._evidence_retention

    def should_save_clip(self) -> bool:
        """Whether evidence clips should be saved."""
        return self._evidence_retention

    def get_expiry_time(self) -> Optional[float]:
        """Get expiry timestamp for new evidence, or None if no expiry."""
        if not self._evidence_retention:
            return None
        return time.time() + (self._evidence_hours * 3600)

    async def start_cleanup_loop(self, interval_seconds: int = 3600) -> None:
        """Start periodic cleanup of expired data."""
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(interval_seconds)
        )

    async def stop_cleanup_loop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self, interval: int) -> None:
        while True:
            try:
                await asyncio.sleep(interval)
                count = await self.cleanup_expired()
                if count > 0:
                    logger.info(f"Retention cleanup: removed {count} expired items")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retention cleanup error: {e}")

    async def cleanup_expired(self) -> int:
        """Clean up expired evidence files."""
        count = 0
        now = time.time()
        if self._evidence_path.exists():
            for f in self._evidence_path.glob("EC_*"):
                age_hours = (now - f.stat().st_mtime) / 3600
                if age_hours > self._evidence_hours:
                    f.unlink()
                    count += 1
        # Also clean up database entries
        try:
            from app.storage.database import cleanup_expired_evidence
            db_count = await cleanup_expired_evidence()
            count += db_count
        except Exception:
            pass
        return count

    def update_config(self, **kwargs) -> None:
        if "raw_video_retention_enabled" in kwargs:
            self._raw_retention = kwargs["raw_video_retention_enabled"]
        if "evidence_retention_enabled" in kwargs:
            self._evidence_retention = kwargs["evidence_retention_enabled"]
        if "evidence_retention_hours" in kwargs:
            self._evidence_hours = kwargs["evidence_retention_hours"]
