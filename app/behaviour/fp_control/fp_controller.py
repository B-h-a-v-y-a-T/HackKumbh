"""False-Positive Filter and Context-Aware Risk Damper."""
import math
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose, InvigilatorState
from app.behaviour.schemas.events import ReasonCode, BehaviourEvent
from app.behaviour.spatial_group.hall_layout import ExamHallLayout


class FilteredDecision(BaseModel):
    track_id: str
    is_suppressed: bool = False
    suppression_reason: Optional[ReasonCode] = None
    confidence_penalty: float = 0.0
    risk_dampening_factor: float = 1.0  # Multiplier between 0.0 (fully suppressed) and 1.0 (unsuppressed)
    active_events: List[str] = Field(default_factory=list)


class FalsePositiveController:
    """Controls false alarms caused by occlusion, brief natural movements, and invigilator patrol context."""

    def __init__(
        self,
        layout: Optional[ExamHallLayout] = None,
        min_keypoint_confidence: float = 0.35,
        invigilator_proximity_radius: float = 0.28,
        transient_duration_threshold_sec: float = 0.8,
    ):
        self.layout = layout or ExamHallLayout()
        self.min_confidence = min_keypoint_confidence
        self.invigilator_radius = invigilator_proximity_radius
        self.transient_thresh_sec = transient_duration_threshold_sec

    def evaluate(
        self,
        track: TrackPose,
        gaze_res: any,
        torso_res: any,
        hand_res: any,
        baseline_res: any,
        invigilators: Optional[List[InvigilatorState]] = None,
    ) -> FilteredDecision:
        """Evaluates raw detections and computes context dampening / suppression."""
        is_suppressed = False
        suppression_reason = None
        dampening_factor = 1.0
        conf_penalty = 0.0

        seat_loc = self.layout.get_seat(track.seat_id)

        # 1. Keypoint Confidence & Occlusion Check
        # Only dampen head gaze if hands are normal; if hands are outside desk (chit / reach), do not suppress!
        has_hand_anomaly = bool(hand_res and (hand_res.hand_outside_zone or hand_res.is_reaching_neighbor or hand_res.is_unusual_hand_movement))
        if gaze_res and gaze_res.confidence < self.min_confidence and not has_hand_anomaly:
            conf_penalty += 0.4
            dampening_factor *= 0.5
            is_suppressed = True
            suppression_reason = ReasonCode.OCCLUSION_LOW_VISIBILITY

        # 2. Transient Natural Movement Check
        # Only mildly dampen very fleeting glances if angle is small (< 24 deg)
        if gaze_res and gaze_res.is_neighbor_gaze and gaze_res.neighbor_gaze_duration_sec < 0.35 and abs(getattr(gaze_res, "yaw_deg", 0.0)) < 24.0:
            dampening_factor *= 0.75

        # 3. Invigilator Patrol / Announcement Context
        if invigilators and seat_loc:
            for proctor in invigilators:
                # Check if proctor is making global announcement
                if proctor.is_making_announcement:
                    # All students looking up/around is expected
                    dampening_factor *= 0.15
                    is_suppressed = True
                    suppression_reason = ReasonCode.INVIGILATOR_PASSING_SUPPRESSION
                    break

                # Check if proctor is physically walking down aisle near student
                dist = math.hypot(seat_loc.x - proctor.x, seat_loc.y - proctor.y)
                if dist < self.invigilator_radius:
                    # Student looking towards proctor's direction is normal
                    dampening_factor *= 0.25
                    is_suppressed = True
                    suppression_reason = ReasonCode.INVIGILATOR_PASSING_SUPPRESSION
                    break

        # 4. Natural Fidget Calibration Check
        if baseline_res and baseline_res.is_natural_fidget:
            dampening_factor *= 0.4
            suppression_reason = ReasonCode.NATURAL_FIDGET_ADAPTED

        return FilteredDecision(
            track_id=track.track_id,
            is_suppressed=is_suppressed,
            suppression_reason=suppression_reason,
            confidence_penalty=round(conf_penalty, 2),
            risk_dampening_factor=round(dampening_factor, 2),
        )
