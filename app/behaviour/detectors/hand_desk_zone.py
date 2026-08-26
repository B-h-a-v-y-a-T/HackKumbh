"""
Hand Movement and Desk Zone Boundary Monitor.
"""

from __future__ import annotations

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose, DeskZone
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode


class HandDeskResult(BaseModel):
    track_id: str
    left_hand_outside: bool = False
    right_hand_outside: bool = False
    hand_outside_zone: bool = False
    reach_direction: Optional[str] = None  # "LEFT", "RIGHT", "FORWARD", "LAP"
    is_reaching_neighbor: bool = False
    hand_velocity_px_sec: float = 0.0
    is_unusual_hand_movement: bool = False
    confidence: float = 1.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class HandDeskZoneDetector:
    """Monitors whether student hands stay within their designated desk boundary with relaxed tolerances."""

    def __init__(
        self,
        velocity_threshold: float = 0.40,  # Normalized velocity per second
        margin_tolerance: float = 0.05,    # 5% boundary cushion
        min_keypoint_confidence: float = 0.20,
    ):
        self.velocity_threshold = velocity_threshold
        self.margin_tolerance = margin_tolerance
        self.min_confidence = min_keypoint_confidence
        self._track_states: Dict[str, Dict] = {}

    def reset_track(self, track_id: str):
        if track_id in self._track_states:
            del self._track_states[track_id]

    def _get_state(self, track_id: str) -> Dict:
        if track_id not in self._track_states:
            self._track_states[track_id] = {
                "last_timestamp_ms": None,
                "last_left_wrist": None,
                "last_right_wrist": None,
                "outside_duration_sec": 0.0,
            }
        return self._track_states[track_id]

    def analyze(self, track: TrackPose, timestamp_ms: float) -> HandDeskResult:
        """Analyzes wrist position relative to desk zone / torso workspace and computes hand kinetics."""
        state = self._get_state(track.track_id)
        
        l_wrist = track.get_keypoint("left_wrist")
        r_wrist = track.get_keypoint("right_wrist")
        l_sh = track.get_keypoint("left_shoulder")
        r_sh = track.get_keypoint("right_shoulder")
        desk_zone = track.desk_zone

        # Construct dynamic fallback workspace if fixed desk zone is not provided
        if not desk_zone and l_sh and r_sh and l_sh.confidence >= self.min_confidence and r_sh.confidence >= self.min_confidence:
            sh_w = max(abs(r_sh.x - l_sh.x), 0.12)
            sh_cx = (l_sh.x + r_sh.x) / 2.0
            sh_cy = (l_sh.y + r_sh.y) / 2.0
            desk_zone = DeskZone(
                seat_id=track.seat_id,
                x_min=sh_cx - sh_w * 0.9,
                x_max=sh_cx + sh_w * 0.9,
                y_min=sh_cy + 0.05,
                y_max=sh_cy + sh_w * 1.8,
            )

        valid_wrists = [w for w in [l_wrist, r_wrist] if w and w.confidence >= self.min_confidence]
        if not valid_wrists:
            return HandDeskResult(
                track_id=track.track_id,
                confidence=0.2,
                reason_codes=[]
            )

        avg_conf = sum(w.confidence for w in valid_wrists) / len(valid_wrists)

        # Compute wrist movement velocity
        dt_sec = 0.05
        if state["last_timestamp_ms"] is not None:
            dt_sec = max((timestamp_ms - state["last_timestamp_ms"]) / 1000.0, 0.001)

        max_vel = 0.0
        if 0 < dt_sec < 2.0:
            if l_wrist and state["last_left_wrist"]:
                dist_l = math.hypot(l_wrist.x - state["last_left_wrist"][0], l_wrist.y - state["last_left_wrist"][1])
                max_vel = max(max_vel, dist_l / dt_sec)
            if r_wrist and state["last_right_wrist"]:
                dist_r = math.hypot(r_wrist.x - state["last_right_wrist"][0], r_wrist.y - state["last_right_wrist"][1])
                max_vel = max(max_vel, dist_r / dt_sec)

        state["last_timestamp_ms"] = timestamp_ms
        if l_wrist:
            state["last_left_wrist"] = (l_wrist.x, l_wrist.y)
        if r_wrist:
            state["last_right_wrist"] = (r_wrist.x, r_wrist.y)

        # Check desk boundary containment and hand gestures
        l_outside = False
        r_outside = False
        reach_dir = None
        is_reaching_neighbor = False
        is_hand_raised = False

        if desk_zone:
            reach_margin = self.margin_tolerance + 0.05

            if l_wrist and l_wrist.confidence >= self.min_confidence:
                if not desk_zone.contains_point(l_wrist.x, l_wrist.y, margin=self.margin_tolerance):
                    l_outside = True
                    if l_wrist.x < (desk_zone.x_min - reach_margin):
                        reach_dir = "LEFT"
                        is_reaching_neighbor = True
                    elif l_wrist.y > (desk_zone.y_max + reach_margin):
                        reach_dir = "LAP"

            if r_wrist and r_wrist.confidence >= self.min_confidence:
                if not desk_zone.contains_point(r_wrist.x, r_wrist.y, margin=self.margin_tolerance):
                    r_outside = True
                    if r_wrist.x > (desk_zone.x_max + reach_margin):
                        reach_dir = "RIGHT"
                        is_reaching_neighbor = True
                    elif r_wrist.y > (desk_zone.y_max + reach_margin):
                        reach_dir = "LAP"

        # Check raised hands / gestures near face or above chest
        if l_sh and l_wrist and l_wrist.confidence >= self.min_confidence and l_sh.confidence >= self.min_confidence:
            if l_wrist.y < (l_sh.y + 0.06):
                is_hand_raised = True
                l_outside = True

        if r_sh and r_wrist and r_wrist.confidence >= self.min_confidence and r_sh.confidence >= self.min_confidence:
            if r_wrist.y < (r_sh.y + 0.06):
                is_hand_raised = True
                r_outside = True

        hand_outside = l_outside or r_outside
        if hand_outside:
            state["outside_duration_sec"] += dt_sec
        else:
            state["outside_duration_sec"] = max(0.0, state["outside_duration_sec"] - dt_sec * 2.0)

        is_unusual_vel = max_vel > self.velocity_threshold or is_hand_raised

        events: List[BehaviourEvent] = []
        reasons: List[ReasonCode] = []

        if hand_outside:
            events.append(BehaviourEvent.HAND_OUTSIDE_DESK_ZONE)
            reasons.append(ReasonCode.WRIST_OUTSIDE_DESK_ZONE)

            if is_reaching_neighbor:
                events.append(BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR)

        if is_unusual_vel:
            events.append(BehaviourEvent.UNUSUAL_HAND_MOVEMENT)
            reasons.append(ReasonCode.ERRATIC_HAND_VELOCITY)

        return HandDeskResult(
            track_id=track.track_id,
            left_hand_outside=l_outside,
            right_hand_outside=r_outside,
            hand_outside_zone=hand_outside,
            reach_direction=reach_dir,
            is_reaching_neighbor=is_reaching_neighbor,
            hand_velocity_px_sec=round(max_vel, 3),
            is_unusual_hand_movement=is_unusual_vel,
            confidence=round(avg_conf, 3),
            detected_events=events,
            reason_codes=reasons,
        )
