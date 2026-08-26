"""
Video source abstraction for camera, RTSP, video file, and mock input.

Handles dropped frames, reconnection, and frame health metrics.
"""

from __future__ import annotations

import logging
import os
import time
from enum import Enum, auto
from typing import Optional, Tuple

import cv2
import numpy as np

from app.perception.core.constants import FrameStatus, StreamStatus
from app.perception.core.data_models import FrameHealth

logger = logging.getLogger(__name__)


class SourceType(Enum):
    WEBCAM = auto()
    RTSP = auto()
    VIDEO_FILE = auto()
    MOCK = auto()


class VideoSource:
    """
    Unified frame acquisition from multiple source types.

    Supports: webcam index, RTSP URL, video file path, or mock/synthetic data.
    Reports frame health (brightness, blur, dropped frames).
    Handles reconnection for RTSP streams.
    """

    def __init__(
        self,
        source: str | int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        camera_id: str = "CAM_01",
        mock_frame_size: Tuple[int, int] = (1280, 720),
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 2.0,
    ):
        self.source = source
        self.target_width = width
        self.target_height = height
        self.target_fps = fps
        self.camera_id = camera_id
        self.mock_frame_size = mock_frame_size
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self._cap: Optional[cv2.VideoCapture] = None
        self._source_type = self._detect_source_type()
        self._frame_count = 0
        self._dropped_count = 0
        self._stream_status = StreamStatus.DISCONNECTED
        self._last_frame_time = 0.0
        self._mock_frame_num = 0
        self._opened = False

    def _detect_source_type(self) -> SourceType:
        """Determine the source type from the input."""
        if isinstance(self.source, int):
            return SourceType.WEBCAM
        source_str = str(self.source).lower()
        if source_str == "mock":
            return SourceType.MOCK
        if source_str.startswith(("rtsp://", "rtmp://", "http://", "https://")):
            return SourceType.RTSP
        return SourceType.VIDEO_FILE

    def open(self) -> bool:
        """Open the video source. Returns True on success."""
        if self._source_type == SourceType.MOCK:
            self._stream_status = StreamStatus.CONNECTED
            self._opened = True
            logger.info("Mock video source opened (%dx%d)",
                        self.mock_frame_size[0], self.mock_frame_size[1])
            return True

        if isinstance(self.source, int):
            if os.name == 'nt':
                for api_pref in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                    try:
                        cap = cv2.VideoCapture(self.source, api_pref)
                        if cap is not None and cap.isOpened():
                            self._cap = cap
                            break
                    except Exception:
                        continue
            else:
                self._cap = cv2.VideoCapture(self.source)
        else:
            self._cap = cv2.VideoCapture(self.source)
        if self._cap is None or not self._cap.isOpened():
            logger.error("Failed to open video source: %s", self.source)
            self._stream_status = StreamStatus.DISCONNECTED
            return False

        # Set resolution & hardware optimizations for webcam/RTSP
        if self._source_type in (SourceType.WEBCAM, SourceType.RTSP):
            try:
                self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            except Exception:
                pass
            try:
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width or 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height or 720)
            self._cap.set(cv2.CAP_PROP_FPS, 30.0)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        self._stream_status = StreamStatus.CONNECTED
        self._opened = True
        logger.info(
            "Video source opened: %s (%dx%d @ %.1f FPS)",
            self.source, actual_w, actual_h, actual_fps,
        )
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray], FrameHealth]:
        """
        Read the next frame.

        Returns:
            (success, frame, frame_health) tuple.
            On failure, frame is None and health reflects the issue.
        """
        health = FrameHealth(
            stream_status=self._stream_status,
            dropped_frame_count=self._dropped_count,
        )

        if not self._opened:
            health.status = FrameStatus.DROPPED
            health.stream_status = StreamStatus.DISCONNECTED
            return False, None, health

        # Mock source: generate synthetic frames
        if self._source_type == SourceType.MOCK:
            frame = self._generate_mock_frame()
            health = self._compute_health(frame)
            self._frame_count += 1
            return True, frame, health

        # Real capture
        ret, frame = self._cap.read()
        if not ret or frame is None:
            self._dropped_count += 1
            health.status = FrameStatus.DROPPED
            health.dropped_frame_count = self._dropped_count

            # For video files, end of file
            if self._source_type == SourceType.VIDEO_FILE:
                logger.info("End of video file reached.")
                self._stream_status = StreamStatus.DISCONNECTED
                health.stream_status = StreamStatus.DISCONNECTED
                return False, None, health

            # For RTSP/webcam, tolerate temporary frame misses without resetting device
            if self._source_type in (SourceType.RTSP, SourceType.WEBCAM):
                if self._dropped_count < 60:
                    health.stream_status = StreamStatus.CONNECTED
                    return False, None, health

                logger.warning("Excessive frame drop (total: %d). Attempting reconnect...", self._dropped_count)
                if self._reconnect():
                    self._dropped_count = 0
                    health.stream_status = StreamStatus.CONNECTED
                    ret, frame = self._cap.read()
                    if ret and frame is not None:
                        health = self._compute_health(frame)
                        self._frame_count += 1
                        return True, frame, health

                health.stream_status = StreamStatus.DISCONNECTED
            return False, None, health

        self._dropped_count = 0
        health = self._compute_health(frame)
        self._frame_count += 1
        self._last_frame_time = time.time()
        return True, frame, health

    def _reconnect(self) -> bool:
        """Attempt to reconnect to the video source."""
        self._stream_status = StreamStatus.RECONNECTING
        for attempt in range(1, self.max_reconnect_attempts + 1):
            logger.info("Reconnect attempt %d/%d...",
                        attempt, self.max_reconnect_attempts)
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
            time.sleep(self.reconnect_delay)
            if isinstance(self.source, int):
                if os.name == 'nt':
                    self._cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
                else:
                    self._cap = cv2.VideoCapture(self.source)
            else:
                self._cap = cv2.VideoCapture(self.source)
            if self._cap is not None and self._cap.isOpened():
                self._stream_status = StreamStatus.CONNECTED
                self._dropped_count = 0
                logger.info("Reconnected successfully.")
                return True
        self._stream_status = StreamStatus.DISCONNECTED
        logger.error("Failed to reconnect after %d attempts.",
                      self.max_reconnect_attempts)
        return False

    def _compute_health(self, frame: np.ndarray) -> FrameHealth:
        """Compute frame quality metrics with high efficiency."""
        h, w = frame.shape[:2]
        # Fast thumbnail sampling for metrics
        small = frame[::4, ::4]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray)) / 255.0

        # Blur: Laplacian variance on sampled thumbnail (scaled to preserve magnitude)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_32F).var())

        # Determine status
        status = FrameStatus.OK
        if brightness < 0.15 or brightness > 0.95 or blur_score < 20:
            status = FrameStatus.DEGRADED

        return FrameHealth(
            brightness=brightness,
            blur_score=blur_score,
            status=status,
            stream_status=self._stream_status,
            dropped_frame_count=self._dropped_count,
            frame_width=w,
            frame_height=h,
        )

    def _generate_mock_frame(self) -> np.ndarray:
        """Generate a synthetic frame with mock seated students for testing."""
        w, h = self.mock_frame_size
        frame = np.full((h, w, 3), (40, 40, 50), dtype=np.uint8)

        # Draw a simple classroom-like scene
        # Floor
        cv2.rectangle(frame, (0, h // 2), (w, h), (60, 55, 50), -1)

        # Draw 3 "desks" as rectangles
        desk_y = h * 2 // 3
        desk_h = 30
        for i in range(3):
            dx1 = w * (i * 3 + 1) // 10
            dx2 = w * (i * 3 + 3) // 10
            cv2.rectangle(frame, (dx1, desk_y), (dx2, desk_y + desk_h),
                          (100, 90, 80), -1)

        # Draw 3 "students" as simple shapes (head + body)
        self._mock_frame_num += 1
        colors = [(180, 140, 100), (100, 140, 180), (140, 180, 100)]
        for i in range(3):
            cx = w * (i * 3 + 2) // 10
            cy = desk_y - 80

            # Add slight movement to simulate head motion
            dx = int(10 * np.sin(self._mock_frame_num * 0.05 + i * 1.5))
            dy = int(5 * np.sin(self._mock_frame_num * 0.03 + i * 2.0))

            # Body (rectangle)
            body_w, body_h = 60, 100
            cv2.rectangle(frame,
                          (cx - body_w // 2 + dx, cy - 20 + dy),
                          (cx + body_w // 2 + dx, cy + body_h + dy),
                          colors[i], -1)

            # Head (circle)
            head_r = 25
            cv2.circle(frame, (cx + dx, cy - 20 - head_r + dy),
                       head_r, colors[i], -1)

            # Arms (lines)
            shoulder_y = cy + dy
            elbow_offset = 40
            cv2.line(frame,
                     (cx - body_w // 2 + dx, shoulder_y),
                     (cx - body_w // 2 - elbow_offset + dx, shoulder_y + 40),
                     colors[i], 3)
            cv2.line(frame,
                     (cx + body_w // 2 + dx, shoulder_y),
                     (cx + body_w // 2 + elbow_offset + dx, shoulder_y + 40),
                     colors[i], 3)

        # Frame counter
        cv2.putText(frame, f"MOCK FRAME {self._mock_frame_num}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        return frame

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def is_opened(self) -> bool:
        return self._opened

    @property
    def source_type(self) -> SourceType:
        return self._source_type

    @property
    def total_frames(self) -> Optional[int]:
        """Total frame count (only for video files)."""
        if self._source_type == SourceType.VIDEO_FILE and self._cap is not None:
            total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
            return total if total > 0 else None
        return None

    @property
    def source_fps(self) -> float:
        """Reported FPS of the source."""
        if self._cap is not None:
            return self._cap.get(cv2.CAP_PROP_FPS)
        return float(self.target_fps)

    def release(self):
        """Release the video source."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._opened = False
        self._stream_status = StreamStatus.DISCONNECTED
        logger.info("Video source released.")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
