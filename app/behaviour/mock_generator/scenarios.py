"""Scenario Definitions and Configurations for Mock Exam Hall Simulations."""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    NORMAL_HALL = "NORMAL_HALL"
    NEIGHBOUR_GAZE_PEEK = "NEIGHBOUR_GAZE_PEEK"
    COORDINATED_CHAIN_T17_T18_T19 = "COORDINATED_CHAIN_T17_T18_T19"
    DESK_ZONE_BREACH = "DESK_ZONE_BREACH"
    FIDGETY_BASELINE_ADAPTATION = "FIDGETY_BASELINE_ADAPTATION"
    INVIGILATOR_PATROL_CONTEXT = "INVIGILATOR_PATROL_CONTEXT"
    COMPOSITE_MULTI_ANOMALY = "COMPOSITE_MULTI_ANOMALY"


class ScenarioConfig(BaseModel):
    id: ScenarioType
    title: str
    description: str
    target_tracks: List[str] = Field(default_factory=list)
    has_invigilator: bool = False
    invigilator_walking: bool = False
    fidgety_tracks: List[str] = Field(default_factory=list)
    expected_outcome: str


SCENARIO_PRESETS: Dict[ScenarioType, ScenarioConfig] = {
    ScenarioType.NORMAL_HALL: ScenarioConfig(
        id=ScenarioType.NORMAL_HALL,
        title="1. Normal Exam Hall Baseline",
        description="15 anonymous students writing calmly with natural micro-movements and occasional head shifts.",
        target_tracks=[],
        has_invigilator=True,
        invigilator_walking=False,
        fidgety_tracks=[],
        expected_outcome="All students maintain low risk (0-15). Status stays NORMAL.",
    ),
    ScenarioType.NEIGHBOUR_GAZE_PEEK: ScenarioConfig(
        id=ScenarioType.NEIGHBOUR_GAZE_PEEK,
        title="2. Sustained Neighbour Gaze & Torso Rotation",
        description="Student T14 (Seat B3) stops writing, turns head and rotates torso towards right neighbor T15 (Seat B4).",
        target_tracks=["T14"],
        has_invigilator=False,
        invigilator_walking=False,
        fidgety_tracks=[],
        expected_outcome="T14 risk escalates to 75-85 with REPEATED_HEAD_TURN, NEIGHBOUR_GAZE, TORSO_ROTATION reason codes.",
    ),
    ScenarioType.COORDINATED_CHAIN_T17_T18_T19: ScenarioConfig(
        id=ScenarioType.COORDINATED_CHAIN_T17_T18_T19,
        title="3. Spatial Chain Intelligence (T17 → T18 → T19)",
        description="Coordinated information propagation chain across Row B: T17 glances at T18, T18 reaches/whispers to T19.",
        target_tracks=["T17", "T18", "T19"],
        has_invigilator=False,
        invigilator_walking=False,
        fidgety_tracks=[],
        expected_outcome="Generates a single unified group event (G3) for T17 -> T18 -> T19, avoiding 3 separate individual alerts.",
    ),
    ScenarioType.DESK_ZONE_BREACH: ScenarioConfig(
        id=ScenarioType.DESK_ZONE_BREACH,
        title="4. Hand Outside Desk Boundary",
        description="Student T08 (Seat C2) repeatedly reaches hand across the aisle boundary into neighbor space.",
        target_tracks=["T08"],
        has_invigilator=False,
        invigilator_walking=False,
        fidgety_tracks=[],
        expected_outcome="Flags HAND_OUTSIDE_DESK_ZONE with boundary violation telemetry and high kinetic wrist velocity.",
    ),
    ScenarioType.FIDGETY_BASELINE_ADAPTATION: ScenarioConfig(
        id=ScenarioType.FIDGETY_BASELINE_ADAPTATION,
        title="5. Personal Baseline Adaptation (Neurodiverse/Fidgety)",
        description="Student T03 naturally shifts posture and fidgets frequently. Demonstrates dynamic baseline calibration.",
        target_tracks=[],
        has_invigilator=False,
        invigilator_walking=False,
        fidgety_tracks=["T03"],
        expected_outcome="Risk engine calibrates to T03's personal movement variance, suppressing false alarms (NATURAL_FIDGET_ADAPTED).",
    ),
    ScenarioType.INVIGILATOR_PATROL_CONTEXT: ScenarioConfig(
        id=ScenarioType.INVIGILATOR_PATROL_CONTEXT,
        title="6. Context Awareness: Invigilator Patrol",
        description="Invigilator walks down the central aisle. Multiple students look up towards the proctor simultaneously.",
        target_tracks=[],
        has_invigilator=True,
        invigilator_walking=True,
        fidgety_tracks=[],
        expected_outcome="Context controller recognizes proctor proximity and suppresses false group/individual alerts.",
    ),
}
