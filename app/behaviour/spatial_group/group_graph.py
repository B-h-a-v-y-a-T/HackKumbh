"""Spatial-Temporal Interaction Graph for Exam Hall."""
import networkx as nx
import numpy as np
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import BehaviourEvent
from .hall_layout import ExamHallLayout


class InteractionEdge(BaseModel):
    source_track: str
    target_track: str
    source_seat: str
    target_seat: str
    weight: float = 0.0
    interaction_types: List[str] = Field(default_factory=list)
    is_gaze_directed: bool = False
    is_hand_reaching: bool = False
    is_synchronized: bool = False
    duration_sec: float = 0.0


class SpatialTemporalGraph:
    """Dynamic directed graph modeling spatial-temporal interactions between students."""

    def __init__(self, layout: Optional[ExamHallLayout] = None, proximity_threshold: float = 0.28):
        self.layout = layout or ExamHallLayout()
        self.prox_thresh = proximity_threshold
        self.graph = nx.DiGraph()
        
        # Edge duration tracking: {(u, v): {"start_ms": float, "duration_sec": float}}
        self._edge_durations: Dict[Tuple[str, str], Dict] = {}

    def build_graph(
        self,
        tracks: List[TrackPose],
        gaze_results: Dict[str, any],
        hand_results: Dict[str, any],
        torso_results: Dict[str, any],
        timestamp_ms: float
    ) -> List[InteractionEdge]:
        """Builds directed interaction edges between active tracks based on spatial proximity & behaviour."""
        self.graph.clear()
        
        # Add nodes
        for tr in tracks:
            self.graph.add_node(tr.track_id, seat_id=tr.seat_id, track=tr)

        active_edges: List[InteractionEdge] = []
        track_map = {tr.track_id: tr for tr in tracks}

        # Evaluate pairs
        for i, tr_a in enumerate(tracks):
            gaze_a = gaze_results.get(tr_a.track_id)
            hand_a = hand_results.get(tr_a.track_id)
            torso_a = torso_results.get(tr_a.track_id)

            for j, tr_b in enumerate(tracks):
                if i == j:
                    continue

                seat_a = tr_a.seat_id
                seat_b = tr_b.seat_id
                dist = self.layout.get_distance(seat_a, seat_b)

                # Only immediate or nearby neighbors
                if dist > self.prox_thresh:
                    continue

                rel_dir = self.layout.get_relative_direction(seat_a, seat_b)
                
                # Check 1: Is Track A looking towards Track B's seat?
                gaze_directed = False
                if gaze_a:
                    if rel_dir == "LEFT" and gaze_a.yaw_deg < -22.0:
                        gaze_directed = True
                    elif rel_dir == "RIGHT" and gaze_a.yaw_deg > 22.0:
                        gaze_directed = True
                    elif rel_dir == "FRONT" and gaze_a.pitch_deg > 12.0:
                        gaze_directed = True

                # Check 2: Is Track A reaching hand toward Track B?
                hand_reaching = False
                if hand_a and hand_a.hand_outside_zone:
                    if rel_dir == "LEFT" and hand_a.reach_direction == "LEFT":
                        hand_reaching = True
                    elif rel_dir == "RIGHT" and hand_a.reach_direction == "RIGHT":
                        hand_reaching = True

                # Check 3: Torso rotation towards B
                torso_aligned = False
                if torso_a and torso_a.is_rotated:
                    if rel_dir == "LEFT" and torso_a.rotation_direction == "LEFT":
                        torso_aligned = True
                    elif rel_dir == "RIGHT" and torso_a.rotation_direction == "RIGHT":
                        torso_aligned = True

                # Compute Edge Weight (0.0 to 1.0)
                types = []
                weight = 0.0

                if gaze_directed:
                    weight += 0.45
                    types.append("GAZE_PEEK")
                if hand_reaching:
                    weight += 0.40
                    types.append("HAND_REACH")
                if torso_aligned:
                    weight += 0.25
                    types.append("TORSO_ALIGNED")

                # If distance is very close (immediate neighbor), boost weight
                if self.layout.is_immediate_neighbor(seat_a, seat_b):
                    weight *= 1.15

                weight = min(weight, 1.0)

                # If significant interaction exists, create edge
                if weight >= 0.35:
                    edge_key = (tr_a.track_id, tr_b.track_id)
                    dur = 0.0
                    if edge_key in self._edge_durations:
                        dur = self._edge_durations[edge_key]["duration_sec"] + 0.1
                        self._edge_durations[edge_key]["duration_sec"] = dur
                    else:
                        self._edge_durations[edge_key] = {"start_ms": timestamp_ms, "duration_sec": 0.1}

                    self.graph.add_edge(
                        tr_a.track_id,
                        tr_b.track_id,
                        weight=weight,
                        types=types,
                        gaze_directed=gaze_directed,
                        hand_reaching=hand_reaching,
                        duration_sec=dur
                    )

                    active_edges.append(
                        InteractionEdge(
                            source_track=tr_a.track_id,
                            target_track=tr_b.track_id,
                            source_seat=seat_a,
                            target_seat=seat_b,
                            weight=round(weight, 2),
                            interaction_types=types,
                            is_gaze_directed=gaze_directed,
                            is_hand_reaching=hand_reaching,
                            duration_sec=round(dur, 2),
                        )
                    )

        # Cleanup expired edges
        current_active_keys = {(e.source_track, e.target_track) for e in active_edges}
        for k in list(self._edge_durations.keys()):
            if k not in current_active_keys:
                del self._edge_durations[k]

        return active_edges
