"""
Temporal keypoint tracking, smoothing, and persistence manager.

Maintains continuous, jitter-free skeletal keypoints across video frames:
1. Exponential Moving Average (EMA) smoothing for stable joint coordinates.
2. Motion-compensated persistence during tracking coasting (brief occlusions).
3. Occlusion infilling for momentarily dropped joints.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import numpy as np

from app.perception.core.constants import TOTAL_KEYPOINTS, TrackingState
from app.perception.core.data_models import BoundingBox, KeypointSet, TrackedObject

logger = logging.getLogger(__name__)


@dataclass
class KeypointTrackState:
    """Internal temporal state for a single tracked student's keypoints."""
    keypoints: KeypointSet
    last_bbox: BoundingBox
    frames_since_detection: int = 0


class TemporalKeypointManager:
    """
    Manages temporal persistence and smoothing of 2D skeletal keypoints.

    Args:
        ema_alpha: Smoothing weight for fresh coordinates [0, 1].
                   Higher = more responsive, lower = smoother. Default 0.75.
        min_detection_conf: Minimum confidence to consider a joint freshly detected.
        coast_decay: Multiplicative decay factor applied to confidence per coasting frame.
        max_coast_frames: Maximum frames to retain keypoints without any fresh detection.
    """

    def __init__(
        self,
        ema_alpha: float = 0.75,
        min_detection_conf: float = 0.20,
        coast_decay: float = 0.95,
        max_coast_frames: int = 45,
        adaptive_alpha: bool = False,
    ):
        self.ema_alpha = float(np.clip(ema_alpha, 0.1, 1.0))
        self.min_detection_conf = min_detection_conf
        self.coast_decay = float(np.clip(coast_decay, 0.8, 0.99))
        self.max_coast_frames = max_coast_frames
        self.adaptive_alpha = adaptive_alpha
        self._states: Dict[int, KeypointTrackState] = {}

    def update(
        self,
        tracked_objects: List[TrackedObject],
        fresh_keypoints_map: Dict[int, KeypointSet],
    ) -> Dict[int, KeypointSet]:
        """
        Update temporal states and return persistent, smoothed keypoints for all active tracks.

        Args:
            tracked_objects: List of TrackedObject from tracker.
            fresh_keypoints_map: Map of track_id -> KeypointSet from current frame detection.

        Returns:
            Map of track_id -> smoothed/persistent KeypointSet for every active track.
        """
        active_ids: Set[int] = set()
        result_map: Dict[int, KeypointSet] = {}

        for track in tracked_objects:
            tid = track.track_id
            if track.state == TrackingState.LOST:
                continue

            active_ids.add(tid)
            fresh_kps = fresh_keypoints_map.get(tid)
            has_fresh = fresh_kps is not None and fresh_kps.region_confidence(list(range(17))) > 0.05

            if has_fresh and fresh_kps is not None:
                # We have fresh detection keypoints for this track
                if tid in self._states:
                    smoothed_kps = self._smooth_keypoints(
                        prev_kps=self._states[tid].keypoints,
                        fresh_kps=fresh_kps,
                        prev_bbox=self._states[tid].last_bbox,
                        curr_bbox=track.bbox,
                    )
                    self._states[tid] = KeypointTrackState(
                        keypoints=smoothed_kps,
                        last_bbox=track.bbox,
                        frames_since_detection=0,
                    )
                else:
                    # New track initialized
                    self._states[tid] = KeypointTrackState(
                        keypoints=fresh_kps,
                        last_bbox=track.bbox,
                        frames_since_detection=0,
                    )
                result_map[tid] = self._states[tid].keypoints

            elif tid in self._states:
                # Coasting track or frame without fresh detection
                state = self._states[tid]
                state.frames_since_detection += 1

                if state.frames_since_detection <= self.max_coast_frames:
                    coasted_kps = self._coast_keypoints(
                        prev_kps=state.keypoints,
                        prev_bbox=state.last_bbox,
                        curr_bbox=track.bbox,
                    )
                    state.keypoints = coasted_kps
                    state.last_bbox = track.bbox
                    result_map[tid] = coasted_kps
                else:
                    # Exceeded coasting limit for keypoints
                    result_map[tid] = KeypointSet.empty()
            else:
                result_map[tid] = KeypointSet.empty()

        # Prune stale tracks from memory
        stale_ids = [tid for tid in self._states if tid not in active_ids]
        for tid in stale_ids:
            del self._states[tid]

        return result_map

    def _smooth_keypoints(
        self,
        prev_kps: KeypointSet,
        fresh_kps: KeypointSet,
        prev_bbox: BoundingBox,
        curr_bbox: BoundingBox,
    ) -> KeypointSet:
        """Apply adaptive velocity-confidence EMA smoothing and kinematic infilling."""
        smooth_xy = np.copy(fresh_kps.xy)
        smooth_conf = np.copy(fresh_kps.confidence)

        # Compute bounding box center displacement
        prev_cx, prev_cy = prev_bbox.center
        curr_cx, curr_cy = curr_bbox.center
        dx = curr_cx - prev_cx
        dy = curr_cy - prev_cy

        # Reference scale for anatomical constraints (shoulder span or head size)
        sh_span = 50.0
        if len(prev_kps.xy) >= 7 and prev_kps.confidence[5] > 0.20 and prev_kps.confidence[6] > 0.20:
            sh_span = max(float(np.linalg.norm(prev_kps.xy[5] - prev_kps.xy[6])), 25.0)

        for i in range(min(len(fresh_kps.confidence), TOTAL_KEYPOINTS)):
            f_conf = fresh_kps.confidence[i]
            p_conf = prev_kps.confidence[i]

            if f_conf >= self.min_detection_conf:
                if p_conf >= self.min_detection_conf:
                    if self.adaptive_alpha:
                        diff_x = fresh_kps.xy[i, 0] - prev_kps.xy[i, 0]
                        diff_y = fresh_kps.xy[i, 1] - prev_kps.xy[i, 1]
                        dist = math.sqrt(diff_x * diff_x + diff_y * diff_y)

                        # High velocity -> responsive alpha (no lag); Low velocity -> smooth alpha (zero jitter)
                        if dist >= 16.0:
                            eff_alpha = 0.88
                        elif dist <= 3.0:
                            eff_alpha = 0.35
                        else:
                            eff_alpha = 0.35 + 0.53 * ((dist - 3.0) / 13.0)

                        if f_conf < 0.40:
                            eff_alpha *= 0.65
                    else:
                        eff_alpha = self.ema_alpha

                    smooth_xy[i, 0] = (eff_alpha * fresh_kps.xy[i, 0]) + ((1.0 - eff_alpha) * prev_kps.xy[i, 0])
                    smooth_xy[i, 1] = (eff_alpha * fresh_kps.xy[i, 1]) + ((1.0 - eff_alpha) * prev_kps.xy[i, 1])
                    smooth_conf[i] = 0.80 * f_conf + 0.20 * p_conf
                else:
                    # New joint detection
                    smooth_xy[i] = fresh_kps.xy[i]
                    smooth_conf[i] = f_conf
            elif p_conf >= self.min_detection_conf:
                # Joint momentarily occluded/missed: infill using translated previous position
                smooth_xy[i, 0] = prev_kps.xy[i, 0] + dx
                smooth_xy[i, 1] = prev_kps.xy[i, 1] + dy
                smooth_conf[i] = p_conf * self.coast_decay

        # Kinematic sanity clamp on arm joints (Shoulder -> Elbow -> Wrist)
        # Left arm: 5 -> 7 -> 9, Right arm: 6 -> 8 -> 10
        max_limb_len = sh_span * 1.55
        for parent, child in [(5, 7), (7, 9), (6, 8), (8, 10)]:
            if parent < len(smooth_xy) and child < len(smooth_xy):
                if smooth_conf[parent] >= 0.25 and smooth_conf[child] >= 0.15:
                    bone_vec = smooth_xy[child] - smooth_xy[parent]
                    bone_len = float(np.linalg.norm(bone_vec))
                    if bone_len > max_limb_len and bone_len > 1e-3:
                        # Clamp over-extended noisy limb detection
                        smooth_xy[child] = smooth_xy[parent] + (bone_vec / bone_len) * max_limb_len

        return KeypointSet(xy=smooth_xy, confidence=smooth_conf)

    def _coast_keypoints(
        self,
        prev_kps: KeypointSet,
        prev_bbox: BoundingBox,
        curr_bbox: BoundingBox,
    ) -> KeypointSet:
        """Translate keypoints according to bounding box shift and decay confidence."""
        prev_cx, prev_cy = prev_bbox.center
        curr_cx, curr_cy = curr_bbox.center
        dx = curr_cx - prev_cx
        dy = curr_cy - prev_cy

        coasted_xy = np.copy(prev_kps.xy)
        coasted_conf = np.copy(prev_kps.confidence)

        # Translate all non-zero joints
        valid_mask = prev_kps.confidence > 0.05
        coasted_xy[valid_mask, 0] += dx
        coasted_xy[valid_mask, 1] += dy
        coasted_conf[valid_mask] *= self.coast_decay

        return KeypointSet(xy=coasted_xy, confidence=coasted_conf)

    def reset(self):
        """Reset all temporal states."""
        self._states.clear()
