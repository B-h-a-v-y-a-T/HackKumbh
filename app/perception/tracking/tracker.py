"""
Multi-person tracker wrapping Ultralytics integrated ByteTrack with Persistent Re-ID & Spatial De-duplication.

Assigns anonymous canonical track IDs (T1, T2...) that remain strictly stable throughout the examination,
eliminating track flickering, ghost duplicate skeletons, and ID churn.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.perception.core.constants import DEFAULT_COAST_FRAMES, TrackingState
from app.perception.core.data_models import BoundingBox, Detection, TrackedObject

logger = logging.getLogger(__name__)


def _suppress_duplicate_detections(
    detections: List[Detection],
    track_ids: Optional[List[int]] = None,
    iou_thresh: float = 0.40,
) -> Tuple[List[Detection], List[int]]:
    """
    Non-Maximum Suppression across detections in the same frame to eliminate duplicate boxes.
    """
    if not detections:
        return [], []

    has_ids = track_ids is not None and len(track_ids) == len(detections)
    indices = list(range(len(detections)))
    # Sort by confidence descending
    indices.sort(key=lambda i: (detections[i].bbox.confidence if detections[i].bbox else 0.0), reverse=True)

    kept_indices: List[int] = []
    for i in indices:
        box_i = detections[i].bbox
        is_dup = False
        for k in kept_indices:
            box_k = detections[k].bbox
            if box_i.iou(box_k) >= iou_thresh:
                is_dup = True
                break
        if not is_dup:
            kept_indices.append(i)

    # Maintain original order among kept
    kept_set = set(kept_indices)
    out_dets = [detections[i] for i in range(len(detections)) if i in kept_set]
    out_ids = [track_ids[i] for i in range(len(detections)) if i in kept_set] if has_ids else []
    return out_dets, out_ids


class MultiPersonTracker:
    """
    Multi-person tracker with Persistent Spatial Canonical IDs and Track Lifecycle Management.

    Features:
    1. Canonical ID Stickiness: Ensures each student maintains the same Track ID (T1, T2, etc.)
       across occlusions, low-confidence frames, and ByteTrack re-initializations.
    2. Spatial & IoU De-duplication: Prevents duplicate ghost skeletons at the same seat.
    3. Seamless Coasting: Cleanly recovers coasting tracks when the student is seen again.
    """

    def __init__(
        self,
        coast_frames: int = DEFAULT_COAST_FRAMES,
        track_prefix: str = "T",
        iou_threshold: float = 0.25,
        spatial_match_dist_px: float = 160.0,
    ):
        self.coast_frames = coast_frames
        self.track_prefix = track_prefix
        self.iou_threshold = iou_threshold
        self.spatial_match_dist_px = spatial_match_dist_px

        # Active tracks: canonical_id → TrackedObject
        self._tracks: Dict[int, TrackedObject] = {}
        # Recently lost tracks: canonical_id → TrackedObject
        self._lost_tracks: Dict[int, TrackedObject] = {}
        # Mapping from YOLO/ByteTrack raw track ID to our Canonical Track ID
        self._yolo_to_canonical: Dict[int, int] = {}
        # Next unique canonical ID
        self._next_id = 1
        self._frame_idx = 0

    def update_from_ultralytics(
        self,
        detections: List[Detection],
        track_ids: List[int],
    ) -> List[TrackedObject]:
        """
        Update tracks using Ultralytics detections and IDs with spatial stabilization and Re-ID.
        """
        self._frame_idx += 1

        # 1. Suppress duplicate detections in the same frame
        clean_dets, clean_yolo_ids = _suppress_duplicate_detections(
            detections, track_ids, iou_thresh=0.40
        )

        seen_canonical_ids: Set[int] = set()
        unmatched_dets: List[Tuple[Detection, int]] = []

        # 2. First Pass: Resolve known YOLO IDs
        for det, yid in zip(clean_dets, clean_yolo_ids):
            canonical_id = None
            if yid >= 0 and yid in self._yolo_to_canonical:
                cid = self._yolo_to_canonical[yid]
                # Validate spatial consistency with existing track
                existing_track = self._tracks.get(cid) or self._lost_tracks.get(cid)
                if existing_track:
                    iou = existing_track.bbox.iou(det.bbox)
                    dist = math.hypot(
                        existing_track.bbox.center[0] - det.bbox.center[0],
                        existing_track.bbox.center[1] - det.bbox.center[1],
                    )
                    if iou >= 0.15 or dist <= self.spatial_match_dist_px:
                        canonical_id = cid

            if canonical_id is not None:
                seen_canonical_ids.add(canonical_id)
                track = self._tracks.get(canonical_id)
                if track:
                    track.bbox = det.bbox
                    track.frames_tracked += 1
                    track.frames_since_seen = 0
                    track.state = TrackingState.TRACKED
                else:
                    # Recover from lost
                    track = self._lost_tracks.pop(canonical_id, None)
                    if track:
                        track.bbox = det.bbox
                        track.frames_tracked += 1
                        track.frames_since_seen = 0
                        track.state = TrackingState.TRACKED
                        self._tracks[canonical_id] = track
                    else:
                        track = TrackedObject(
                            track_id=canonical_id,
                            bbox=det.bbox,
                            state=TrackingState.NEW,
                            frames_tracked=1,
                            frames_since_seen=0,
                        )
                        self._tracks[canonical_id] = track
            else:
                unmatched_dets.append((det, yid))

        # 3. Second Pass: Spatial & IoU Matching for Unmatched Detections
        available_tracks: List[TrackedObject] = []
        for cid, tr in list(self._tracks.items()):
            if cid not in seen_canonical_ids:
                available_tracks.append(tr)
        for cid, tr in list(self._lost_tracks.items()):
            if tr.frames_since_seen <= 150:  # Recent within 5-6 seconds
                available_tracks.append(tr)

        if unmatched_dets and available_tracks:
            cost_matrix = np.full((len(available_tracks), len(unmatched_dets)), 999.0)
            for i, tr in enumerate(available_tracks):
                for j, (det, _) in enumerate(unmatched_dets):
                    iou = tr.bbox.iou(det.bbox)
                    dist = math.hypot(
                        tr.bbox.center[0] - det.bbox.center[0],
                        tr.bbox.center[1] - det.bbox.center[1],
                    )
                    # Matching criteria for exam seats: high IoU or small centroid movement
                    if iou >= self.iou_threshold:
                        cost_matrix[i, j] = 1.0 - iou
                    elif dist <= self.spatial_match_dist_px:
                        cost_matrix[i, j] = 0.5 + (dist / (self.spatial_match_dist_px * 2.0))

            row_indices, col_indices = linear_sum_assignment(cost_matrix)
            matched_cols = set()

            for r, c in zip(row_indices, col_indices):
                if cost_matrix[r, c] < 1.0:
                    matched_tr = available_tracks[r]
                    det, yid = unmatched_dets[c]
                    cid = matched_tr.track_id

                    seen_canonical_ids.add(cid)
                    matched_cols.add(c)

                    if yid >= 0:
                        self._yolo_to_canonical[yid] = cid

                    # Re-attach track
                    matched_tr.bbox = det.bbox
                    matched_tr.frames_tracked += 1
                    matched_tr.frames_since_seen = 0
                    matched_tr.state = TrackingState.TRACKED

                    self._tracks[cid] = matched_tr
                    self._lost_tracks.pop(cid, None)

            # Keep only still-unmatched detections
            unmatched_dets = [
                (det, yid) for j, (det, yid) in enumerate(unmatched_dets) if j not in matched_cols
            ]

        # 4. Third Pass: Force Match or Create New Canonical Tracks for remaining unmatched detections
        for det, yid in unmatched_dets:
            # Check if there is ANY existing track within spatial proximity
            best_existing_cid = None
            best_dist = 999.0
            for cid, tr in list(self._tracks.items()):
                if cid not in seen_canonical_ids:
                    dist = math.hypot(tr.bbox.center[0] - det.bbox.center[0], tr.bbox.center[1] - det.bbox.center[1])
                    if dist <= self.spatial_match_dist_px and dist < best_dist:
                        best_dist = dist
                        best_existing_cid = cid

            if best_existing_cid is not None:
                # Force-match to existing spatial track rather than spawning duplicate
                cid = best_existing_cid
                matched_tr = self._tracks[cid]
                matched_tr.bbox = det.bbox
                matched_tr.frames_tracked += 1
                matched_tr.frames_since_seen = 0
                matched_tr.state = TrackingState.TRACKED
                seen_canonical_ids.add(cid)
                if yid >= 0:
                    self._yolo_to_canonical[yid] = cid
                continue

            if yid > 0 and yid not in self._tracks:
                cid = yid
                if cid >= self._next_id:
                    self._next_id = cid + 1
            else:
                cid = self._next_id
                self._next_id += 1

            if yid >= 0:
                self._yolo_to_canonical[yid] = cid

            track = TrackedObject(
                track_id=cid,
                bbox=det.bbox,
                state=TrackingState.NEW,
                frames_tracked=1,
                frames_since_seen=0,
            )
            self._tracks[cid] = track
            seen_canonical_ids.add(cid)

        # 5. Update Coasting & Lost States
        lost_ids = []
        for cid, track in self._tracks.items():
            if cid not in seen_canonical_ids:
                track.frames_since_seen += 1
                if track.frames_since_seen >= self.coast_frames:
                    track.state = TrackingState.LOST
                    lost_ids.append(cid)
                else:
                    track.state = TrackingState.COASTING

        for cid in lost_ids:
            self._lost_tracks[cid] = self._tracks.pop(cid)

        # 6. Strict Track De-Duplication: If two active tracks overlap heavily, keep older
        active_cids = list(self._tracks.keys())
        for i in range(len(active_cids)):
            cid1 = active_cids[i]
            if cid1 not in self._tracks:
                continue
            tr1 = self._tracks[cid1]
            for j in range(i + 1, len(active_cids)):
                cid2 = active_cids[j]
                if cid2 not in self._tracks:
                    continue
                tr2 = self._tracks[cid2]
                iou = tr1.bbox.iou(tr2.bbox)
                dist = math.hypot(tr1.bbox.center[0] - tr2.bbox.center[0], tr1.bbox.center[1] - tr2.bbox.center[1])
                if iou >= 0.35 or dist <= 100.0:
                    # Duplicate detected! Keep older track (lower cid or higher frames_tracked)
                    keep_cid = cid1 if (tr1.frames_tracked >= tr2.frames_tracked or cid1 < cid2) else cid2
                    drop_cid = cid2 if keep_cid == cid1 else cid1
                    self._lost_tracks[drop_cid] = self._tracks.pop(drop_cid)

        # Clean up very old lost tracks
        if len(self._lost_tracks) > 100:
            sorted_lost = sorted(
                self._lost_tracks.items(),
                key=lambda x: x[1].frames_since_seen,
            )
            self._lost_tracks = dict(sorted_lost[:100])

        return list(self._tracks.values())

    def update_standalone(
        self,
        detections: List[Detection],
    ) -> List[TrackedObject]:
        """
        Update tracks using IoU-based assignment (standalone mode).
        """
        fake_ids = [-1] * len(detections)
        return self.update_from_ultralytics(detections, fake_ids)

    def get_active_tracks(self) -> List[TrackedObject]:
        """Return currently active (non-LOST) tracks."""
        return list(self._tracks.values())

    def get_track(self, track_id: int) -> Optional[TrackedObject]:
        """Get a specific track by ID."""
        return self._tracks.get(track_id)

    @property
    def active_count(self) -> int:
        return len(self._tracks)

    @property
    def total_tracks_created(self) -> int:
        return self._next_id - 1

    def reset(self):
        """Reset all tracking state."""
        self._tracks.clear()
        self._lost_tracks.clear()
        self._yolo_to_canonical.clear()
        self._next_id = 1
        self._frame_idx = 0
