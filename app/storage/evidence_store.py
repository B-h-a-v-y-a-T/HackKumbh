"""
Evidence Store — Manages evidence clips and file storage.

Provides secure local IDs rather than exposing filesystem paths.
Evidence clips are only saved when retention is enabled.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class EvidenceStore:
    """
    Manages evidence clip storage with secure identifiers.

    - Generates secure clip IDs (not filesystem paths).
    - Respects retention settings.
    - Provides file management for evidence clips.
    """

    def __init__(
        self,
        storage_path: str = "data/evidence",
        retention_enabled: bool = True,
        retention_hours: int = 24,
    ) -> None:
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._retention_enabled = retention_enabled
        self._retention_hours = retention_hours

    def generate_clip_id(self, alert_id: str, timestamp: float) -> str:
        """Generate a secure clip identifier (not a filesystem path)."""
        raw = f"{alert_id}_{timestamp}_{time.time()}"
        return f"EC_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    def get_clip_path(self, clip_id: str) -> Path:
        """Get the internal filesystem path for a clip (not exposed in API)."""
        return self._storage_path / f"{clip_id}.mp4"

    def save_clip(
        self,
        clip_id: str,
        video_data: bytes,
    ) -> Optional[dict]:
        """
        Save an evidence clip.

        Returns clip metadata, or None if retention is disabled.
        """
        if not self._retention_enabled:
            logger.debug("Evidence retention disabled, clip not saved")
            return None

        clip_path = self.get_clip_path(clip_id)
        clip_path.write_bytes(video_data)

        created_at = time.time()
        expires_at = created_at + (self._retention_hours * 3600)

        logger.info(f"Saved evidence clip {clip_id} ({len(video_data)} bytes)")
        return {
            "clip_id": clip_id,
            "size_bytes": len(video_data),
            "created_at": created_at,
            "retention_expires_at": expires_at,
        }

    def get_clip(self, clip_id: str) -> Optional[bytes]:
        """Retrieve evidence clip data by ID."""
        clip_path = self.get_clip_path(clip_id)
        if clip_path.exists():
            return clip_path.read_bytes()
        return None

    def delete_clip(self, clip_id: str) -> bool:
        """Delete an evidence clip."""
        clip_path = self.get_clip_path(clip_id)
        if clip_path.exists():
            clip_path.unlink()
            logger.info(f"Deleted evidence clip {clip_id}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """Delete expired evidence clips. Returns count deleted."""
        count = 0
        now = time.time()
        for f in self._storage_path.glob("EC_*.mp4"):
            # Check file age
            age_hours = (now - f.stat().st_mtime) / 3600
            if age_hours > self._retention_hours:
                f.unlink()
                count += 1
        if count:
            logger.info(f"Cleaned up {count} expired evidence clips")
        return count

    def update_config(
        self,
        retention_enabled: Optional[bool] = None,
        retention_hours: Optional[int] = None,
    ) -> None:
        if retention_enabled is not None:
            self._retention_enabled = retention_enabled
        if retention_hours is not None:
            self._retention_hours = retention_hours
