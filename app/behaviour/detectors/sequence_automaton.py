"""
Suspicious Sequence Detection Automaton.

Detects multi-step composite temporal patterns across sliding time windows:
- Pattern A: COORDINATED_PEEK_AND_REACH (Writing Stop/Torso -> Neighbor Gaze -> Hand Reach)
- Pattern B: SUSTAINED_TORSO_AND_REPEATED_PEEK (Torso Rotation -> Repeated Neighbor Glances)
- Pattern C: HALTED_WRITING_REPEATED_GLANCE (Writing Stop -> Repeated Head Turns)
- Pattern D: DESK_BREACH_AND_LOOK (Hand Outside Zone -> Gaze towards Neighbor)
- Pattern E: PROLONGED_SEARCH_AND_GLANCE (Head Up Searching -> Lateral Glance)
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.behaviour.schemas.events import BehaviourEvent, ReasonCode


class SequenceDetectionResult(BaseModel):
    track_id: str
    sequence_detected: bool = False
    sequence_name: Optional[str] = None
    sequence_steps: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class SequenceAutomaton:
    """Detects multi-step composite temporal patterns across sliding time windows."""

    def __init__(self, sequence_window_sec: float = 12.0):
        self.window_sec = sequence_window_sec
        # Store recent event log per track: {track_id: [(timestamp_ms, event_name)]}
        self._event_histories: Dict[str, List] = {}

    def reset_track(self, track_id: str):
        if track_id in self._event_histories:
            del self._event_histories[track_id]

    def record_events(
        self,
        track_id: str,
        events: List[BehaviourEvent],
        timestamp_ms: float,
    ) -> SequenceDetectionResult:
        """Records active events and evaluates sequence automata."""
        if track_id not in self._event_histories:
            self._event_histories[track_id] = []

        history = self._event_histories[track_id]

        # Add new events (avoid spamming duplicate entries within 800ms)
        recent_names = {e[1] for e in history if (timestamp_ms - e[0]) < 800.0}
        for ev in events:
            if ev.value not in recent_names:
                history.append((timestamp_ms, ev.value))

        # Prune older than window
        cutoff_ms = timestamp_ms - (self.window_sec * 1000.0)
        history = [item for item in history if item[0] >= cutoff_ms]
        self._event_histories[track_id] = history

        event_names = [item[1] for item in history]

        # Event presence indicators
        has_stop = ("WRITING_STOP" in event_names) or ("WRITING_STOPPED_WHILE_LOOKING_AROUND" in event_names)
        has_gaze = ("NEIGHBOUR_GAZE" in event_names) or ("PROLONGED_NEIGHBOUR_GAZE" in event_names)
        has_reach = ("HAND_OUTSIDE_DESK_ZONE" in event_names) or ("REACHING_TOWARDS_NEIGHBOUR" in event_names)
        has_torso = ("TORSO_ROTATION" in event_names) or ("TORSO_ROTATION_LEFT" in event_names) or ("TORSO_ROTATION_RIGHT" in event_names)
        has_repeated = "REPEATED_HEAD_TURN" in event_names
        has_head_up = "HEAD_UP_SEARCHING" in event_names

        detected = False
        seq_name = None
        steps = []
        conf = 0.0

        if has_gaze and has_reach and (has_stop or has_torso):
            detected = True
            seq_name = "COORDINATED_PEEK_AND_REACH"
            steps = ["WRITING_STOP/TORSO_ROTATION", "NEIGHBOUR_GAZE", "HAND_REACH_OUTSIDE_DESK"]
            conf = 0.92
        elif has_torso and has_gaze and has_repeated:
            detected = True
            seq_name = "SUSTAINED_TORSO_AND_REPEATED_PEEK"
            steps = ["TORSO_ROTATION", "REPEATED_HEAD_TURN", "NEIGHBOUR_GAZE"]
            conf = 0.88
        elif has_stop and has_repeated and has_gaze:
            detected = True
            seq_name = "HALTED_WRITING_REPEATED_GLANCE"
            steps = ["WRITING_STOP", "REPEATED_HEAD_TURN", "NEIGHBOUR_GAZE"]
            conf = 0.84
        elif has_reach and has_gaze:
            detected = True
            seq_name = "DESK_BREACH_AND_LOOK"
            steps = ["HAND_OUTSIDE_DESK_ZONE", "NEIGHBOUR_GAZE"]
            conf = 0.80
        elif has_head_up and has_gaze and (has_repeated or has_reach):
            detected = True
            seq_name = "PROLONGED_SEARCH_AND_GLANCE"
            steps = ["HEAD_UP_SEARCHING", "LATERAL_GLANCE"]
            conf = 0.75

        out_events = [BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED] if detected else []
        out_reasons = [ReasonCode.SUSPICIOUS_MULTISTEP_SEQUENCE] if detected else []

        return SequenceDetectionResult(
            track_id=track_id,
            sequence_detected=detected,
            sequence_name=seq_name,
            sequence_steps=steps,
            confidence=conf,
            detected_events=out_events,
            reason_codes=out_reasons,
        )
