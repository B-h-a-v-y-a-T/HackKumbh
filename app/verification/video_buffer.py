"""
Video Buffer — Abstraction over video sources.

Supports MP4 files, timestamp-aware seeking, configurable frame sampling,
and subclip extraction. RTSP-compatible interface (file-based for dev).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VideoBuffer:
    """
    Video source abstraction supporting MP4 and RTSP-compatible architecture.

    For development, operates on local video files.
    """

    def __init__(self, video_path: str) -> None:
        self._path = Path(video_path)
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 0
        self._total_frames: int = 0
        self._duration: float = 0
        self._width: int = 0
        self._height: int = 0

    def open(self) -> None:
        """Open the video source."""
        if not self._path.exists():
            raise FileNotFoundError(f"Video not found: {self._path}")
        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise ValueError(f"Cannot open video: {self._path}")
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._duration = self._total_frames / self._fps if self._fps > 0 else 0
        logger.info(
            f"Opened video: {self._path.name} "
            f"({self._width}x{self._height}, {self._fps:.1f}fps, "
            f"{self._duration:.1f}s, {self._total_frames} frames)"
        )

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def resolution(self) -> Tuple[int, int]:
        return self._width, self._height

    def seek_to_time(self, time_sec: float) -> None:
        """Seek to a specific time in seconds."""
        if self._cap is None:
            raise RuntimeError("Video not opened")
        frame_num = int(time_sec * self._fps)
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)

    def read_frame(self) -> Optional[np.ndarray]:
        """Read the next frame."""
        if self._cap is None:
            raise RuntimeError("Video not opened")
        ret, frame = self._cap.read()
        return frame if ret else None

    def get_current_time(self) -> float:
        """Get current position in seconds."""
        if self._cap is None:
            return 0.0
        return self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    def extract_frames(
        self,
        start_time: float,
        end_time: float,
        sample_fps: float = 2.0,
    ) -> List[Tuple[float, np.ndarray]]:
        """
        Extract frames from a time range at a specified sample rate.

        Args:
            start_time: Start time in seconds.
            end_time: End time in seconds.
            sample_fps: Target frames per second to sample.

        Returns:
            List of (timestamp, frame) tuples.
        """
        if self._cap is None:
            raise RuntimeError("Video not opened")

        frames = []
        interval = 1.0 / sample_fps if sample_fps > 0 else 1.0
        current_time = start_time

        self.seek_to_time(start_time)

        while current_time <= end_time:
            self.seek_to_time(current_time)
            frame = self.read_frame()
            if frame is None:
                break
            frames.append((current_time, frame))
            current_time += interval

        logger.debug(
            f"Extracted {len(frames)} frames from {start_time:.1f}s to {end_time:.1f}s "
            f"at {sample_fps:.1f}fps"
        )
        return frames

    def extract_clip(
        self,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> Optional[str]:
        """
        Extract a video subclip using FFmpeg.

        Args:
            start_time: Clip start in seconds.
            end_time: Clip end in seconds.
            output_path: Path to save the clip.

        Returns:
            Output path if successful, None otherwise.
        """
        try:
            duration = end_time - start_time
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-i", str(self._path),
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                logger.info(f"Extracted clip: {output_path}")
                return output_path
            else:
                logger.error(f"FFmpeg error: {result.stderr[:200]}")
                return None
        except FileNotFoundError:
            logger.warning("FFmpeg not found, using OpenCV fallback for clip extraction")
            return self._extract_clip_opencv(start_time, end_time, output_path)
        except Exception as e:
            logger.error(f"Clip extraction failed: {e}")
            return None

    def _extract_clip_opencv(
        self, start_time: float, end_time: float, output_path: str
    ) -> Optional[str]:
        """Fallback clip extraction using OpenCV."""
        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                output_path, fourcc, self._fps, (self._width, self._height)
            )
            self.seek_to_time(start_time)
            while self.get_current_time() <= end_time:
                frame = self.read_frame()
                if frame is None:
                    break
                writer.write(frame)
            writer.release()
            return output_path
        except Exception as e:
            logger.error(f"OpenCV clip extraction failed: {e}")
            return None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
