"""
Writing Activity and Test Engagement Monitor.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode


class WritingActivityResult(BaseModel):
    track_id: str
    is_writing: bool = True
    stillness_duration_sec: float = 0.0
    dominant_wrist_motion_power: float = 0.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class WritingActivityDetector:
    """Monitors continuous writing micro-motion vs stoppage while looking around during exams."""

    def __init__(
        self,
        motion_threshold: float = 0.004,
        stoppage_threshold_sec: float = 4.0,
        window_frames: int = 15,
    ):
        self.motion_threshold = motion_threshold
        self.stoppage_threshold_sec = stoppage_threshold_sec
        self.window_frames = window_frames
        self._track_states: Dict[str, Dict] = {}

    def reset_track(self, track_id: str):
        if track_id in self._track_states:
            del self._track_states[track_id]

    def _get_state(self, track_id: str) -> Dict:
        if track_id not in self._track_states:
            self._track_states[track_id] = {
                "last_timestamp_ms": None,
                "wrist_motion_buffer": [],
                "stillness_duration_sec": 0.0,
                "is_writing": True,
            }
        return self._track_states[track_id]

    def analyze(
        self,
        track: TrackPose,
        timestamp_ms: float,
        is_head_turning: bool = False,
    ) -> WritingActivityResult:
        """Analyzes micro-kinetics of writing wrist with generous margins."""
        state = self._get_state(track.track_id)

        r_wrist = track.get_keypoint("right_wrist")
        l_wrist = track.get_keypoint("left_wrist")

        active_wrist = r_wrist if (r_wrist and r_wrist.confidence > 0.30) else l_wrist

        motion = 0.0
        if active_wrist:
            state["wrist_motion_buffer"].append((active_wrist.x, active_wrist.y))
            if len(state["wrist_motion_buffer"]) > self.window_frames:
                state["wrist_motion_buffer"].pop(0)

            if len(state["wrist_motion_buffer"]) >= 3:
                coords = np.array(state["wrist_motion_buffer"])
                motion = float(np.mean(np.std(coords, axis=0)))

        dt_sec = 0.0
        if state["last_timestamp_ms"] is not None:
            dt_sec = max((timestamp_ms - state["last_timestamp_ms"]) / 1000.0, 0.0)

        state["last_timestamp_ms"] = timestamp_ms

        # Check if wrist is inside desk boundary (with 5% margin)
        wrist_in_desk = True
        if track.desk_zone and active_wrist:
            wrist_in_desk = track.desk_zone.contains_point(active_wrist.x, active_wrist.y, margin=0.05)

        is_actively_writing = (motion >= self.motion_threshold) and wrist_in_desk and (not is_head_turning)

        if is_actively_writing or not is_head_turning:
            # Normal forward writing or screen reading focus
            if is_actively_writing:
                state["stillness_duration_sec"] = max(0.0, state["stillness_duration_sec"] - dt_sec * 2.0)
            state["is_writing"] = True
        else:
            state["stillness_duration_sec"] += dt_sec
            if is_head_turning and state["stillness_duration_sec"] >= 1.5:
                state["is_writing"] = False
            elif state["stillness_duration_sec"] >= self.stoppage_threshold_sec:
                state["is_writing"] = False

        events: List[BehaviourEvent] = []
        reasons: List[ReasonCode] = []

        if state["is_writing"]:
            events.append(BehaviourEvent.WRITING_ACTIVE)
        else:
            events.append(BehaviourEvent.WRITING_STOP)
            if is_head_turning and state["stillness_duration_sec"] >= 1.5:
                events.append(BehaviourEvent.WRITING_STOPPED_WHILE_LOOKING_AROUND)
                reasons.append(ReasonCode.WRITING_HALTED_PROLONGED)

        return WritingActivityResult(
            track_id=track.track_id,
            is_writing=state["is_writing"],
            stillness_duration_sec=round(state["stillness_duration_sec"], 2),
            dominant_wrist_motion_power=round(motion, 5),
            detected_events=events,
            reason_codes=reasons,
        )
