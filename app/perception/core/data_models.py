"""
CopyCop core data models — the output contract for Part 1.

Every struct here is part of the public API that Parts 2–4 consume.
All fields are documented. Schema version is tracked in ``copycop.version``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from app.perception.core.constants import (
    DirectionLabel,
    FrameStatus,
    StreamStatus,
    TrackingState,
    VisibilityLevel,
    TOTAL_KEYPOINTS,
)


# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Axis-aligned bounding box in pixel coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def iou(self, other: "BoundingBox") -> float:
        """Compute Intersection-over-Union with another box."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "x1": round(self.x1, 1),
            "y1": round(self.y1, 1),
            "x2": round(self.x2, 1),
            "y2": round(self.y2, 1),
            "confidence": round(self.confidence, 3),
        }

    def to_xyxy(self) -> list[float]:
        """Return [x1, y1, x2, y2]."""
        return [self.x1, self.y1, self.x2, self.y2]

    def to_xywh(self) -> list[float]:
        """Return [cx, cy, w, h]."""
        cx, cy = self.center
        return [cx, cy, self.width, self.height]

    def pad(self, ratio: float = 0.1) -> "BoundingBox":
        """Return a padded copy of this bbox."""
        pw = self.width * ratio
        ph = self.height * ratio
        return BoundingBox(
            x1=self.x1 - pw, y1=self.y1 - ph,
            x2=self.x2 + pw, y2=self.y2 + ph,
            confidence=self.confidence,
        )

    def clip(self, img_w: int, img_h: int) -> "BoundingBox":
        """Clip bbox to image boundaries."""
        return BoundingBox(
            x1=max(0, min(self.x1, img_w)),
            y1=max(0, min(self.y1, img_h)),
            x2=max(0, min(self.x2, img_w)),
            y2=max(0, min(self.y2, img_h)),
            confidence=self.confidence,
        )


@dataclass
class Detection:
    """A single person detection from the detector."""
    bbox: BoundingBox
    class_id: int = 0       # Always 0 (person) in our pipeline
    class_name: str = "person"


# ---------------------------------------------------------------------------
# Keypoints
# ---------------------------------------------------------------------------

@dataclass
class KeypointSet:
    """
    Whole-body keypoints following COCO-WholeBody 133-point layout.

    Attributes:
        xy: (133, 2) array of (x, y) pixel coordinates.
        confidence: (133,) array of per-keypoint confidence scores [0–1].
    """
    xy: np.ndarray             # shape: (133, 2)
    confidence: np.ndarray     # shape: (133,)

    @staticmethod
    def empty() -> "KeypointSet":
        """Create an empty keypoint set (all zeros)."""
        return KeypointSet(
            xy=np.zeros((TOTAL_KEYPOINTS, 2), dtype=np.float32),
            confidence=np.zeros(TOTAL_KEYPOINTS, dtype=np.float32),
        )

    def get_point(self, idx: int) -> tuple[float, float, float]:
        """Return (x, y, confidence) for a keypoint index."""
        return (float(self.xy[idx, 0]), float(self.xy[idx, 1]),
                float(self.confidence[idx]))

    def get_points(self, indices: list[int]) -> tuple[np.ndarray, np.ndarray]:
        """Return (xy_subset, conf_subset) for a list of indices."""
        return self.xy[indices], self.confidence[indices]

    def valid_mask(self, min_conf: float = 0.3) -> np.ndarray:
        """Boolean mask of keypoints above confidence threshold."""
        return self.confidence >= min_conf

    def region_confidence(self, indices: list[int]) -> float:
        """Average confidence of a group of keypoints."""
        if not indices:
            return 0.0
        return float(np.mean(self.confidence[indices]))

    def to_dict(self) -> Dict[str, Any]:
        """Compact serialization: only include keypoints with confidence > 0."""
        result = {}
        for i in range(len(self.confidence)):
            if self.confidence[i] > 0.01:
                result[str(i)] = {
                    "x": round(float(self.xy[i, 0]), 1),
                    "y": round(float(self.xy[i, 1]), 1),
                    "c": round(float(self.confidence[i]), 3),
                }
        return result

    @staticmethod
    def from_yolo_17(xy: np.ndarray, confidence: np.ndarray) -> "KeypointSet":
        """
        Create a KeypointSet from YOLO pose output (17 COCO body keypoints).

        Maps the 17 body keypoints into the 133-point layout (slots 0–16),
        leaving face/hand/foot slots at zero.

        Args:
            xy: (17, 2) array of (x, y) coordinates.
            confidence: (17,) array of per-keypoint confidence.

        Returns:
            KeypointSet with body keypoints populated.
        """
        full_xy = np.zeros((TOTAL_KEYPOINTS, 2), dtype=np.float32)
        full_conf = np.zeros(TOTAL_KEYPOINTS, dtype=np.float32)
        n = min(len(confidence), 17)
        full_xy[:n] = xy[:n]
        full_conf[:n] = confidence[:n]
        return KeypointSet(xy=full_xy, confidence=full_conf)


# ---------------------------------------------------------------------------
# Tracked objects
# ---------------------------------------------------------------------------

@dataclass
class TrackedObject:
    """A detection associated with a persistent track."""
    track_id: int
    bbox: BoundingBox
    state: TrackingState = TrackingState.TRACKED
    frames_tracked: int = 0
    frames_since_seen: int = 0

    @property
    def display_id(self) -> str:
        """Anonymous display ID like T17."""
        return f"T{self.track_id}"


# ---------------------------------------------------------------------------
# Analysis results
# ---------------------------------------------------------------------------

@dataclass
class HeadOrientation:
    """Estimated head orientation from SixDRepNet or facial landmarks."""
    yaw: float = 0.0               # Behaviour delta yaw (deviation from neutral baseline), negative=left, positive=right
    pitch: float = 0.0              # Behaviour delta pitch (deviation from neutral baseline), negative=down, positive=up
    roll: float = 0.0               # Roll angle in degrees
    confidence: float = 0.0         # [0–1] how reliable this estimate is
    direction: DirectionLabel = DirectionLabel.UNKNOWN
    is_smoothed: bool = True
    crop_valid: bool = True

    # Absolute 3D physical head orientation in camera space (for physical visualization)
    absolute_yaw: float = 0.0
    absolute_pitch: float = 0.0
    absolute_roll: float = 0.0
    rotation_matrix: Optional[List[List[float]]] = None
    arrow_vector: Optional[Tuple[float, float]] = None  # Normalized (dx, dy) 2D image vector

    @property
    def yaw_deg(self) -> float:
        return self.yaw

    @property
    def pitch_deg(self) -> float:
        return self.pitch

    @property
    def roll_deg(self) -> float:
        return self.roll

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "yaw": round(self.yaw, 1),
            "pitch": round(self.pitch, 1),
            "roll": round(self.roll, 1),
            "confidence": round(self.confidence, 3),
            "direction": self.direction.value,
            "absolute_yaw": round(self.absolute_yaw, 1),
            "absolute_pitch": round(self.absolute_pitch, 1),
            "absolute_roll": round(self.absolute_roll, 1),
        }
        if self.arrow_vector:
            d["arrow_vector"] = (round(self.arrow_vector[0], 3), round(self.arrow_vector[1], 3))
        return d


@dataclass
class VisibilityInfo:
    """Per-region and overall visibility/occlusion scores."""
    overall: float = 0.0           # [0–1] weighted average visibility
    head: float = 0.0
    left_shoulder: float = 0.0
    right_shoulder: float = 0.0
    left_arm: float = 0.0
    right_arm: float = 0.0
    left_hand: float = 0.0
    right_hand: float = 0.0

    # Occlusion flags
    is_occluded_by_person: bool = False
    is_at_frame_edge: bool = False

    # Camera-level visibility for this seat
    camera_visibility: VisibilityLevel = VisibilityLevel.GOOD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 3),
            "head": round(self.head, 3),
            "left_shoulder": round(self.left_shoulder, 3),
            "right_shoulder": round(self.right_shoulder, 3),
            "left_arm": round(self.left_arm, 3),
            "right_arm": round(self.right_arm, 3),
            "left_hand": round(self.left_hand, 3),
            "right_hand": round(self.right_hand, 3),
            "is_occluded_by_person": self.is_occluded_by_person,
            "is_at_frame_edge": self.is_at_frame_edge,
            "camera_visibility": self.camera_visibility.value,
        }


@dataclass
class BodyGeometry:
    """Shoulder-normalized body measurements for camera-distance independence."""
    shoulder_width_px: float = 0.0   # Pixel distance between shoulders
    torso_lean_angle: float = 0.0    # Degrees from vertical
    left_arm_extension: float = 0.0  # Normalized by shoulder width
    right_arm_extension: float = 0.0
    left_hand_position: tuple[float, float] = (0.0, 0.0)   # Relative to shoulder center
    right_hand_position: tuple[float, float] = (0.0, 0.0)
    shoulder_center: tuple[float, float] = (0.0, 0.0)      # Pixel coordinates

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shoulder_width_px": round(self.shoulder_width_px, 1),
            "torso_lean_angle": round(self.torso_lean_angle, 1),
            "left_arm_extension": round(self.left_arm_extension, 3),
            "right_arm_extension": round(self.right_arm_extension, 3),
            "left_hand_position": [round(v, 3) for v in self.left_hand_position],
            "right_hand_position": [round(v, 3) for v in self.right_hand_position],
            "shoulder_center": [round(v, 1) for v in self.shoulder_center],
        }


@dataclass
class DeskROI:
    """Estimated desk/interaction region for downstream object detection."""
    bbox: BoundingBox
    confidence: float = 0.0  # How reliable this estimate is

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.to_dict(),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class SeatInfo:
    """Seat/spatial association for a tracked student."""
    seat_id: str = "UNASSIGNED"       # e.g., "S1", "S2"
    position: tuple[float, float] = (0.0, 0.0)  # Seat centroid in frame
    assignment_confidence: float = 0.0
    is_vacant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seat_id": self.seat_id,
            "position": [round(v, 1) for v in self.position],
            "assignment_confidence": round(self.assignment_confidence, 3),
            "is_vacant": self.is_vacant,
        }


# ---------------------------------------------------------------------------
# Frame-level metadata
# ---------------------------------------------------------------------------

@dataclass
class FrameHealth:
    """Quality metrics for a captured frame."""
    brightness: float = 0.0        # Mean pixel value normalized [0–1]
    blur_score: float = 0.0        # Laplacian variance (higher = sharper)
    status: FrameStatus = FrameStatus.OK
    stream_status: StreamStatus = StreamStatus.CONNECTED
    dropped_frame_count: int = 0
    frame_width: int = 0
    frame_height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brightness": round(self.brightness, 3),
            "blur_score": round(self.blur_score, 1),
            "status": self.status.value,
            "stream_status": self.stream_status.value,
            "dropped_frame_count": self.dropped_frame_count,
            "resolution": f"{self.frame_width}x{self.frame_height}",
        }


# ---------------------------------------------------------------------------
# Top-level output: StudentState
# ---------------------------------------------------------------------------

@dataclass
class StudentState:
    """
    Complete perception state for a single tracked student.

    This is the primary output contract for Part 1.
    Parts 2–4 consume this to perform behavioural analysis.
    """
    # Identity (anonymous)
    track_id: str = ""                # e.g., "T17"
    seat_id: str = "UNASSIGNED"

    # Spatial
    bbox: Optional[BoundingBox] = None
    keypoints: Optional[KeypointSet] = None

    # Analysis
    head_orientation: Optional[HeadOrientation] = None
    visibility: Optional[VisibilityInfo] = None
    body_geometry: Optional[BodyGeometry] = None
    desk_roi: Optional[DeskROI] = None
    seat_info: Optional[SeatInfo] = None

    # Tracking
    tracking_state: TrackingState = TrackingState.NEW
    frames_tracked: int = 0
    frames_since_seen: int = 0

    # Timestamp
    timestamp: float = 0.0          # Unix timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "track_id": self.track_id,
            "seat_id": self.seat_id,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "keypoints": self.keypoints.to_dict() if self.keypoints else None,
            "head_orientation": self.head_orientation.to_dict() if self.head_orientation else None,
            "visibility": self.visibility.to_dict() if self.visibility else None,
            "body_geometry": self.body_geometry.to_dict() if self.body_geometry else None,
            "desk_roi": self.desk_roi.to_dict() if self.desk_roi else None,
            "seat_info": self.seat_info.to_dict() if self.seat_info else None,
            "tracking_state": self.tracking_state.value,
            "frames_tracked": self.frames_tracked,
            "frames_since_seen": self.frames_since_seen,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Frame-level output
# ---------------------------------------------------------------------------

@dataclass
class FrameMeta:
    """Metadata for a single processed frame."""
    timestamp: float = 0.0
    camera_id: str = "CAM_01"
    frame_number: int = 0
    pipeline_fps: float = 0.0
    pipeline_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "frame_number": self.frame_number,
            "pipeline_fps": round(self.pipeline_fps, 1),
            "pipeline_latency_ms": round(self.pipeline_latency_ms, 1),
        }


@dataclass
class PipelineOutput:
    """
    Complete output of one pipeline cycle (one frame).

    This is the top-level JSON object emitted per frame.
    """
    schema_version: str = "1.0.0"
    frame_meta: Optional[FrameMeta] = None
    frame_health: Optional[FrameHealth] = None
    students: List[StudentState] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "frame_meta": self.frame_meta.to_dict() if self.frame_meta else None,
            "frame_health": self.frame_health.to_dict() if self.frame_health else None,
            "students": [s.to_dict() for s in self.students],
        }
