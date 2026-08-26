"""
Head Pose and Gaze Vector Estimation Detector.

Integrates:
1. 3D Euler angles (Yaw, Pitch, Roll) from SixDRepNet or landmark fallback.
2. Resting Neutral Sitting Calibration: Initializes to each student's individual
   desk/monitor orientation on frame 1 and tracks relative head turns (Delta Yaw).
3. Spatial neighbor geometry matching: detects both solo suspicious head turns
   and targeted neighbor gazes.
4. Multi-tier temporal staging: fleeting eye check (<0.8s) -> sustained head turn / neighbor gaze (>=1.3s)
   -> prolonged gaze (>=2.8s).
5. Repeated glance episode counting (e.g. 3 distinct turns in 10s window).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose, Keypoint
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode
from app.behaviour.spatial_group.hall_layout import ExamHallLayout


class HeadGazeResult(BaseModel):
    track_id: str
    yaw_deg: float = 0.0          # Relative yaw from resting monitor/desk orientation (Negative = Left, Positive = Right)
    raw_yaw_deg: float = 0.0      # Absolute camera-relative yaw
    pitch_deg: float = 0.0        # Negative = Down (at desk), Positive = Up
    roll_deg: float = 0.0
    gaze_direction: str = "FORWARD"  # FORWARD, LEFT, RIGHT, DOWN, UP, UNKNOWN
    gaze_target_neighbor: Optional[str] = None  # "LEFT_NEIGHBOUR", "RIGHT_NEIGHBOUR", "FRONT_NEIGHBOUR"
    target_seat_id: Optional[str] = None
    target_track_id: Optional[str] = None
    is_neighbor_gaze: bool = False
    is_prolonged_neighbor_gaze: bool = False
    neighbor_gaze_duration_sec: float = 0.0
    head_turn_count_window: int = 0
    confidence: float = 1.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class HeadGazeDetector:
    """Estimates 3D head pose, relative head turns, and sustained neighbor gaze vectors."""

    def __init__(
        self,
        layout: Optional[ExamHallLayout] = None,
        yaw_neighbor_threshold_deg: float = 28.0,
        pitch_down_threshold_deg: float = -22.0,
        pitch_up_threshold_deg: float = 18.0,
        sustained_gaze_sec: float = 1.2,
        prolonged_gaze_sec: float = 2.8,
        turn_window_sec: float = 10.0,
        min_keypoint_confidence: float = 0.35,
    ):
        self.layout = layout
        self.yaw_neighbor_thresh = yaw_neighbor_threshold_deg
        self.pitch_down_thresh = pitch_down_threshold_deg
        self.pitch_up_thresh = pitch_up_threshold_deg
        self.sustained_gaze_sec = sustained_gaze_sec
        self.prolonged_gaze_sec = prolonged_gaze_sec
        self.turn_window_sec = turn_window_sec
        self.min_confidence = min_keypoint_confidence

        # State tracking per track_id
        self._track_states: Dict[str, Dict] = {}

    def reset_track(self, track_id: str):
        """Reset state for a specific track."""
        if track_id in self._track_states:
            del self._track_states[track_id]

    def _get_state(self, track_id: str) -> Dict:
        if track_id not in self._track_states:
            self._track_states[track_id] = {
                "last_timestamp_ms": None,
                "current_direction": "FORWARD",
                "current_direction_start_ms": None,
                "direction_duration_sec": 0.0,
                "glance_episodes": [],
                "neutral_yaw": 0.0,
                "last_yaw": 0.0,
                "previous_direction": "FORWARD",
            }
        return self._track_states[track_id]

    def analyze(
        self,
        track: TrackPose,
        timestamp_ms: float,
        all_tracks: Optional[List[TrackPose]] = None,
    ) -> HeadGazeResult:
        """
        Analyze 3D head pose and neighbor gaze for a given track.
        """
        state = self._get_state(track.track_id)

        # 1. Retrieve 3D Euler angles (from SixDRepNet in additional_meta if available)
        yaw_deg = 0.0
        pitch_deg = 0.0
        roll_deg = 0.0
        avg_conf = 0.85
        has_meta_pose = False

        if track.additional_meta and ("head_yaw" in track.additional_meta or "head_abs_yaw" in track.additional_meta):
            # Prefer absolute yaw if available, fallback to head_yaw
            yaw_deg = float(track.additional_meta.get("head_abs_yaw", track.additional_meta.get("head_yaw", 0.0)))
            pitch_deg = float(track.additional_meta.get("head_abs_pitch", track.additional_meta.get("head_pitch", 0.0)))
            roll_deg = float(track.additional_meta.get("head_abs_roll", track.additional_meta.get("head_roll", 0.0)))
            avg_conf = float(track.additional_meta.get("head_conf", 0.85))
            has_meta_pose = True

            # If crop was marked invalid
            if track.additional_meta.get("head_crop_valid") is False:
                return HeadGazeResult(
                    track_id=track.track_id,
                    confidence=0.0,
                    gaze_direction="UNKNOWN",
                    reason_codes=[ReasonCode.OCCLUSION_LOW_VISIBILITY],
                )

        # Fallback to keypoint geometry if meta pose is not populated
        if not has_meta_pose:
            nose = track.get_keypoint("nose")
            l_eye = track.get_keypoint("left_eye")
            r_eye = track.get_keypoint("right_eye")
            l_ear = track.get_keypoint("left_ear")
            r_ear = track.get_keypoint("right_ear")
            l_sh = track.get_keypoint("left_shoulder")
            r_sh = track.get_keypoint("right_shoulder")

            valid_pts = [pt for pt in [nose, l_eye, r_eye, l_sh, r_sh] if pt and pt.confidence >= self.min_confidence]
            if len(valid_pts) < 2 or not nose:
                return HeadGazeResult(
                    track_id=track.track_id,
                    confidence=0.2,
                    gaze_direction="UNKNOWN",
                    reason_codes=[ReasonCode.OCCLUSION_LOW_VISIBILITY],
                )

            avg_conf = sum(pt.confidence for pt in valid_pts) / len(valid_pts)

            # Compute fallback Yaw (positive = Right, negative = Left)
            if l_eye and r_eye and l_eye.confidence >= self.min_confidence and r_eye.confidence >= self.min_confidence:
                eye_mid_x = (l_eye.x + r_eye.x) / 2.0
                eye_span = max(abs(r_eye.x - l_eye.x), 0.015)
                nose_offset = (nose.x - eye_mid_x) / (eye_span * 0.5)
                yaw_deg = float(np.clip(nose_offset * 48.0, -90.0, 90.0))
            elif l_ear and r_ear and l_ear.confidence >= self.min_confidence and r_ear.confidence >= self.min_confidence:
                ear_mid_x = (l_ear.x + r_ear.x) / 2.0
                ear_span = max(abs(r_ear.x - l_ear.x), 0.025)
                nose_offset = (nose.x - ear_mid_x) / (eye_span * 0.5)
                yaw_deg = float(np.clip(nose_offset * 50.0, -90.0, 90.0))

            # Compute fallback Pitch (negative = Down at desk, positive = Up)
            if l_eye and r_eye and l_sh and r_sh:
                eye_mid_y = (l_eye.y + r_eye.y) / 2.0
                sh_mid_y = (l_sh.y + r_sh.y) / 2.0
                head_sh_dist = max(sh_mid_y - eye_mid_y, 0.03)
                nose_y_ratio = (nose.y - eye_mid_y) / head_sh_dist
                pitch_deg = float((0.42 - nose_y_ratio) * 65.0)

            # Compute fallback Roll
            if l_eye and r_eye:
                dy = r_eye.y - l_eye.y
                dx = r_eye.x - l_eye.x
                roll_deg = float(math.degrees(math.atan2(dy, max(abs(dx), 0.001))))

        # 2. Adaptive Neutral Resting Baseline
        if has_meta_pose:
            relative_yaw = yaw_deg
            state["neutral_yaw"] = 0.0
        else:
            if abs(yaw_deg) < 12.0:
                state["neutral_yaw"] = (0.98 * state["neutral_yaw"]) + (0.02 * yaw_deg)
            state["neutral_yaw"] = float(np.clip(state["neutral_yaw"], -10.0, 10.0))
            relative_yaw = yaw_deg - state["neutral_yaw"]

        # 3. Classify Direction
        gaze_direction = "FORWARD"
        if track.additional_meta and "head_direction" in track.additional_meta:
            upstream_dir = str(track.additional_meta["head_direction"])
            if upstream_dir in ["LEFT", "RIGHT", "DOWN", "UP", "FORWARD"]:
                gaze_direction = upstream_dir

        if gaze_direction in ["FORWARD", "UNKNOWN"] or abs(relative_yaw) >= 16.0:
            if relative_yaw < -16.0:
                gaze_direction = "LEFT"
            elif relative_yaw > 16.0:
                gaze_direction = "RIGHT"
            elif pitch_deg < self.pitch_down_thresh:
                gaze_direction = "DOWN"
            elif pitch_deg > self.pitch_up_thresh:
                gaze_direction = "UP"
            else:
                gaze_direction = "FORWARD"

        # 4. Spatial Neighbor Geometry Verification
        target_neighbor, target_seat_id, target_track_id, has_actual_neighbor = self._resolve_spatial_neighbor(
            track=track,
            direction=gaze_direction,
            all_tracks=all_tracks,
        )

        # 5. Temporal Accumulation & Episode Tracking
        dt_sec = 0.05
        if state["last_timestamp_ms"] is not None:
            dt_sec = max((timestamp_ms - state["last_timestamp_ms"]) / 1000.0, 0.001)
            if dt_sec > 3.0:
                dt_sec = 0.05
                state["direction_duration_sec"] = 0.0
                state["current_direction_start_ms"] = timestamp_ms

        if gaze_direction == state["current_direction"]:
            state["direction_duration_sec"] += dt_sec
        else:
            prev_dir = state["current_direction"]
            prev_dur = state["direction_duration_sec"]

            # Genuine turn (>= 0.4s) records as a glance episode
            if prev_dir in ["LEFT", "RIGHT", "UP"] and prev_dur >= 0.4:
                state["glance_episodes"].append({
                    "timestamp_ms": timestamp_ms,
                    "direction": prev_dir,
                    "target_neighbor": state.get("last_target_neighbor"),
                    "duration_sec": prev_dur,
                })

            state["previous_direction"] = prev_dir
            state["current_direction"] = gaze_direction
            state["current_direction_start_ms"] = timestamp_ms
            state["direction_duration_sec"] = dt_sec

        state["last_timestamp_ms"] = timestamp_ms
        state["last_yaw"] = yaw_deg
        state["last_target_neighbor"] = target_neighbor

        # 6. Prune Glance Episodes outside Rolling Window
        window_cutoff = timestamp_ms - (self.turn_window_sec * 1000.0)
        state["glance_episodes"] = [
            ep for ep in state["glance_episodes"] if ep["timestamp_ms"] >= window_cutoff
        ]
        glance_episode_count = len(state["glance_episodes"])

        current_glance_active = (gaze_direction in ["LEFT", "RIGHT"]) and (state["direction_duration_sec"] >= 0.4)
        total_glance_episodes = glance_episode_count + (1 if current_glance_active else 0)

        # 7. Evaluate Gaze Duration Staging & Extreme Turn Detection
        events: List[BehaviourEvent] = []
        reasons: List[ReasonCode] = []

        is_neighbor_gaze = False
        is_prolonged_neighbor_gaze = False

        duration = state["direction_duration_sec"]
        is_extreme_turn = (abs(relative_yaw) >= 40.0)

        if gaze_direction in ["LEFT", "RIGHT"]:
            turn_event = BehaviourEvent.HEAD_TURN_LEFT if gaze_direction == "LEFT" else BehaviourEvent.HEAD_TURN_RIGHT
            reason_side = ReasonCode.PROLONGED_NEIGHBOUR_GAZE_LEFT if gaze_direction == "LEFT" else ReasonCode.PROLONGED_NEIGHBOUR_GAZE_RIGHT

            # Add head turn event immediately
            events.append(turn_event)
            reasons.append(reason_side if has_actual_neighbor else ReasonCode.HEAD_YAW_EXCEEDS_BASELINE)

            if duration >= 0.4 or has_actual_neighbor or is_extreme_turn or abs(relative_yaw) >= 25.0:
                is_neighbor_gaze = True
                events.append(BehaviourEvent.NEIGHBOUR_GAZE)

            if duration >= 1.2 or is_extreme_turn or abs(relative_yaw) >= 38.0:
                is_prolonged_neighbor_gaze = True
                events.append(BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE)

        elif gaze_direction == "DOWN":
            if duration > 15.0:
                events.append(BehaviourEvent.HEAD_DOWN_PROLONGED)

        elif gaze_direction == "UP":
            if duration >= 2.5:
                events.append(BehaviourEvent.HEAD_UP_SEARCHING)

        # Repeated head turns (requires >= 2 distinct glance episodes)
        if total_glance_episodes >= 2:
            events.append(BehaviourEvent.REPEATED_HEAD_TURN)
            reasons.append(ReasonCode.HEAD_YAW_EXCEEDS_BASELINE)

        return HeadGazeResult(
            track_id=track.track_id,
            yaw_deg=round(relative_yaw, 1),
            raw_yaw_deg=round(yaw_deg, 1),
            pitch_deg=round(pitch_deg, 1),
            roll_deg=round(roll_deg, 1),
            gaze_direction=gaze_direction,
            gaze_target_neighbor=target_neighbor,
            target_seat_id=target_seat_id,
            target_track_id=target_track_id,
            is_neighbor_gaze=is_neighbor_gaze,
            is_prolonged_neighbor_gaze=is_prolonged_neighbor_gaze,
            neighbor_gaze_duration_sec=round(duration, 2) if is_neighbor_gaze or duration >= self.sustained_gaze_sec else 0.0,
            head_turn_count_window=total_glance_episodes,
            confidence=round(avg_conf, 3),
            detected_events=events,
            reason_codes=reasons,
        )

    def _resolve_spatial_neighbor(
        self,
        track: TrackPose,
        direction: str,
        all_tracks: Optional[List[TrackPose]] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], bool]:
        """
        Resolves whether a genuine student neighbor exists in the gaze direction.
        """
        if direction not in ["LEFT", "RIGHT", "UP"]:
            return None, None, None, False

        seat_id = track.seat_id

        # 1. Hall layout grid resolution if available
        if self.layout and seat_id and seat_id != "UNASSIGNED":
            curr_seat = self.layout.get_seat(seat_id)
            if curr_seat:
                for other_seat_id, other_seat in self.layout.seats.items():
                    if other_seat_id == seat_id:
                        continue
                    rel_dir = self.layout.get_relative_direction(seat_id, other_seat_id)
                    if rel_dir == direction:
                        target_tid = None
                        if all_tracks:
                            for other_tr in all_tracks:
                                if other_tr.seat_id == other_seat_id and other_tr.track_id != track.track_id:
                                    target_tid = other_tr.track_id
                                    break
                        label = f"{direction}_NEIGHBOUR"
                        return label, other_seat_id, target_tid, True

        # 2. Track bounding box spatial proximity fallback
        if all_tracks and len(all_tracks) > 1 and track.bbox:
            cx = (track.bbox.x_min + track.bbox.x_max) / 2.0
            cy = (track.bbox.y_min + track.bbox.y_max) / 2.0

            best_neighbor_tr = None
            min_dist = 999.0

            for other_tr in all_tracks:
                if other_tr.track_id == track.track_id or not other_tr.bbox:
                    continue
                ocx = (other_tr.bbox.x_min + other_tr.bbox.x_max) / 2.0
                ocy = (other_tr.bbox.y_min + other_tr.bbox.y_max) / 2.0

                dx = ocx - cx
                dy = ocy - cy
                dist = math.hypot(dx, dy)

                if direction == "LEFT" and dx < -0.05 and abs(dy) < 0.25 and dist < 0.45:
                    if dist < min_dist:
                        min_dist = dist
                        best_neighbor_tr = other_tr
                elif direction == "RIGHT" and dx > 0.05 and abs(dy) < 0.25 and dist < 0.45:
                    if dist < min_dist:
                        min_dist = dist
                        best_neighbor_tr = other_tr
                elif direction == "UP" and dy < -0.05 and abs(dx) < 0.25 and dist < 0.45:
                    if dist < min_dist:
                        min_dist = dist
                        best_neighbor_tr = other_tr

            if best_neighbor_tr is not None:
                label = f"{direction}_NEIGHBOUR"
                return label, best_neighbor_tr.seat_id, best_neighbor_tr.track_id, True

        return None, None, None, False
