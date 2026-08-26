"""Synthetic Realistic Pose & Keypoint Stream Generator."""
import math
import random
import time
import numpy as np
from typing import Dict, List, Optional, Tuple

from app.behaviour.schemas.pose import (
    COCO_KEYPOINTS,
    Keypoint,
    BoundingBox,
    DeskZone,
    TrackPose,
    InvigilatorState,
    FrameInput,
    filter_student_tracks,
)
from app.behaviour.spatial_group.hall_layout import ExamHallLayout, SeatLocation
from .scenarios import ScenarioType, SCENARIO_PRESETS, ScenarioConfig


class MockPoseStreamGenerator:
    """Generates continuous streams of realistic 17-keypoint skeleton poses."""

    def __init__(
        self,
        layout: Optional[ExamHallLayout] = None,
        num_students: int = 15,
        fps: float = 15.0,
    ):
        self.layout = layout or ExamHallLayout(rows=3, cols=5)
        self.fps = fps
        self.frame_id = 0
        self.start_time_ms = time.time() * 1000.0
        self.current_scenario: ScenarioType = ScenarioType.NORMAL_HALL
        
        # Build student roster: Assign anonymous track IDs to seats
        self.tracks: Dict[str, str] = {}  # {track_id: seat_id}
        all_seats = sorted(list(self.layout.seats.keys()))[:num_students]
        
        # Ensure T17, T18, T19 exist on consecutive seats in row B for chain scenario
        assigned_seats = {}
        # Predefined mapping for demo consistency:
        special_mapping = {
            "T17": "B2",
            "T18": "B3",
            "T19": "B4",
            "T14": "C3",
            "T15": "C4",
            "T08": "C2",
            "T03": "A3",
        }

        # Build list of tracks (up to num_students, plus ensure T17/T18/T19 exist)
        track_list = [f"T{i:02d}" for i in range(1, num_students + 1)]
        for forced in ["T17", "T18", "T19"]:
            if forced not in track_list:
                track_list.append(forced)

        # Reserve seats used by special_mapping so fallback never reuses them
        reserved_seats = set(special_mapping.values())
        available_seats = [s for s in all_seats if s not in reserved_seats]

        avail_idx = 0
        for t_id in track_list:
            if t_id in special_mapping and special_mapping[t_id] in self.layout.seats:
                self.tracks[t_id] = special_mapping[t_id]
            else:
                if avail_idx < len(available_seats):
                    self.tracks[t_id] = available_seats[avail_idx]
                    avail_idx += 1

        # Invigilator position
        self.invigilator_x = 0.5
        self.invigilator_y = 0.1
        self.invigilator_dir = 1.0

    def set_scenario(self, scenario: ScenarioType):
        """Switches the active mock scenario."""
        self.current_scenario = scenario

    def _generate_normal_keypoints(
        self,
        seat: SeatLocation,
        t_sec: float,
        is_fidgety: bool = False
    ) -> List[Keypoint]:
        """Generates standard seated exam-writing keypoint coordinates with natural noise."""
        cx = seat.x
        cy = seat.y

        # Micro-breathing and writing hand movement
        fidget_mult = 3.5 if is_fidgety else 1.0
        noise_x = math.sin(t_sec * 2.0 + cx * 10) * 0.002 * fidget_mult
        noise_y = math.cos(t_sec * 1.5 + cy * 10) * 0.002 * fidget_mult

        # Seated student standard geometry:
        # Head slightly forward and pitched down at paper
        head_x = cx + noise_x
        head_y = cy - 0.025 + noise_y

        # Shoulders
        sh_w = 0.028
        l_sh_x = head_x - sh_w
        l_sh_y = cy - 0.01
        r_sh_x = head_x + sh_w
        r_sh_y = cy - 0.01

        # Elbows
        l_elb_x = l_sh_x - 0.015
        l_elb_y = cy + 0.01
        r_elb_x = r_sh_x + 0.015
        r_elb_y = cy + 0.01

        # Wrists (writing micro-motion on right hand)
        writing_osc = math.sin(t_sec * 6.0) * 0.004
        l_wri_x = cx - 0.015
        l_wri_y = cy + 0.02
        r_wri_x = cx + 0.015 + writing_osc
        r_wri_y = cy + 0.02 + (writing_osc * 0.5)

        # Hips
        hip_w = 0.02
        l_hip_x = cx - hip_w
        l_hip_y = cy + 0.038
        r_hip_x = cx + hip_w
        r_hip_y = cy + 0.038

        # Knees
        l_knee_x = l_hip_x - 0.005
        l_knee_y = cy + 0.065
        r_knee_x = r_hip_x + 0.005
        r_knee_y = cy + 0.065

        # Ankles
        l_ank_x = l_knee_x
        l_ank_y = cy + 0.09
        r_ank_x = r_knee_x
        r_ank_y = cy + 0.09

        # Facial keypoints
        nose_x = head_x
        nose_y = head_y + 0.006  # pitched down
        l_eye_x = head_x - 0.006
        l_eye_y = head_y
        r_eye_x = head_x + 0.006
        r_eye_y = head_y
        l_ear_x = head_x - 0.012
        l_ear_y = head_y - 0.002
        r_ear_x = head_x + 0.012
        r_ear_y = head_y - 0.002

        raw_points = [
            (nose_x, nose_y),      # 0 nose
            (l_eye_x, l_eye_y),    # 1 l_eye
            (r_eye_x, r_eye_y),    # 2 r_eye
            (l_ear_x, l_ear_y),    # 3 l_ear
            (r_ear_x, r_ear_y),    # 4 r_ear
            (l_sh_x, l_sh_y),      # 5 l_sh
            (r_sh_x, r_sh_y),      # 6 r_sh
            (l_elb_x, l_elb_y),    # 7 l_elb
            (r_elb_x, r_elb_y),    # 8 r_elb
            (l_wri_x, l_wri_y),    # 9 l_wri
            (r_wri_x, r_wri_y),    # 10 r_wri
            (l_hip_x, l_hip_y),    # 11 l_hip
            (r_hip_x, r_hip_y),    # 12 r_hip
            (l_knee_x, l_knee_y),  # 13 l_knee
            (r_knee_x, r_knee_y),  # 14 r_knee
            (l_ank_x, l_ank_y),    # 15 l_ank
            (r_ank_x, r_ank_y),    # 16 r_ank
        ]

        keypoints = []
        for x, y in raw_points:
            keypoints.append(
                Keypoint(
                    x=round(float(x), 4),
                    y=round(float(y), 4),
                    confidence=0.95 + (random.random() * 0.05),
                    z=0.0
                )
            )
        return keypoints

    def _apply_scenario_modifications(
        self,
        track_id: str,
        kps: List[Keypoint],
        seat: SeatLocation,
        t_sec: float
    ) -> List[Keypoint]:
        """Applies behavioral anomalies based on the selected scenario."""
        sc = self.current_scenario

        # Scenario 2: Neighbour Gaze Peek (T14 looking at T15 to the right)
        if sc == ScenarioType.NEIGHBOUR_GAZE_PEEK and track_id == "T14":
            # Turn head sharply to right (+yaw)
            yaw_offset = 0.018  # nose shifted right of eye midpoint
            kps[0].x += yaw_offset  # nose
            kps[1].x += yaw_offset * 0.5  # left eye visible
            kps[2].x += yaw_offset * 0.2  # right eye foreshortened
            kps[4].confidence = 0.15  # right ear occluded
            kps[3].confidence = 0.95  # left ear prominent

            # Rotate torso right: left shoulder moves forward/up, right shoulder moves back
            kps[5].y += 0.008  # left shoulder
            kps[6].y -= 0.008  # right shoulder
            kps[5].x += 0.006

            # Stop writing
            kps[10].x = seat.desk_x_min + 0.02  # hand idle

        # Scenario 3: Coordinated Chain T17 -> T18 -> T19
        elif sc == ScenarioType.COORDINATED_CHAIN_T17_T18_T19:
            if track_id == "T17":
                # T17 looks right at T18 and leans slightly
                kps[0].x += 0.016
                kps[5].y += 0.006
                kps[6].y -= 0.006
                kps[10].x += 0.012  # reaching right
            elif track_id == "T18":
                # T18 glances back left at T17, then right towards T19
                phase = math.sin(t_sec * 1.5)
                offset = 0.015 if phase > 0 else -0.015
                kps[0].x += offset
                # Hand extends across right desk boundary towards T19
                kps[10].x = seat.desk_x_max + 0.022
                kps[10].y = seat.y
            elif track_id == "T19":
                # T19 looks left at T18 and extends hand towards T18
                kps[0].x -= 0.016
                kps[9].x = seat.desk_x_min - 0.020
                kps[9].y = seat.y

        # Scenario 4: Desk Zone Breach (T08 reaching outside)
        elif sc == ScenarioType.DESK_ZONE_BREACH and track_id == "T08":
            # Right wrist reaches far into aisle/neighbor zone
            reach_offset = 0.035 + (math.sin(t_sec * 2.5) * 0.01)
            kps[10].x = seat.desk_x_max + reach_offset
            kps[10].y = seat.y + 0.015
            # Torso rotated
            kps[6].x += 0.01

        # Scenario 5: Fidgety Student (T03 naturally moving)
        elif sc == ScenarioType.FIDGETY_BASELINE_ADAPTATION and track_id == "T03":
            # Natural frequent posture shift
            wiggle = math.sin(t_sec * 3.5) * 0.009
            kps[0].x += wiggle
            kps[5].x += wiggle * 0.7
            kps[6].x += wiggle * 0.7
            kps[10].x += math.cos(t_sec * 4.0) * 0.008

        # Scenario 6: Invigilator Patrol Context
        elif sc == ScenarioType.INVIGILATOR_PATROL_CONTEXT:
            # Multiple students look up toward the moving proctor
            if seat.col_idx in [1, 2, 3]:
                # Look towards proctor y coordinate (higher up)
                kps[0].y -= 0.009  # nose up (pitch positive)
                kps[1].y -= 0.008
                kps[2].y -= 0.008

        return kps

    def generate_frame(self) -> FrameInput:
        """Generates the next simulated frame payload."""
        self.frame_id += 1
        curr_time_ms = self.start_time_ms + (self.frame_id * (1000.0 / self.fps))
        t_sec = (curr_time_ms - self.start_time_ms) / 1000.0

        track_poses: List[TrackPose] = []

        for track_id, seat_id in self.tracks.items():
            seat = self.layout.get_seat(seat_id)
            if not seat:
                continue

            is_fidgety = (track_id == "T03")
            raw_kps = self._generate_normal_keypoints(seat, t_sec, is_fidgety=is_fidgety)
            final_kps = self._apply_scenario_modifications(track_id, raw_kps, seat, t_sec)

            desk_zone = DeskZone(
                seat_id=seat_id,
                x_min=seat.desk_x_min,
                y_min=seat.desk_y_min,
                x_max=seat.desk_x_max,
                y_max=seat.desk_y_max,
                row=seat.row_idx,
                col=seat.col_idx,
            )

            bbox = BoundingBox(
                x_min=seat.x - 0.04,
                y_min=seat.y - 0.05,
                x_max=seat.x + 0.04,
                y_max=seat.y + 0.08,
            )

            track_poses.append(
                TrackPose(
                    track_id=track_id,
                    seat_id=seat_id,
                    keypoints=final_kps,
                    bbox=bbox,
                    desk_zone=desk_zone,
                    is_writing_tool_detected=True,
                )
            )

        # Invigilator state
        invigilators = []
        if self.current_scenario == ScenarioType.INVIGILATOR_PATROL_CONTEXT:
            # Move invigilator up and down central aisle (x ~ 0.5)
            self.invigilator_y += self.invigilator_dir * 0.004
            if self.invigilator_y > 0.85:
                self.invigilator_dir = -1.0
            elif self.invigilator_y < 0.15:
                self.invigilator_dir = 1.0

            invigilators.append(
                InvigilatorState(
                    invigilator_id="PROCTOR_1",
                    x=round(self.invigilator_x, 3),
                    y=round(self.invigilator_y, 3),
                    is_walking_in_aisle=True,
                    is_making_announcement=False,
                )
            )

        student_tracks = filter_student_tracks(
            track_poses,
            valid_seats=set(self.layout.seats.keys()),
        )

        return FrameInput(
            frame_id=self.frame_id,
            timestamp_ms=round(curr_time_ms, 2),
            room_id="HALL_101",
            tracks=student_tracks,
            invigilators=invigilators,
            exam_phase="IN_PROGRESS",
        )
