"""
SQLite database for evidence metadata and job tracking.

Uses aiosqlite for async operations. No PII stored — only anonymous IDs.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

_db_path: Optional[str] = None
_db: Optional[aiosqlite.Connection] = None


async def init_database(db_path: str) -> None:
    """Initialize the database and create tables."""
    global _db_path, _db
    _db_path = db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS evidence_events (
            alert_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            track_ids TEXT NOT NULL,
            seat_ids TEXT DEFAULT '',
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            events TEXT DEFAULT '[]',
            objects TEXT DEFAULT '[]',
            pose_confidence REAL DEFAULT 0.0,
            verification_confidence REAL DEFAULT 0.0,
            temporal_anomaly_score REAL DEFAULT 0.0,
            status TEXT DEFAULT 'NO_CHANGE',
            source TEXT DEFAULT 'live',
            evidence_clip_id TEXT,
            image_quality REAL,
            low_visibility INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            expires_at REAL
        );

        CREATE TABLE IF NOT EXISTS verification_jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'QUEUED',
            progress REAL DEFAULT 0.0,
            video_path TEXT,
            start_time REAL,
            end_time REAL,
            events_found INTEGER DEFAULT 0,
            error_message TEXT,
            created_at REAL NOT NULL,
            completed_at REAL,
            result_data TEXT
        );

        CREATE TABLE IF NOT EXISTS metrics_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            tags TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS student_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            seat_id TEXT DEFAULT 'UNASSIGNED',
            timestamp REAL NOT NULL,
            risk_score INTEGER DEFAULT 0,
            behaviour_events TEXT DEFAULT '[]',
            group_id TEXT,
            visibility REAL DEFAULT 1.0,
            data TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS behaviour_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            seat_id TEXT,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            risk_score INTEGER DEFAULT 0,
            group_id TEXT,
            data TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS group_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            participants TEXT NOT NULL,
            seat_ids TEXT DEFAULT '[]',
            group_risk INTEGER DEFAULT 0,
            data TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS invigilator_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT NOT NULL,
            track_id TEXT,
            group_id TEXT,
            action_type TEXT NOT NULL,
            notes TEXT,
            timestamp REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_created
            ON evidence_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_evidence_camera
            ON evidence_events(camera_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON verification_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_student_states_track
            ON student_states(track_id);
        CREATE INDEX IF NOT EXISTS idx_behaviour_events_track
            ON behaviour_events(track_id);
        CREATE INDEX IF NOT EXISTS idx_invigilator_action
            ON invigilator_decisions(action_id);
    """)
    await _db.commit()
    logger.info(f"Database initialized at {db_path}")


async def get_db() -> aiosqlite.Connection:
    """Get the database connection."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


async def close_database() -> None:
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


# --- Evidence Operations ---

async def save_evidence(evidence: Dict[str, Any]) -> None:
    """Save an evidence event to the database."""
    db = await get_db()
    import json
    await db.execute(
        """INSERT OR REPLACE INTO evidence_events
           (alert_id, camera_id, track_ids, seat_ids, start_time, end_time,
            events, objects, pose_confidence, verification_confidence,
            temporal_anomaly_score, status, source, evidence_clip_id,
            image_quality, low_visibility, created_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            evidence["alert_id"],
            evidence["camera_id"],
            json.dumps(evidence.get("track_ids", [])),
            json.dumps(evidence.get("seat_ids", [])),
            evidence["start_time"],
            evidence["end_time"],
            json.dumps(evidence.get("events", [])),
            json.dumps(evidence.get("objects", [])),
            evidence.get("pose_confidence", 0.0),
            evidence.get("verification_confidence", 0.0),
            evidence.get("temporal_anomaly_score", 0.0),
            evidence.get("status", "NO_CHANGE"),
            evidence.get("source", "live"),
            evidence.get("evidence_clip_id"),
            evidence.get("image_quality"),
            1 if evidence.get("low_visibility") else 0,
            evidence.get("created_at", time.time()),
            evidence.get("expires_at"),
        ),
    )
    await db.commit()


async def get_evidence(alert_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an evidence event by alert ID."""
    db = await get_db()
    import json
    cursor = await db.execute(
        "SELECT * FROM evidence_events WHERE alert_id = ?", (alert_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    d = dict(row)
    d["track_ids"] = json.loads(d["track_ids"])
    d["seat_ids"] = json.loads(d["seat_ids"])
    d["events"] = json.loads(d["events"])
    d["objects"] = json.loads(d["objects"])
    d["low_visibility"] = bool(d["low_visibility"])
    return d


async def list_evidence(
    camera_id: Optional[str] = None, limit: int = 100
) -> List[Dict[str, Any]]:
    """List evidence events, optionally filtered by camera."""
    db = await get_db()
    import json
    if camera_id:
        cursor = await db.execute(
            "SELECT * FROM evidence_events WHERE camera_id = ? ORDER BY created_at DESC LIMIT ?",
            (camera_id, limit),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM evidence_events ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["track_ids"] = json.loads(d["track_ids"])
        d["seat_ids"] = json.loads(d["seat_ids"])
        d["events"] = json.loads(d["events"])
        d["objects"] = json.loads(d["objects"])
        d["low_visibility"] = bool(d["low_visibility"])
        results.append(d)
    return results


# --- Job Operations ---

async def save_job(job: Dict[str, Any]) -> None:
    """Save or update a verification job."""
    db = await get_db()
    import json
    await db.execute(
        """INSERT OR REPLACE INTO verification_jobs
           (job_id, status, progress, video_path, start_time, end_time,
            events_found, error_message, created_at, completed_at, result_data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["job_id"],
            job["status"],
            job.get("progress", 0.0),
            job.get("video_path"),
            job.get("start_time"),
            job.get("end_time"),
            job.get("events_found", 0),
            job.get("error_message"),
            job.get("created_at", time.time()),
            job.get("completed_at"),
            json.dumps(job.get("result_data")) if job.get("result_data") else None,
        ),
    )
    await db.commit()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a verification job by ID."""
    db = await get_db()
    import json
    cursor = await db.execute(
        "SELECT * FROM verification_jobs WHERE job_id = ?", (job_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("result_data"):
        d["result_data"] = json.loads(d["result_data"])
    return d


async def update_job_progress(
    job_id: str, progress: float, events_found: int = 0
) -> None:
    """Update job progress."""
    db = await get_db()
    await db.execute(
        "UPDATE verification_jobs SET progress = ?, events_found = ? WHERE job_id = ?",
        (progress, events_found, job_id),
    )
    await db.commit()


async def update_job_status(
    job_id: str, status: str, error_message: Optional[str] = None
) -> None:
    """Update job status."""
    db = await get_db()
    completed = time.time() if status in ("COMPLETED", "FAILED") else None
    await db.execute(
        """UPDATE verification_jobs
           SET status = ?, error_message = ?, completed_at = ?
           WHERE job_id = ?""",
        (status, error_message, completed, job_id),
    )
    await db.commit()


# --- Cleanup ---

async def cleanup_expired_evidence() -> int:
    """Remove expired evidence. Returns count of deleted records."""
    db = await get_db()
    now = time.time()
    cursor = await db.execute(
        "DELETE FROM evidence_events WHERE expires_at IS NOT NULL AND expires_at < ?",
        (now,),
    )
    await db.commit()
    return cursor.rowcount


# --- Invigilator Decision Operations ---

async def save_invigilator_decision(decision: Dict[str, Any]) -> None:
    """Save an invigilator decision into the audit log table."""
    db = await get_db()
    await db.execute(
        """INSERT INTO invigilator_decisions (action_id, track_id, group_id, action_type, notes, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            decision["action_id"],
            decision.get("track_id"),
            decision.get("group_id"),
            decision["action_type"],
            decision.get("notes"),
            decision.get("timestamp_ms", time.time() * 1000) / 1000.0,
        ),
    )
    await db.commit()


async def get_invigilator_decisions(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve invigilator decisions audit log."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM invigilator_decisions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Real-Time State Logging ---

async def save_student_state(record: Dict[str, Any]) -> None:
    """Log an anonymous student state snapshot."""
    import json
    db = await get_db()
    await db.execute(
        """INSERT INTO student_states (camera_id, track_id, seat_id, timestamp, risk_score, behaviour_events, group_id, visibility, data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.get("camera_id", "CAM_01"),
            record["track_id"],
            record.get("seat_id", "UNASSIGNED"),
            record.get("timestamp", time.time()),
            record.get("risk_score", 0),
            json.dumps(record.get("behaviour_events", [])),
            record.get("group_id"),
            record.get("visibility", 1.0),
            json.dumps(record.get("data", {})),
        ),
    )
    await db.commit()

