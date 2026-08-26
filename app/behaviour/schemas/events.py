"""Event and Risk Schemas for Behaviour & Spatial Intelligence."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BehaviourEvent(str, Enum):
    # Head & Gaze Events
    HEAD_TURN_LEFT = "HEAD_TURN_LEFT"
    HEAD_TURN_RIGHT = "HEAD_TURN_RIGHT"
    HEAD_DOWN_PROLONGED = "HEAD_DOWN_PROLONGED"
    HEAD_UP_SEARCHING = "HEAD_UP_SEARCHING"
    REPEATED_HEAD_TURN = "REPEATED_HEAD_TURN"
    NEIGHBOUR_GAZE = "NEIGHBOUR_GAZE"
    PROLONGED_NEIGHBOUR_GAZE = "PROLONGED_NEIGHBOUR_GAZE"
    
    # Torso & Posture Events
    TORSO_ROTATION = "TORSO_ROTATION"
    TORSO_ROTATION_LEFT = "TORSO_ROTATION_LEFT"
    TORSO_ROTATION_RIGHT = "TORSO_ROTATION_RIGHT"
    LEANING_OVER_DESK = "LEANING_OVER_DESK"
    
    # Hand & Desk Events
    UNUSUAL_HAND_MOVEMENT = "UNUSUAL_HAND_MOVEMENT"
    HAND_OUTSIDE_DESK_ZONE = "HAND_OUTSIDE_DESK_ZONE"
    REACHING_TOWARDS_NEIGHBOUR = "REACHING_TOWARDS_NEIGHBOUR"
    
    # Writing Activity
    WRITING_ACTIVE = "WRITING_ACTIVE"
    WRITING_STOP = "WRITING_STOP"
    WRITING_STOPPED_WHILE_LOOKING_AROUND = "WRITING_STOPPED_WHILE_LOOKING_AROUND"
    
    # Sequence & CTR-GCN Temporal Predictions
    SUSPICIOUS_SEQUENCE_DETECTED = "SUSPICIOUS_SEQUENCE_DETECTED"
    CTR_GCN_ANOMALOUS_POSE_PATTERN = "CTR_GCN_ANOMALOUS_POSE_PATTERN"
    
    # Coordinated Group Events
    COORDINATED_GAZE = "COORDINATED_GAZE"
    COORDINATED_HAND_EXCHANGE = "COORDINATED_HAND_EXCHANGE"
    CHAIN_INFORMATION_FLOW = "CHAIN_INFORMATION_FLOW"
    # Object & Contraband Evidence Events
    PAPER_CHIT_DETECTED = "PAPER_CHIT_DETECTED"
    OBJECT_EVIDENCE_DETECTED = "OBJECT_EVIDENCE_DETECTED"


class ReasonCode(str, Enum):
    NORMAL_TEST_TAKING = "NORMAL_TEST_TAKING"
    NATURAL_FIDGET_ADAPTED = "NATURAL_FIDGET_ADAPTED"
    HEAD_YAW_EXCEEDS_BASELINE = "HEAD_YAW_EXCEEDS_BASELINE"
    PROLONGED_NEIGHBOUR_GAZE_LEFT = "PROLONGED_NEIGHBOUR_GAZE_LEFT"
    PROLONGED_NEIGHBOUR_GAZE_RIGHT = "PROLONGED_NEIGHBOUR_GAZE_RIGHT"
    TORSO_ROTATION_EXCEEDS_THRESHOLD = "TORSO_ROTATION_EXCEEDS_THRESHOLD"
    WRIST_OUTSIDE_DESK_ZONE = "WRIST_OUTSIDE_DESK_ZONE"
    ERRATIC_HAND_VELOCITY = "ERRATIC_HAND_VELOCITY"
    WRITING_HALTED_PROLONGED = "WRITING_HALTED_PROLONGED"
    SUSPICIOUS_MULTISTEP_SEQUENCE = "SUSPICIOUS_MULTISTEP_SEQUENCE"
    SYNCHRONIZED_NEIGHBOUR_ACTIVITY = "SYNCHRONIZED_NEIGHBOUR_ACTIVITY"
    SPATIAL_CHAIN_PROPAGATION = "SPATIAL_CHAIN_PROPAGATION"
    OCCLUSION_LOW_VISIBILITY = "OCCLUSION_LOW_VISIBILITY"
    INVIGILATOR_PASSING_SUPPRESSION = "INVIGILATOR_PASSING_SUPPRESSION"
    PAPER_CHIT_SUSPICION = "PAPER_CHIT_SUSPICION"
    CONTRABAND_ROI_EVIDENCE = "CONTRABAND_ROI_EVIDENCE"


class RiskStatus(str, Enum):
    NORMAL = "NORMAL"
    MONITORING = "MONITORING"
    UNUSUAL_BEHAVIOUR = "UNUSUAL_BEHAVIOUR"
    SUSPICIOUS_BEHAVIOUR = "SUSPICIOUS_BEHAVIOUR"


class TrackRiskOutput(BaseModel):
    """Real-time risk assessment output for an individual anonymous track."""
    track_id: str = Field(..., description="Anonymous track identifier, e.g. T17")
    seat_id: str = Field(..., description="Seat designation, e.g. B4")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score between 0 and 100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence 0.0 - 1.0")
    events: List[str] = Field(default_factory=list, description="Active detected behaviour events")
    group_id: Optional[str] = Field(default=None, description="Assigned spatial group ID if in coordinated event, e.g. G3")
    duration_sec: float = Field(default=0.0, description="Duration in seconds of ongoing sustained behaviour")
    
    # Enriched diagnostic fields
    baseline_deviation: float = Field(default=0.0, description="Z-score deviation from student's personal baseline")
    reason_codes: List[ReasonCode] = Field(default_factory=list, description="Detailed explanatory reason codes")
    status: RiskStatus = Field(default=RiskStatus.NORMAL, description="Advisory status classification (never Cheating)")
    gaze_angle_deg: Optional[float] = Field(default=None, description="Estimated head yaw angle in degrees")
    torso_angle_deg: Optional[float] = Field(default=None, description="Estimated torso rotation angle in degrees")
    hand_outside_zone: bool = Field(default=False, description="Whether hand is currently beyond desk boundary")
    writing_active: bool = Field(default=True, description="Whether student is actively writing")
    is_suppressed_by_context: bool = Field(default=False, description="Whether risk is suppressed by invigilator or occlusion")
    object_evidence: Optional[List[Dict[str, Any]]] = Field(default=None, description="Part 3 verified object evidence")
    temporal_object_score: Optional[float] = Field(default=None, description="Multi-frame accumulated object confidence")


class GroupEventOutput(BaseModel):
    """Unified group-level event aggregating multi-student coordinated behaviour."""
    group_id: str = Field(..., description="Unique Group Event ID, e.g. G3")
    group_risk: int = Field(..., ge=0, le=100, description="Combined group risk score 0 - 100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Group detection confidence")
    event_type: str = Field(..., description="e.g. COORDINATED_GAZE_CHAIN, SUSPICIOUS_PASSING_PAIR")
    participants: List[str] = Field(..., description="List of participant track IDs, e.g. ['T17', 'T18', 'T19']")
    seat_ids: List[str] = Field(..., description="Seats involved, e.g. ['B3', 'B4', 'B5']")
    chain_path: Optional[List[str]] = Field(default=None, description="Ordered propagation chain, e.g. ['T17', 'T18', 'T19']")
    duration_sec: float = Field(default=0.0, description="Duration in seconds of coordinated activity")
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    description: str = Field(..., description="Human-readable explanation for invigilator")


class InvigilatorDecision(BaseModel):
    """Human-in-the-loop invigilator feedback or action."""
    action_id: str
    track_id: Optional[str] = None
    group_id: Optional[str] = None
    action_type: str = Field(..., description="ACKNOWLEDGE, MARK_NATURAL, FLAG_IN_PERSON, DISMISS")
    notes: Optional[str] = None
    timestamp_ms: float


class FrameAnalysisResponse(BaseModel):
    """Complete response payload for a processed frame."""
    frame_id: int
    timestamp_ms: float
    room_id: str
    tracks: List[TrackRiskOutput]
    groups: List[GroupEventOutput]
    global_invigilator_context: Dict[str, Any] = Field(default_factory=dict)
    system_latency_ms: float = 0.0
