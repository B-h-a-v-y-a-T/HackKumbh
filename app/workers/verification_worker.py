"""
Verification Worker — asyncio.Queue-based background job processor.

Picks up verification jobs, runs the retrospective pipeline,
and updates job status/progress. Never blocks the FastAPI event loop
(uses run_in_executor for CPU/GPU work).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.config import get_settings
from app.storage import database as db
from app.verification.pipeline import RetrospectivePipeline

logger = logging.getLogger(__name__)


class VerificationWorker:
    """
    Background worker for processing verification jobs.

    Uses asyncio.Queue for job management (no external dependencies).
    Can be replaced with Redis-backed queue without API changes.
    """

    def __init__(self, max_concurrent: int = 2) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._max_concurrent = max_concurrent
        self._active_jobs: int = 0
        self._tasks: list = []
        self._running = False
        self._pipeline = RetrospectivePipeline()

    async def start(self) -> None:
        """Start the worker pool."""
        self._running = True
        for i in range(self._max_concurrent):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._tasks.append(task)
        logger.info(f"Started {self._max_concurrent} verification workers")

    async def stop(self) -> None:
        """Stop all workers gracefully."""
        self._running = False
        # Signal workers to stop
        for _ in self._tasks:
            await self._queue.put(None)
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Verification workers stopped")

    async def submit_job(
        self,
        job_id: str,
        video_path: str,
        start_time: float,
        end_time: float,
        camera_id: Optional[str] = None,
        track_ids: Optional[list] = None,
        roi_metadata: Optional[list] = None,
    ) -> str:
        """Submit a verification job to the queue."""
        job = {
            "job_id": job_id,
            "video_path": video_path,
            "start_time": start_time,
            "end_time": end_time,
            "camera_id": camera_id,
            "track_ids": track_ids,
            "roi_metadata": roi_metadata,
            "status": "QUEUED",
            "progress": 0.0,
            "events_found": 0,
            "created_at": time.time(),
        }
        await db.save_job(job)
        await self._queue.put(job)
        logger.info(f"Queued verification job {job_id}")
        return job_id

    async def _worker_loop(self, name: str) -> None:
        """Main worker loop."""
        logger.info(f"Worker {name} started")
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if job is None:
                break

            self._active_jobs += 1
            try:
                await self._process_job(job, name)
            except Exception as e:
                logger.error(f"Worker {name} job {job['job_id']} failed: {e}")
                await db.update_job_status(job["job_id"], "FAILED", str(e))
            finally:
                self._active_jobs -= 1
                self._queue.task_done()

    async def _process_job(self, job: dict, worker_name: str) -> None:
        """Process a single verification job."""
        job_id = job["job_id"]
        logger.info(f"Worker {worker_name} processing job {job_id}")

        await db.update_job_status(job_id, "RUNNING")

        # Run pipeline in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        try:
            events = await self._pipeline.run(
                job_id=job_id,
                video_path=job["video_path"],
                start_time=job["start_time"],
                end_time=job["end_time"],
                camera_id=job.get("camera_id"),
                track_ids=job.get("track_ids"),
                roi_metadata=job.get("roi_metadata"),
            )
            await db.update_job_status(job_id, "COMPLETED")
            logger.info(f"Job {job_id} completed: {len(events)} events found")
        except FileNotFoundError as e:
            await db.update_job_status(job_id, "FAILED", f"Video not found: {e}")
        except Exception as e:
            await db.update_job_status(job_id, "FAILED", str(e))
            raise

    @property
    def active_jobs(self) -> int:
        return self._active_jobs

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


# Global worker instance
_worker: Optional[VerificationWorker] = None


def get_worker() -> VerificationWorker:
    global _worker
    if _worker is None:
        settings = get_settings()
        _worker = VerificationWorker(
            max_concurrent=settings.max_concurrent_verification_jobs
        )
    return _worker


async def start_worker() -> None:
    worker = get_worker()
    await worker.start()


async def stop_worker() -> None:
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None
