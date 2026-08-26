"""
Dynamic seat detection and track-to-seat association.

Discovers seats from stable student positions over time.
Supports manual seat maps, dynamic rearrangement, and vacant seat detection.
Track identity is separate from seat identity: a student is Track T5 at Seat S3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.perception.core.constants import (
    DEFAULT_SEAT_MERGE_DISTANCE,
    DEFAULT_SEAT_STABILITY_FRAMES,
    VisibilityLevel,
)
from app.perception.core.data_models import SeatInfo, TrackedObject

logger = logging.getLogger(__name__)


@dataclass
class _SeatCandidate:
    """Internal representation of a discovered or configured seat."""
    seat_id: str
    position: np.ndarray          # (2,) centroid in frame coords
    stability_count: int = 0       # How many frames this position has been stable
    is_confirmed: bool = False     # True after stability threshold reached
    assigned_track_id: Optional[int] = None
    vacant_frames: int = 0         # Frames since last occupancy
    visibility_history: List[float] = field(default_factory=list)

    @property
    def camera_visibility(self) -> VisibilityLevel:
        """Compute camera visibility level from recent history."""
        if not self.visibility_history:
            return VisibilityLevel.GOOD
        avg = np.mean(self.visibility_history[-30:])  # Last 30 frames
        if avg >= 0.7:
            return VisibilityLevel.GOOD
        elif avg >= 0.4:
            return VisibilityLevel.PARTIAL
        return VisibilityLevel.POOR


class SeatManager:
    """
    Manages seat discovery, association, and occupancy tracking.

    Seats are discovered dynamically from stable student positions.
    Optionally, a manual seat map can be loaded from configuration.

    Args:
        stability_frames: Frames required at same position to confirm a seat.
        merge_distance: Pixel distance to merge nearby seat candidates.
        max_assignment_distance: Max pixel distance for track-to-seat assignment.
        seat_prefix: Prefix for auto-generated seat IDs.
    """

    def __init__(
        self,
        stability_frames: int = DEFAULT_SEAT_STABILITY_FRAMES,
        merge_distance: float = DEFAULT_SEAT_MERGE_DISTANCE,
        max_assignment_distance: float = 150.0,
        seat_prefix: str = "S",
    ):
        self.stability_frames = stability_frames
        self.merge_distance = merge_distance
        self.max_assignment_distance = max_assignment_distance
        self.seat_prefix = seat_prefix

        self._seats: Dict[str, _SeatCandidate] = {}
        self._next_seat_num = 1
        self._candidates: List[_SeatCandidate] = []

    def load_seat_map(self, seat_map: Dict[str, Tuple[float, float]]):
        """
        Load a pre-configured seat map.

        Args:
            seat_map: Dict of seat_id → (x, y) position in frame coordinates.
                      e.g., {"S1": (200, 300), "S2": (500, 300)}
        """
        for seat_id, (x, y) in seat_map.items():
            self._seats[seat_id] = _SeatCandidate(
                seat_id=seat_id,
                position=np.array([x, y], dtype=np.float32),
                is_confirmed=True,
                stability_count=self.stability_frames,
            )
        logger.info("Loaded %d seats from manual seat map.", len(seat_map))

    def update(
        self,
        tracked_objects: List[TrackedObject],
        visibility_scores: Optional[Dict[int, float]] = None,
    ) -> Dict[int, SeatInfo]:
        """
        Update seat associations for current frame.

        Args:
            tracked_objects: Currently tracked persons.
            visibility_scores: Optional overall visibility score per track_id.

        Returns:
            Dict mapping track_id → SeatInfo.
        """
        if not tracked_objects:
            # Mark all seats as vacant
            for seat in self._seats.values():
                seat.vacant_frames += 1
                seat.assigned_track_id = None
            return {}

        # Step 1: Update seat candidates from stable track positions
        self._update_candidates(tracked_objects)

        # Step 2: Assign tracks to confirmed seats
        assignments = self._assign_tracks_to_seats(tracked_objects)

        # Step 3: Update visibility history
        if visibility_scores:
            for seat in self._seats.values():
                if seat.assigned_track_id in visibility_scores:
                    vis = visibility_scores[seat.assigned_track_id]
                    seat.visibility_history.append(vis)
                    # Keep only last 300 frames of history
                    if len(seat.visibility_history) > 300:
                        seat.visibility_history = seat.visibility_history[-300:]

        # Step 4: Build SeatInfo results
        result: Dict[int, SeatInfo] = {}
        for track_id, seat_id in assignments.items():
            seat = self._seats.get(seat_id)
            if seat is not None:
                result[track_id] = SeatInfo(
                    seat_id=seat_id,
                    position=(float(seat.position[0]), float(seat.position[1])),
                    assignment_confidence=self._compute_confidence(
                        tracked_objects, track_id, seat
                    ),
                    is_vacant=False,
                )
            else:
                result[track_id] = SeatInfo(seat_id="UNASSIGNED")

        # Assign UNASSIGNED for tracks without a seat
        for track in tracked_objects:
            if track.track_id not in result:
                result[track.track_id] = SeatInfo(seat_id="UNASSIGNED")

        return result

    def _update_candidates(self, tracked_objects: List[TrackedObject]):
        """Discover new seats from stable track positions."""
        updated_candidates: set = set()

        for track in tracked_objects:
            pos = np.array(track.bbox.center, dtype=np.float32)

            # Check if this position matches an existing seat
            matched_seat = self._find_nearest_seat(pos)
            if matched_seat is not None:
                # Update seat position with exponential moving average
                alpha = 0.05
                matched_seat.position = (
                    (1 - alpha) * matched_seat.position + alpha * pos
                )
                matched_seat.stability_count += 1
                matched_seat.vacant_frames = 0
                continue

            # Check if this position matches an existing candidate
            matched_candidate = None
            for cand in self._candidates:
                dist = np.linalg.norm(cand.position - pos)
                if dist < self.merge_distance:
                    matched_candidate = cand
                    break

            if matched_candidate is not None:
                matched_candidate.stability_count += 1
                updated_candidates.add(id(matched_candidate))
                alpha = 0.1
                matched_candidate.position = (
                    (1 - alpha) * matched_candidate.position + alpha * pos
                )

                # Promote to confirmed seat
                if matched_candidate.stability_count >= self.stability_frames:
                    matched_candidate.is_confirmed = True
                    self._seats[matched_candidate.seat_id] = matched_candidate
                    self._candidates.remove(matched_candidate)
                    logger.info(
                        "Seat %s confirmed at (%.0f, %.0f)",
                        matched_candidate.seat_id,
                        matched_candidate.position[0],
                        matched_candidate.position[1],
                    )
            else:
                # Create new candidate
                seat_id = f"{self.seat_prefix}{self._next_seat_num}"
                self._next_seat_num += 1
                new_cand = _SeatCandidate(
                    seat_id=seat_id,
                    position=pos.copy(),
                    stability_count=1,
                )
                self._candidates.append(new_cand)
                updated_candidates.add(id(new_cand))

        # Decay stability for candidates NOT updated this frame
        for cand in self._candidates:
            if id(cand) not in updated_candidates:
                cand.stability_count = max(0, cand.stability_count - 1)

        # Clean up stale candidates (not seen for too long)
        self._candidates = [
            c for c in self._candidates
            if c.stability_count > 0
        ]

    def _find_nearest_seat(
        self, position: np.ndarray
    ) -> Optional[_SeatCandidate]:
        """Find the nearest confirmed seat within merge distance."""
        best = None
        best_dist = self.merge_distance * 2  # Use larger threshold for confirmed
        for seat in self._seats.values():
            dist = float(np.linalg.norm(seat.position - position))
            if dist < best_dist:
                best = seat
                best_dist = dist
        return best

    def _assign_tracks_to_seats(
        self, tracked_objects: List[TrackedObject]
    ) -> Dict[int, str]:
        """Assign tracks to seats using Hungarian algorithm."""
        if not self._seats or not tracked_objects:
            return {}

        seat_list = list(self._seats.values())
        n_tracks = len(tracked_objects)
        n_seats = len(seat_list)

        # Cost matrix: distance between track centers and seat positions
        cost = np.full((n_tracks, n_seats), 1e6, dtype=np.float64)
        for i, track in enumerate(tracked_objects):
            pos = np.array(track.bbox.center, dtype=np.float32)
            for j, seat in enumerate(seat_list):
                dist = float(np.linalg.norm(pos - seat.position))
                if dist <= self.max_assignment_distance:
                    cost[i, j] = dist

        row_idx, col_idx = linear_sum_assignment(cost)

        assignments: Dict[int, str] = {}
        # Reset all seat assignments
        for seat in seat_list:
            seat.assigned_track_id = None
            seat.vacant_frames += 1

        for r, c in zip(row_idx, col_idx):
            if cost[r, c] < self.max_assignment_distance:
                track = tracked_objects[r]
                seat = seat_list[c]
                assignments[track.track_id] = seat.seat_id
                seat.assigned_track_id = track.track_id
                seat.vacant_frames = 0

        return assignments

    def _compute_confidence(
        self,
        tracked_objects: List[TrackedObject],
        track_id: int,
        seat: _SeatCandidate,
    ) -> float:
        """Compute assignment confidence based on distance and stability."""
        track = None
        for t in tracked_objects:
            if t.track_id == track_id:
                track = t
                break
        if track is None:
            return 0.0

        pos = np.array(track.bbox.center, dtype=np.float32)
        dist = float(np.linalg.norm(pos - seat.position))

        # Distance-based confidence (closer = higher)
        dist_conf = max(0.0, 1.0 - dist / self.max_assignment_distance)

        # Stability-based confidence
        stab_conf = min(1.0, seat.stability_count / self.stability_frames)

        return 0.6 * dist_conf + 0.4 * stab_conf

    def get_seat_visibility(self, seat_id: str) -> VisibilityLevel:
        """Get the camera visibility level for a specific seat."""
        seat = self._seats.get(seat_id)
        if seat is None:
            return VisibilityLevel.GOOD
        return seat.camera_visibility

    def get_all_seats(self) -> Dict[str, SeatInfo]:
        """Return info for all confirmed seats."""
        result = {}
        for seat_id, seat in self._seats.items():
            result[seat_id] = SeatInfo(
                seat_id=seat_id,
                position=(float(seat.position[0]), float(seat.position[1])),
                assignment_confidence=float(
                    min(1.0, seat.stability_count / self.stability_frames)
                ),
                is_vacant=seat.vacant_frames > 30,
            )
        return result

    @property
    def confirmed_seat_count(self) -> int:
        return len(self._seats)

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)
