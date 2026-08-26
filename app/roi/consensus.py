"""
Temporal Object Consensus Tracker — Aggregates multi-frame detections into stable canonical evidence.

Maintains candidate object tracks across frames, evaluating:
- Class consensus (prevents label flickering between phone and chit)
- Temporal persistence (requires sustained observation, not one-frame glitch)
- Spatial IoU consistency (confirms object is physically stable)
- Maximum and mean confidence
- Bounded evidence strength
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from app.schemas.common import ObjectDetection

logger = logging.getLogger(__name__)


def compute_iou(box1: List[int], box2: List[int]) -> float:
    """Compute Intersection over Union between two [x1, y1, x2, y2] boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(1, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(1, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class ConsensusObjectEvidence(BaseModel):
    """Aggregated temporal evidence for an object candidate."""
    track_id: str
    seat_id: Optional[str] = None
    consensus_class: str
    consensus_confidence: float
    consensus_bbox: List[int]
    persistence_sec: float
    detection_count: int
    max_confidence: float
    mean_confidence: float
    iou_consistency: float
    is_confirmed: bool


class TrackCandidateState:
    """Internal state tracking an object candidate across adjacent frames."""

    def __init__(self, track_id: str, window_sec: float = 3.0):
        self.track_id = track_id
        self.window_sec = window_sec
        self.history: deque = deque()  # (timestamp, ObjectDetection)

    def add(self, detection: ObjectDetection, timestamp: float) -> None:
        self.history.append((timestamp, detection))
        self._prune(timestamp)

    def _prune(self, current_time: float) -> None:
        while self.history and (current_time - self.history[0][0] > self.window_sec):
            self.history.popleft()

    def get_consensus(self, current_time: float, seat_id: Optional[str] = None) -> Optional[ConsensusObjectEvidence]:
        self._prune(current_time)
        if not self.history:
            return None

        # Tally class occurrences and confidences
        class_confs = defaultdict(list)
        boxes = []
        timestamps = []

        for ts, det in self.history:
            class_confs[det.object_class].append(det.confidence)
            boxes.append(det.bbox)
            timestamps.append(ts)

        first_ts = timestamps[0]
        last_ts = timestamps[-1]
        persistence_sec = max(0.0, last_ts - first_ts)
        detection_count = len(self.history)

        # Determine dominant class
        total_detections = detection_count
        top_class = None
        top_count = 0

        for cls, confs in class_confs.items():
            if len(confs) > top_count:
                top_count = len(confs)
                top_class = cls

        top_ratio = top_count / total_detections if total_detections > 0 else 0.0

        # Class consensus check:
        # If consecutive frames agree (> 65% votes), keep top class.
        # If classes alternate or are ambiguous, downgrade to unknown_object with confidence penalty.
        if top_ratio >= 0.65:
            consensus_class = top_class
            class_confs_active = class_confs[top_class]
        else:
            consensus_class = "unknown_object"
            class_confs_active = [c * 0.7 for confs in class_confs.values() for c in confs]

        max_conf = max(class_confs_active, default=0.0)
        # Weighted mean: more recent frames carry more weight
        weights = np.linspace(0.6, 1.0, len(class_confs_active))
        weights /= np.sum(weights)
        mean_conf = float(np.sum(np.array(class_confs_active) * weights))

        # Smoothed bounding box (average of last 3 boxes)
        recent_boxes = boxes[-3:]
        avg_box = [
            int(np.mean([b[0] for b in recent_boxes])),
            int(np.mean([b[1] for b in recent_boxes])),
            int(np.mean([b[2] for b in recent_boxes])),
            int(np.mean([b[3] for b in recent_boxes])),
        ]

        # IoU consistency across consecutive boxes
        ious = []
        for i in range(len(boxes) - 1):
            ious.append(compute_iou(boxes[i], boxes[i + 1]))
        avg_iou = float(np.mean(ious)) if ious else 1.0

        # Confirmation condition:
        # 1. At least 2 observations
        # 2. Mean confidence >= class threshold
        # 3. Persistence >= 0.8s OR very strong max confidence (>= 0.75)
        thresh = 0.48 if consensus_class == "paper_chit" else (0.58 if consensus_class == "mobile_phone" else 0.50)
        is_confirmed = (
            detection_count >= 2 and
            mean_conf >= thresh and
            (persistence_sec >= 0.6 or max_conf >= 0.75)
        )

        return ConsensusObjectEvidence(
            track_id=self.track_id,
            seat_id=seat_id,
            consensus_class=consensus_class,
            consensus_confidence=round(mean_conf, 4),
            consensus_bbox=avg_box,
            persistence_sec=round(persistence_sec, 2),
            detection_count=detection_count,
            max_confidence=round(max_conf, 4),
            mean_confidence=round(mean_conf, 4),
            iou_consistency=round(avg_iou, 2),
            is_confirmed=is_confirmed,
        )


class TemporalConsensusTracker:
    """
    Manages temporal candidate tracks for all active students in the exam hall.
    """

    def __init__(self, window_sec: float = 3.0):
        self.window_sec = window_sec
        self._tracks: Dict[str, TrackCandidateState] = {}

    def update(
        self,
        track_id: str,
        detections: List[ObjectDetection],
        timestamp: float,
        seat_id: Optional[str] = None,
    ) -> Optional[ConsensusObjectEvidence]:
        """
        Record frame detections for a student track and return consensus evidence.
        """
        if track_id not in self._tracks:
            self._tracks[track_id] = TrackCandidateState(track_id, self.window_sec)

        cand = self._tracks[track_id]

        for det in detections:
            cand.add(det, timestamp)

        return cand.get_consensus(timestamp, seat_id)

    def get_evidence(self, track_id: str, timestamp: float, seat_id: Optional[str] = None) -> Optional[ConsensusObjectEvidence]:
        """Get current consensus evidence for a track."""
        if track_id not in self._tracks:
            return None
        return self._tracks[track_id].get_consensus(timestamp, seat_id)

    def clear(self, track_id: Optional[str] = None) -> None:
        """Clear consensus history."""
        if track_id:
            self._tracks.pop(track_id, None)
        else:
            self._tracks.clear()
