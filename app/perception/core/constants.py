"""
Constants, enums, and keypoint index maps for CopyCop perception pipeline.

COCO-WholeBody 133-keypoint layout (used by RTMW):
  Body:       0–16   (17 keypoints)
  Feet:       17–22  (6 keypoints)
  Face:       23–90  (68 keypoints)
  Left Hand:  91–111 (21 keypoints)
  Right Hand: 112–132 (21 keypoints)
"""

from enum import Enum, auto


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrackingState(str, Enum):
    """State of a tracked person across frames."""
    NEW = "NEW"                # First appearance
    TRACKED = "TRACKED"        # Actively detected and tracked
    COASTING = "COASTING"      # Temporarily lost, predicted by Kalman filter
    LOST = "LOST"              # Lost beyond coast timeout


class DirectionLabel(str, Enum):
    """Discrete head orientation labels."""
    FORWARD = "FORWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    DOWN = "DOWN"
    UP = "UP"
    UNKNOWN = "UNKNOWN"


class VisibilityLevel(str, Enum):
    """Camera visibility quality for a seat/region."""
    GOOD = "GOOD"              # Clear, unobstructed view
    PARTIAL = "PARTIAL"        # Some occlusion or angle issues
    POOR = "POOR"              # Significant occlusion or blind spot


class FrameStatus(str, Enum):
    """Status of a captured frame."""
    OK = "OK"
    DEGRADED = "DEGRADED"      # Low brightness, high blur, etc.
    DROPPED = "DROPPED"        # Frame was not captured


class StreamStatus(str, Enum):
    """Status of the video stream/camera connection."""
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DISCONNECTED = "DISCONNECTED"


class BodyPart(str, Enum):
    """Body region identifiers for visibility scoring."""
    HEAD = "HEAD"
    LEFT_SHOULDER = "LEFT_SHOULDER"
    RIGHT_SHOULDER = "RIGHT_SHOULDER"
    LEFT_ARM = "LEFT_ARM"
    RIGHT_ARM = "RIGHT_ARM"
    LEFT_HAND = "LEFT_HAND"
    RIGHT_HAND = "RIGHT_HAND"
    TORSO = "TORSO"


# ---------------------------------------------------------------------------
# COCO-WholeBody 133 Keypoint Indices
# ---------------------------------------------------------------------------

# Body keypoints (indices 0–16)
KP_NOSE = 0
KP_LEFT_EYE = 1
KP_RIGHT_EYE = 2
KP_LEFT_EAR = 3
KP_RIGHT_EAR = 4
KP_LEFT_SHOULDER = 5
KP_RIGHT_SHOULDER = 6
KP_LEFT_ELBOW = 7
KP_RIGHT_ELBOW = 8
KP_LEFT_WRIST = 9
KP_RIGHT_WRIST = 10
KP_LEFT_HIP = 11
KP_RIGHT_HIP = 12
KP_LEFT_KNEE = 13
KP_RIGHT_KNEE = 14
KP_LEFT_ANKLE = 15
KP_RIGHT_ANKLE = 16

# Feet keypoints (indices 17–22)
KP_FEET_START = 17
KP_FEET_END = 22

# Face keypoints (indices 23–90)
KP_FACE_START = 23
KP_FACE_END = 90

# Left hand keypoints (indices 91–111)
KP_LEFT_HAND_START = 91
KP_LEFT_HAND_END = 111
KP_LEFT_HAND_WRIST = 91  # Hand-local wrist

# Right hand keypoints (indices 112–132)
KP_RIGHT_HAND_START = 112
KP_RIGHT_HAND_END = 132
KP_RIGHT_HAND_WRIST = 112  # Hand-local wrist

# Total keypoints
TOTAL_KEYPOINTS = 133


# ---------------------------------------------------------------------------
# Body region groupings (indices into the 133-keypoint array)
# ---------------------------------------------------------------------------

# Upper body — the critical keypoints for seated exam monitoring
UPPER_BODY_INDICES = [
    KP_NOSE, KP_LEFT_EYE, KP_RIGHT_EYE, KP_LEFT_EAR, KP_RIGHT_EAR,
    KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER,
    KP_LEFT_ELBOW, KP_RIGHT_ELBOW,
    KP_LEFT_WRIST, KP_RIGHT_WRIST,
]

# Head landmarks for orientation estimation
HEAD_INDICES = [KP_NOSE, KP_LEFT_EYE, KP_RIGHT_EYE, KP_LEFT_EAR, KP_RIGHT_EAR]

# Shoulder pair for normalization reference
SHOULDER_INDICES = [KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER]

# Arm keypoints
LEFT_ARM_INDICES = [KP_LEFT_SHOULDER, KP_LEFT_ELBOW, KP_LEFT_WRIST]
RIGHT_ARM_INDICES = [KP_RIGHT_SHOULDER, KP_RIGHT_ELBOW, KP_RIGHT_WRIST]

# Hand keypoint ranges
LEFT_HAND_INDICES = list(range(KP_LEFT_HAND_START, KP_LEFT_HAND_END + 1))
RIGHT_HAND_INDICES = list(range(KP_RIGHT_HAND_START, KP_RIGHT_HAND_END + 1))

# Face keypoint range
FACE_INDICES = list(range(KP_FACE_START, KP_FACE_END + 1))


# ---------------------------------------------------------------------------
# Skeleton connections for visualization (upper body focus)
# ---------------------------------------------------------------------------

UPPER_BODY_SKELETON = [
    # Head
    (KP_LEFT_EAR, KP_LEFT_EYE),
    (KP_LEFT_EYE, KP_NOSE),
    (KP_NOSE, KP_RIGHT_EYE),
    (KP_RIGHT_EYE, KP_RIGHT_EAR),
    # Shoulders
    (KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER),
    # Left arm
    (KP_LEFT_SHOULDER, KP_LEFT_ELBOW),
    (KP_LEFT_ELBOW, KP_LEFT_WRIST),
    # Right arm
    (KP_RIGHT_SHOULDER, KP_RIGHT_ELBOW),
    (KP_RIGHT_ELBOW, KP_RIGHT_WRIST),
    # Neck (shoulder midpoint to nose)
    (KP_NOSE, KP_LEFT_SHOULDER),
    (KP_NOSE, KP_RIGHT_SHOULDER),
]

# Full body skeleton (including lower body when visible)
FULL_BODY_SKELETON = UPPER_BODY_SKELETON + [
    (KP_LEFT_SHOULDER, KP_LEFT_HIP),
    (KP_RIGHT_SHOULDER, KP_RIGHT_HIP),
    (KP_LEFT_HIP, KP_RIGHT_HIP),
    (KP_LEFT_HIP, KP_LEFT_KNEE),
    (KP_LEFT_KNEE, KP_LEFT_ANKLE),
    (KP_RIGHT_HIP, KP_RIGHT_KNEE),
    (KP_RIGHT_KNEE, KP_RIGHT_ANKLE),
]

# Hand skeleton connections (within each 21-point hand)
# Standard hand keypoint order: wrist, then 4 fingers × 4 joints + thumb × 4
HAND_SKELETON_LOCAL = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
    (0, 13), (13, 14), (14, 15), (15, 16),# Ring
    (0, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (5, 9), (9, 13), (13, 17),            # Palm connections
]


# ---------------------------------------------------------------------------
# Visualization colors (BGR for OpenCV)
# ---------------------------------------------------------------------------

COLOR_BBOX = (0, 255, 128)          # Green
COLOR_BBOX_COASTING = (0, 180, 255) # Orange
COLOR_BBOX_NEW = (255, 200, 0)      # Cyan-ish
COLOR_SKELETON = (255, 255, 0)      # Cyan
COLOR_HAND_LEFT = (255, 128, 0)     # Blue-ish
COLOR_HAND_RIGHT = (0, 128, 255)    # Orange-ish
COLOR_HEAD_ARROW = (0, 0, 255)      # Red
COLOR_SEAT = (200, 200, 0)          # Teal
COLOR_DESK_ROI = (128, 0, 255)      # Purple
COLOR_TEXT_BG = (0, 0, 0)           # Black
COLOR_TEXT_FG = (255, 255, 255)     # White

COLOR_VIS_GOOD = (0, 255, 0)       # Green
COLOR_VIS_PARTIAL = (0, 200, 255)  # Yellow
COLOR_VIS_POOR = (0, 0, 255)       # Red


# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

DEFAULT_DETECTION_CONF = 0.5
DEFAULT_KEYPOINT_CONF = 0.3
DEFAULT_HEAD_LANDMARK_CONF = 0.3
DEFAULT_COAST_FRAMES = 30
DEFAULT_SEAT_STABILITY_FRAMES = 60
DEFAULT_SEAT_MERGE_DISTANCE = 50  # pixels

# ---------------------------------------------------------------------------
# YOLO Pose model outputs 17 COCO body keypoints (same indices 0–16 as above).
# When using YOLO pose, we only get the first 17 keypoints.
# Hand/face keypoints (indices 17+) are only available from RTMW.
# ---------------------------------------------------------------------------
YOLO_BODY_KEYPOINTS = 17

