"""
Asynchronous Video Analysis Service & Job Manager.

Executes the unified AI analysis pipeline across uploaded examination video files:
- Skeleton & Pose Estimation (YOLO11-pose)
- Continuous ByteTrack Tracking with persistent track IDs
- Full Behaviour Detection (gaze, turns, torso, hands, leaky risk)
- High-Resolution Student/Desk ROI Object Detection (Phone, Chit, Earbuds)
- Real-time progress reporting, timeline generation, and JSON report caching
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

from app.pipeline.frame_analyzer import CommonFrameAnalyzer

logger = logging.getLogger(__name__)

MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class VideoAnalysisService:
    """
    Manages asynchronous background analysis jobs for uploaded examination videos.
    """

    _instance: Optional[VideoAnalysisService] = None

    @classmethod
    def get_instance(cls) -> VideoAnalysisService:
        if cls._instance is None:
            cls._instance = VideoAnalysisService()
        return cls._instance

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._cached_results: Dict[str, Dict[str, Any]] = {}
        self._analyzer: Optional[CommonFrameAnalyzer] = None
        self._lock = threading.Lock()
        self._load_persisted_results()

    def _get_analyzer(self) -> CommonFrameAnalyzer:
        if self._analyzer is None:
            self._analyzer = CommonFrameAnalyzer()
        return self._analyzer

    def _load_persisted_results(self):
        """Load any previously cached analysis JSON files from media directory."""
        try:
            for fname in os.listdir(MEDIA_DIR):
                if fname.endswith(".analysis.json"):
                    fpath = MEDIA_DIR / fname
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            v_name = data.get("video_filename")
                            if v_name:
                                self._cached_results[v_name] = data
                    except Exception as ex:
                        logger.debug("Could not load cached analysis %s: %s", fname, ex)
        except Exception:
            pass

    def start_job(
        self,
        video_filename: str,
        start_time_sec: float = 0.0,
        end_time_sec: Optional[float] = None,
        sample_fps: float = 15.0,
    ) -> str:
        """
        Start an asynchronous video analysis job.

        Returns:
            job_id: str
        """
        job_id = f"JOB_{uuid.uuid4().hex[:8].upper()}"
        video_path = MEDIA_DIR / video_filename
        if not video_path.exists():
            # Check relative path
            video_path = Path(video_filename)
            if not video_path.exists():
                raise FileNotFoundError(f"Video file '{video_filename}' not found in media repository.")

        job_info = {
            "job_id": job_id,
            "video_filename": video_filename,
            "status": "QUEUED",
            "progress": 0.0,
            "frames_processed": 0,
            "total_frames": 0,
            "elapsed_sec": 0.0,
            "estimated_remaining_sec": 0.0,
            "inference_fps": 0.0,
            "current_timestamp": start_time_sec,
            "current_time_str": "00:00.000",
            "events_count": 0,
            "error": None,
            "created_at": time.time(),
            "completed_at": None,
            "report": None,
            "events": [],
            "tracks": [],
        }

        with self._lock:
            self._jobs[job_id] = job_info

        worker_thread = threading.Thread(
            target=self._run_job,
            args=(job_id, str(video_path), video_filename, start_time_sec, end_time_sec, sample_fps),
            daemon=True,
            name=f"VideoAnalyzer-{job_id}",
        )
        worker_thread.start()

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get live job progress and status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return dict(job)
        return None

    def get_results_for_video(self, video_filename: str) -> Optional[Dict[str, Any]]:
        """Get cached or latest completed analysis results for a video."""
        with self._lock:
            # Check memory cache first
            if video_filename in self._cached_results:
                return self._cached_results[video_filename]

            # Check jobs
            for job in self._jobs.values():
                if job.get("video_filename") == video_filename and job.get("status") == "COMPLETED":
                    return {
                        "job_id": job["job_id"],
                        "video_filename": video_filename,
                        "report": job.get("report"),
                        "events": job.get("events", []),
                        "tracks": job.get("tracks", []),
                    }
        return None

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all video analysis jobs."""
        with self._lock:
            return [dict(j) for j in self._jobs.values()]

    def _run_job(
        self,
        job_id: str,
        video_path_str: str,
        video_filename: str,
        start_time_sec: float,
        end_time_sec: Optional[float],
        sample_fps: float,
    ):
        """Worker thread executing the frame-by-frame analysis loop."""
        logger.info("Starting Video Analysis Job %s for '%s'...", job_id, video_filename)

        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "RUNNING"

        cap = cv2.VideoCapture(video_path_str)
        if not cap.isOpened():
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = "FAILED"
                    self._jobs[job_id]["error"] = f"Failed to open video file at {video_path_str}"
            return

        fps_source = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        total_duration_sec = total_source_frames / fps_source if fps_source > 0 else 0.0

        target_end_sec = end_time_sec if (end_time_sec and end_time_sec < total_duration_sec) else total_duration_sec
        start_frame = int(start_time_sec * fps_source)
        end_frame = int(target_end_sec * fps_source)
        frames_to_process = max(1, end_frame - start_frame)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        analyzer = self._get_analyzer()
        analyzer.risk_engine.reset()  # Clean baseline start

        all_canonical_events: List[Dict[str, Any]] = []
        track_summaries: Dict[str, Dict[str, Any]] = {}
        processed_count = 0
        start_wall_time = time.time()
        last_calc_time = start_wall_time
        fps_counter = 0
        current_fps = 0.0

        frame_step = max(1, int(round(fps_source / sample_fps)))

        curr_frame_idx = start_frame

        try:
            while curr_frame_idx <= end_frame:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                if (curr_frame_idx - start_frame) % frame_step == 0:
                    current_timestamp = curr_frame_idx / fps_source

                    # Run unified frame analyzer
                    res = analyzer.analyze_frame(
                        frame=frame,
                        frame_id=curr_frame_idx,
                        timestamp_sec=current_timestamp,
                        source_id=video_filename,
                        continuous_object_scan=True,
                    )

                    # Accumulate events
                    for evt in res.get("events", []):
                        all_canonical_events.append(evt)

                    # Update track summaries
                    for t in res.get("tracks", []):
                        tid = t.track_id
                        score = t.risk_score
                        if tid not in track_summaries:
                            track_summaries[tid] = {
                                "track_id": tid,
                                "seat_id": t.seat_id or "UNASSIGNED",
                                "peak_risk": score,
                                "current_risk": score,
                                "events_count": len(t.events or []),
                                "events": list(t.events or []),
                                "object_evidence": list(t.object_evidence or []),
                            }
                        else:
                            track_summaries[tid]["peak_risk"] = max(track_summaries[tid]["peak_risk"], score)
                            track_summaries[tid]["current_risk"] = score
                            for e in (t.events or []):
                                if e not in track_summaries[tid]["events"]:
                                    track_summaries[tid]["events"].append(e)
                            for obj in (t.object_evidence or []):
                                if obj not in track_summaries[tid]["object_evidence"]:
                                    track_summaries[tid]["object_evidence"].append(obj)

                    processed_count += 1
                    fps_counter += 1
                    now = time.time()
                    if now - last_calc_time >= 0.5:
                        current_fps = round(fps_counter / (now - last_calc_time), 1)
                        fps_counter = 0
                        last_calc_time = now

                    elapsed = now - start_wall_time
                    progress = min(0.99, (curr_frame_idx - start_frame) / frames_to_process)
                    est_total_time = (elapsed / max(0.01, progress)) if progress > 0.05 else 0.0
                    remaining = max(0.0, est_total_time - elapsed)

                    # Update progress in state
                    with self._lock:
                        if job_id in self._jobs:
                            self._jobs[job_id].update({
                                "progress": round(progress, 3),
                                "frames_processed": processed_count,
                                "total_frames": frames_to_process // frame_step,
                                "elapsed_sec": round(elapsed, 1),
                                "estimated_remaining_sec": round(remaining, 1),
                                "inference_fps": current_fps,
                                "current_timestamp": round(current_timestamp, 3),
                                "current_time_str": res.get("time_str", "00:00.000"),
                                "events_count": len(all_canonical_events),
                            })

                curr_frame_idx += 1

            cap.release()

            # Deduplicate contiguous events for clean review
            deduped_events = self._deduplicate_events(all_canonical_events)

            # Generate comprehensive summary report
            total_elapsed = time.time() - start_wall_time
            behaviour_evts = [e for e in deduped_events if "DETECTED" not in e.get("event_type", "")]
            object_evts = [e for e in deduped_events if "DETECTED" in e.get("event_type", "")]

            sorted_tracks = sorted(track_summaries.values(), key=lambda x: x["peak_risk"], reverse=True)
            highest_risk_tracks = [t["track_id"] for t in sorted_tracks if t["peak_risk"] >= 30]

            report = {
                "video_filename": video_filename,
                "total_duration_sec": round(total_duration_sec, 2),
                "duration_formatted": f"{int(total_duration_sec//60):02d}:{int(total_duration_sec%60):02d}",
                "analysis_wall_time_sec": round(total_elapsed, 2),
                "total_frames_analyzed": processed_count,
                "average_fps": round(processed_count / max(0.1, total_elapsed), 1),
                "students_tracked_count": len(track_summaries),
                "behaviour_events_count": len(behaviour_evts),
                "object_events_count": len(object_evts),
                "total_events_count": len(deduped_events),
                "highest_risk_tracks": highest_risk_tracks[:5],
                "summary": f"Analyzed {processed_count} frames across {len(track_summaries)} candidates. Identified {len(deduped_events)} behavioral & contraband events.",
            }

            final_result = {
                "job_id": job_id,
                "video_filename": video_filename,
                "status": "COMPLETED",
                "progress": 1.0,
                "frames_processed": processed_count,
                "total_frames": processed_count,
                "elapsed_sec": round(total_elapsed, 1),
                "estimated_remaining_sec": 0.0,
                "inference_fps": round(processed_count / max(0.1, total_elapsed), 1),
                "completed_at": time.time(),
                "report": report,
                "events": deduped_events,
                "tracks": sorted_tracks,
            }

            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].update(final_result)
                self._cached_results[video_filename] = final_result

            # Write cache JSON to media directory
            cache_file = MEDIA_DIR / f"{video_filename}.analysis.json"
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(final_result, f, indent=2)
                logger.info("Saved analysis results cache to %s", cache_file)
            except Exception as ex:
                logger.warning("Could not persist analysis cache file: %s", ex)

            logger.info("Video Analysis Job %s COMPLETED successfully in %.2fs (%d events).", job_id, total_elapsed, len(deduped_events))

        except Exception as ex:
            logger.exception("Error during Video Analysis Job %s: %s", job_id, ex)
            cap.release()
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id].update({
                        "status": "FAILED",
                        "error": str(ex),
                    })

    def _deduplicate_events(self, events: List[Dict[str, Any]], window_sec: float = 2.0) -> List[Dict[str, Any]]:
        """Cluster contiguous single-frame detections of the same event into sustained interval events."""
        if not events:
            return []

        events = sorted(events, key=lambda x: x.get("timestamp", 0.0))
        clustered: List[Dict[str, Any]] = []

        for e in events:
            if not clustered:
                c = dict(e)
                c["duration"] = 0.5
                clustered.append(c)
                continue

            last = clustered[-1]
            same_track = (last.get("track_id") == e.get("track_id"))
            same_type = (last.get("event_type") == e.get("event_type"))
            dt = e.get("timestamp", 0.0) - last.get("timestamp", 0.0)

            if same_track and same_type and dt <= window_sec:
                # Merge / extend duration
                last["duration"] = round(dt + 0.5, 2)
                last["risk_score"] = max(last.get("risk_score", 0), e.get("risk_score", 0))
                last["confidence"] = max(last.get("confidence", 0.0), e.get("confidence", 0.0))
            else:
                c = dict(e)
                c["duration"] = 0.5
                clustered.append(c)

        return clustered
