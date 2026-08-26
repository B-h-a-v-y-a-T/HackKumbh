"""
Torso Rotation and Posture Analysis Detector.

Calculates upper-body torso rotation relative to the designated seat frontal axis.
Applies angular hysteresis and minimum temporal persistence to eliminate momentary fidgets.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode


class TorsoPostureResult(BaseModel):
    track_id: str
    torso_rotation_deg: float = 0.0  # Angle relative to seat frontal axis (-90 to +90)
    torso_tilt_deg: float = 0.0      # Slouch / forward leaning
    is_rotated: bool = False
    rotation_direction: str = "CENTER"  # CENTER, LEFT, RIGHT
    is_leaning: bool = False
    duration_sec: float = 0.0
    confidence: float = 1.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class TorsoPostureDetector:
    """Detects upper body and torso rotation relative to seat forward axis with relaxed thresholds."""

    def __init__(
        self,
        rotation_threshold_deg: float = 20.0,
        rotation_exit_threshold_deg: float = 14.0,
        persistence_threshold_sec: float = 0.25,
        leaning_threshold_offset: float = 0.10,
        min_keypoint_confidence: float = 0.30,
    ):
        self.rot_enter = rotation_threshold_deg
        self.rot_exit = rotation_exit_threshold_deg
        self.persistence_sec = persistence_threshold_sec
        self.lean_thresh = leaning_threshold_offset
        self.min_confidence = min_keypoint_confidence
        self._track_states: Dict[str, Dict] = {}

    def _get_state(self, track_id: str) -> Dict:
        if track_id not in self._track_states:
            self._track_states[track_id] = {
                "neutral_slope": None,
                "current_direction": "CENTER",
                "rotation_duration_sec": 0.0,
                "last_timestamp_ms": None,
            }
        return self._track_states[track_id]

    def reset_track(self, track_id: str):
        if track_id in self._track_states:
            del self._track_states[track_id]

    def analyze(self, track: TrackPose, timestamp_ms: float) -> TorsoPostureResult:
        """Analyzes upper-body posture and torso orientation."""
        state = self._get_state(track.track_id)

        l_sh = track.get_keypoint("left_shoulder")
        r_sh = track.get_keypoint("right_shoulder")

        if not l_sh or not r_sh or l_sh.confidence < self.min_confidence or r_sh.confidence < self.min_confidence:
            return TorsoPostureResult(
                track_id=track.track_id,
                confidence=0.2,
                reason_codes=[ReasonCode.OCCLUSION_LOW_VISIBILITY],
            )

        avg_conf = (l_sh.confidence + r_sh.confidence) / 2.0

        # Shoulder vector in 2D plane
        dx = r_sh.x - l_sh.x
        dy = r_sh.y - l_sh.y
        raw_slope = math.degrees(math.atan2(dy, max(abs(dx), 0.01)))

        # Adaptive baseline for resting sitting posture
        if state["neutral_slope"] is None:
            state["neutral_slope"] = raw_slope
        else:
            diff = (raw_slope - state["neutral_slope"] + 180.0) % 360.0 - 180.0
            if abs(diff) < 16.0:
                state["neutral_slope"] = (0.98 * state["neutral_slope"]) + (0.02 * raw_slope)

        # Angular difference with unwrapping
        diff_slope = (raw_slope - state["neutral_slope"] + 180.0) % 360.0 - 180.0
        raw_rot = diff_slope * 1.25
        rot_deg = float(np.clip(raw_rot, -90.0, 90.0))

        # Check leaning relative to desk center
        is_leaning = False
        if track.desk_zone:
            desk_center_x = (track.desk_zone.x_min + track.desk_zone.x_max) / 2.0
            sh_center_x = (l_sh.x + r_sh.x) / 2.0
            if abs(sh_center_x - desk_center_x) > (self.lean_thresh * 1.5):
                is_leaning = True

        # Temporal delta
        dt_sec = 0.0
        if state["last_timestamp_ms"] is not None:
            dt_sec = max((timestamp_ms - state["last_timestamp_ms"]) / 1000.0, 0.0)
            if dt_sec > 4.0:
                state["rotation_duration_sec"] = 0.0

        state["last_timestamp_ms"] = timestamp_ms

        # Hysteresis state transition
        prev_dir = state["current_direction"]
        current_dir = prev_dir

        if prev_dir == "LEFT":
            if rot_deg > -self.rot_exit:
                current_dir = "RIGHT" if rot_deg > self.rot_enter else "CENTER"
        elif prev_dir == "RIGHT":
            if rot_deg < self.rot_exit:
                current_dir = "LEFT" if rot_deg < -self.rot_enter else "CENTER"
        else:
            if rot_deg < -self.rot_enter:
                current_dir = "LEFT"
            elif rot_deg > self.rot_enter:
                current_dir = "RIGHT"
            else:
                current_dir = "CENTER"

        if current_dir == prev_dir and current_dir != "CENTER":
            state["rotation_duration_sec"] += dt_sec
        else:
            state["current_direction"] = current_dir
            state["rotation_duration_sec"] = dt_sec if current_dir != "CENTER" else 0.0

        is_rotated = (current_dir in ["LEFT", "RIGHT"]) and (state["rotation_duration_sec"] >= self.persistence_sec or abs(rot_deg) >= 25.0)

        events: List[BehaviourEvent] = []
        reasons: List[ReasonCode] = []

        if is_rotated:
            events.append(BehaviourEvent.TORSO_ROTATION)
            if current_dir == "LEFT":
                events.append(BehaviourEvent.TORSO_ROTATION_LEFT)
            else:
                events.append(BehaviourEvent.TORSO_ROTATION_RIGHT)
            reasons.append(ReasonCode.TORSO_ROTATION_EXCEEDS_THRESHOLD)

        if is_leaning:
            events.append(BehaviourEvent.LEANING_OVER_DESK)

        return TorsoPostureResult(
            track_id=track.track_id,
            torso_rotation_deg=round(rot_deg, 1),
            torso_tilt_deg=round(dy * 100.0, 1),
            is_rotated=is_rotated,
            rotation_direction=current_dir,
            is_leaning=is_leaning,
            duration_sec=round(state["rotation_duration_sec"], 2),
            confidence=round(avg_conf, 3),
            detected_events=events,
            reason_codes=reasons,
        )
