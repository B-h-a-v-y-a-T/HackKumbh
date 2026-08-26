"""Coordinated Group and Multi-Student Chain Detection Engine."""
import networkx as nx
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import GroupEventOutput, ReasonCode, BehaviourEvent
from .group_graph import SpatialTemporalGraph, InteractionEdge
from .hall_layout import ExamHallLayout


class CoordinatedGroupAnalysis(BaseModel):
    group_events: List[GroupEventOutput] = Field(default_factory=list)
    track_to_group_map: Dict[str, str] = Field(default_factory=dict)
    active_chains: List[List[str]] = Field(default_factory=list)
    detected_events_by_track: Dict[str, List[BehaviourEvent]] = Field(default_factory=dict)


class CoordinatedGroupDetector:
    """Detects multi-student coordinated behaviour and propagation chains (e.g. T17 -> T18 -> T19).
    
    Generates unified group-level alerts to prevent proctor alert fatigue.
    """

    def __init__(self, layout: Optional[ExamHallLayout] = None, chain_min_len: int = 2):
        self.layout = layout or ExamHallLayout()
        self.graph_builder = SpatialTemporalGraph(self.layout)
        self.chain_min_len = chain_min_len
        self._group_counter = 1
        self._active_group_ids: Dict[Tuple[str, ...], str] = {}

    def _get_group_id(self, participants: List[str]) -> str:
        """Maintains stable group IDs across consecutive frames for the same participant set."""
        key = tuple(sorted(participants))
        if key not in self._active_group_ids:
            self._active_group_ids[key] = f"G{self._group_counter}"
            self._group_counter += 1
        return self._active_group_ids[key]

    def analyze(
        self,
        tracks: List[TrackPose],
        gaze_results: Dict[str, any],
        hand_results: Dict[str, any],
        torso_results: Dict[str, any],
        timestamp_ms: float
    ) -> CoordinatedGroupAnalysis:
        """Identifies coordinated pairs, multi-student chains, and generates unified group events."""
        # 1. Build dynamic interaction graph
        edges = self.graph_builder.build_graph(
            tracks, gaze_results, hand_results, torso_results, timestamp_ms
        )
        G = self.graph_builder.graph

        track_map = {tr.track_id: tr for tr in tracks}
        group_events: List[GroupEventOutput] = []
        track_to_group: Dict[str, str] = {}
        all_chains: List[List[str]] = []
        events_by_track: Dict[str, List[BehaviourEvent]] = {tr.track_id: [] for tr in tracks}

        # 2. Search for Simple Paths / Directed Chains (e.g., T17 -> T18 -> T19)
        found_chains: List[List[str]] = []
        if G.number_of_edges() >= 2:
            nodes = list(G.nodes)
            for u in nodes:
                for v in nodes:
                    if u != v:
                        try:
                            for path in nx.all_simple_paths(G, source=u, target=v, cutoff=3):
                                if len(path) >= 3:  # 3 nodes = 2 edges chain
                                    found_chains.append(path)
                        except (nx.NetworkXNoPath, nx.NodeNotFound):
                            pass

        # 3. Connected Components Analysis on Undirected Projection of active edges
        undirected_G = G.to_undirected()
        connected_components = [
            list(c) for c in nx.connected_components(undirected_G) if len(c) >= 2
        ]

        processed_tracks: Set[str] = set()

        # Process Chains first (e.g. T17 -> T18 -> T19)
        for chain in found_chains:
            participants = chain
            group_id = self._get_group_id(participants)
            seats = [track_map[t].seat_id for t in participants if t in track_map]
            
            # Calculate group risk
            durations = [
                G[chain[i]][chain[i+1]].get("duration_sec", 0.0)
                for i in range(len(chain) - 1)
                if G.has_edge(chain[i], chain[i+1])
            ]
            avg_dur = sum(durations) / max(len(durations), 1)
            
            # Chain risk base = 75, scaling with duration
            group_risk = min(int(70 + min(avg_dur * 4.0, 25.0)), 98)

            chain_str = " → ".join(participants)
            seat_str = " → ".join(seats)
            desc = f"Coordinated information chain detected: {chain_str} across seats {seat_str}"

            group_ev = GroupEventOutput(
                group_id=group_id,
                group_risk=group_risk,
                confidence=0.91,
                event_type="CHAIN_INFORMATION_FLOW",
                participants=participants,
                seat_ids=seats,
                chain_path=chain,
                duration_sec=round(avg_dur, 2),
                reason_codes=[
                    ReasonCode.SPATIAL_CHAIN_PROPAGATION,
                    ReasonCode.SYNCHRONIZED_NEIGHBOUR_ACTIVITY,
                ],
                description=desc,
            )
            group_events.append(group_ev)
            all_chains.append(chain)

            for t in participants:
                track_to_group[t] = group_id
                processed_tracks.add(t)
                events_by_track[t].append(BehaviourEvent.CHAIN_INFORMATION_FLOW)

        # Process remaining Pairwise / Cluster components
        for comp in connected_components:
            # If all nodes in comp already in a chain, skip duplicate
            if all(t in processed_tracks for t in comp):
                continue

            participants = list(comp)
            group_id = self._get_group_id(participants)
            seats = [track_map[t].seat_id for t in participants if t in track_map]

            # Determine dominant interaction type
            has_hand = any(
                G[u][v].get("hand_reaching", False)
                for u in comp for v in comp if G.has_edge(u, v)
            )
            
            durations = [
                G[u][v].get("duration_sec", 0.0)
                for u in comp for v in comp if G.has_edge(u, v)
            ]
            avg_dur = sum(durations) / max(len(durations), 1)

            if has_hand:
                ev_type = "COORDINATED_HAND_EXCHANGE"
                base_risk = 75
                desc = f"Suspicious reach / exchange detected between {', '.join(participants)} (Seats {', '.join(seats)})"
                ev_enum = BehaviourEvent.COORDINATED_HAND_EXCHANGE
            else:
                ev_type = "COORDINATED_GAZE_PAIR"
                base_risk = 60
                desc = f"Synchronized neighbor gaze detected between {', '.join(participants)} (Seats {', '.join(seats)})"
                ev_enum = BehaviourEvent.COORDINATED_GAZE

            group_risk = min(int(base_risk + min(avg_dur * 3.0, 25.0)), 95)

            group_ev = GroupEventOutput(
                group_id=group_id,
                group_risk=group_risk,
                confidence=0.86,
                event_type=ev_type,
                participants=participants,
                seat_ids=seats,
                chain_path=None,
                duration_sec=round(avg_dur, 2),
                reason_codes=[ReasonCode.SYNCHRONIZED_NEIGHBOUR_ACTIVITY],
                description=desc,
            )
            group_events.append(group_ev)

            for t in participants:
                track_to_group[t] = group_id
                events_by_track[t].append(ev_enum)

        return CoordinatedGroupAnalysis(
            group_events=group_events,
            track_to_group_map=track_to_group,
            active_chains=all_chains,
            detected_events_by_track=events_by_track,
        )
