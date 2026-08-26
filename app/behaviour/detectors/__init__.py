"""Behaviour detectors — head/gaze, torso, hand, writing, sequence."""

from app.behaviour.detectors.head_gaze import HeadGazeDetector
from app.behaviour.detectors.torso_posture import TorsoPostureDetector
from app.behaviour.detectors.hand_desk_zone import HandDeskZoneDetector
from app.behaviour.detectors.writing_activity import WritingActivityDetector
from app.behaviour.detectors.sequence_automaton import SequenceAutomaton

__all__ = [
    "HeadGazeDetector", "TorsoPostureDetector",
    "HandDeskZoneDetector", "WritingActivityDetector",
    "SequenceAutomaton",
]
