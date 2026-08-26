"""
Retrospective Verification Pipeline — Full async verification flow.

Pipeline:
    Video file → frame sampling → temporal scanning (VideoMAE V2-L)
    → rank suspicious windows → select top-K → RT-DETRv4-L + ViTPose++-L
    → cross-check → evidence generation

Runs entirely in background worker. NEVER blocks the live pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import numpy as np

from app.config import get_settings
from app.models.base import ModelRegistry
from app.schemas.common import VerificationStatus
from app.schemas.evidence import EvidenceEvent
from app.storage import database as db
from app.verification.comparator import LiveRetroComparator
from app.verification.evidence import EvidenceGenerator
from app.verification.temporal_ranker import TemporalRanker
from app.verification.verifier import HighAccuracyVerifier
from app.verification.video_buffer import VideoBuffer

logger = logging.getLogger(__name__)


class RetrospectivePipeline:
    """
    Orchestrates the full retrospective verification flow.

    This pipeline is designed to run asynchronously and never block
    the live ROI detection pipeline.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._ranker = TemporalRanker(
            top_k=settings.temporal_top_k_windows,
            anomaly_threshold=settings.temporal_anomaly_threshold,
            scan_window_seconds=settings.temporal_scan_window_seconds,
            scan_stride_seconds=settings.temporal_scan_stride_seconds,
        )
        self._verifier = HighAccuracyVerifier()
        self._comparator = LiveRetroComparator()
        self._evidence_gen = EvidenceGenerator(
            clip_pre_seconds=settings.evidence_clip_pre_seconds,
            clip_post_seconds=settings.evidence_clip_post_seconds,
        )
        self._sample_fps = settings.verification_frame_sample_fps

    async def run(
        self,
        job_id: str,
        video_path: str,
        start_time: float,
        end_time: float,
        camera_id: Optional[str] = None,
        track_ids: Optional[List[str]] = None,
        roi_metadata: Optional[List[Dict]] = None,
    ) -> List[EvidenceEvent]:
        """
        Run the full retrospective verification pipeline.

        Args:
            job_id: Job identifier for progress tracking.
            video_path: Path to video file.
            start_time: Start of verification window (seconds).
            end_time: End of verification window (seconds).
            camera_id: Camera identifier.
            track_ids: Optional filter for specific tracks.

        Returns:
            List of evidence events found.
        """
        cam_id = camera_id or "CAM_UNKNOWN"
        evidence_events = []

        try:
            # Phase 1: Extract frames (20% progress)
            await db.update_job_progress(job_id, 0.1)
            logger.info(f"Job {job_id}: Extracting frames from {video_path}")

            video = VideoBuffer(video_path)
            video.open()

            frames = video.extract_frames(start_time, end_time, self._sample_fps)
            if not frames:
                logger.warning(f"Job {job_id}: No frames extracted")
                await db.update_job_status(job_id, "COMPLETED")
                video.close()
                return []

            await db.update_job_progress(job_id, 0.2)

            # Phase 2: Temporal scanning with VideoMAE V2-L (50% progress)
            logger.info(f"Job {job_id}: Running temporal scanning on {len(frames)} frames")
            temporal_windows = self._ranker.scan_video_frames(frames)
            await db.update_job_progress(job_id, 0.5)

            # Phase 3: Rank and select suspicious windows
            suspicious = self._ranker.rank_windows(temporal_windows)
            logger.info(f"Job {job_id}: Found {len(suspicious)} suspicious windows")

            if not suspicious:
                await db.update_job_progress(job_id, 1.0, 0)
                video.close()
                return []

            # Phase 4: High-accuracy verification (80% progress)
            total_suspicious = len(suspicious)
            for i, window in enumerate(suspicious):
                logger.info(
                    f"Job {job_id}: Verifying window {i+1}/{total_suspicious} "
                    f"({window.window_start:.1f}s-{window.window_end:.1f}s, "
                    f"anomaly={window.temporal_anomaly_score:.3f})"
                )

                # Extract frames for this window
                window_frames = video.extract_frames(
                    window.window_start, window.window_end, self._sample_fps
                )
                frame_images = [f for _, f in window_frames]

                if not frame_images:
                    continue

                # Run RT-DETR + ViTPose verification
                verification = self._verifier.verify_window(frame_images)

                # Create evidence if verification found something
                if verification["verification_confidence"] > 0.3:
                    t_ids = track_ids or ["T_UNKNOWN"]
                    
                    # Extract seat_ids from roi_metadata if provided
                    s_ids = []
                    if roi_metadata:
                        for track_id in t_ids:
                            for roi in roi_metadata:
                                if roi.get("track_id") == track_id and "seat_id" in roi:
                                    s_ids.append(roi["seat_id"])
                    
                    evidence = self._evidence_gen.create_retrospective_evidence(
                        track_ids=t_ids,
                        camera_id=cam_id,
                        start_time=window.window_start,
                        end_time=window.window_end,
                        detections=verification["object_detections"],
                        pose_evidence=verification["pose_evidence"],
                        temporal_anomaly_score=window.temporal_anomaly_score,
                        verification_confidence=verification["verification_confidence"],
                        status=VerificationStatus.NEW_EVENT,
                        events=verification.get("notes", []),
                        seat_ids=s_ids,
                    )
                    evidence_events.append(evidence)

                    # Save to database
                    await db.save_evidence(evidence.model_dump())

                progress = 0.5 + (0.3 * (i + 1) / total_suspicious)
                await db.update_job_progress(job_id, progress, len(evidence_events))

            video.close()

            # Phase 5: Finalize (100%)
            await db.update_job_progress(job_id, 1.0, len(evidence_events))
            logger.info(f"Job {job_id}: Completed. Found {len(evidence_events)} evidence events.")

            return evidence_events

        except Exception as e:
            logger.error(f"Job {job_id}: Pipeline error: {e}")
            await db.update_job_status(job_id, "FAILED", str(e))
            raise
