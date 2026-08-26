"""
Unit tests for CopyCop core data models.

Tests serialization, geometry, and construction of all data model classes.
"""

import json
import math
import time

import numpy as np
import pytest

from app.perception.core.constants import (
    TOTAL_KEYPOINTS,
    DirectionLabel,
    FrameStatus,
    StreamStatus,
    TrackingState,
    VisibilityLevel,
)
from app.perception.core.data_models import (
    BodyGeometry,
    BoundingBox,
    DeskROI,
    Detection,
    FrameHealth,
    FrameMeta,
    HeadOrientation,
    KeypointSet,
    PipelineOutput,
    SeatInfo,
    StudentState,
    TrackedObject,
    VisibilityInfo,
)


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------

class TestBoundingBox:
    def test_basic_properties(self):
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=120)
        assert bbox.width == 100
        assert bbox.height == 100
        assert bbox.center == (60, 70)
        assert bbox.area == 10000

    def test_iou_identical(self):
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        assert bbox.iou(bbox) == pytest.approx(1.0)

    def test_iou_no_overlap(self):
        a = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        b = BoundingBox(x1=60, y1=60, x2=100, y2=100)
        assert a.iou(b) == 0.0

    def test_iou_partial(self):
        a = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        b = BoundingBox(x1=50, y1=50, x2=150, y2=150)
        # Intersection: 50x50 = 2500, Union: 10000+10000-2500 = 17500
        assert a.iou(b) == pytest.approx(2500 / 17500, abs=0.01)

    def test_to_dict(self):
        bbox = BoundingBox(x1=10.123, y1=20.456, x2=110.789, y2=120.012, confidence=0.95123)
        d = bbox.to_dict()
        assert "x1" in d
        assert "confidence" in d
        assert d["confidence"] == 0.951

    def test_pad(self):
        bbox = BoundingBox(x1=100, y1=100, x2=200, y2=200)
        padded = bbox.pad(0.1)
        assert padded.x1 < 100
        assert padded.y1 < 100
        assert padded.x2 > 200
        assert padded.y2 > 200

    def test_clip(self):
        bbox = BoundingBox(x1=-10, y1=-20, x2=1300, y2=800)
        clipped = bbox.clip(1280, 720)
        assert clipped.x1 == 0
        assert clipped.y1 == 0
        assert clipped.x2 == 1280
        assert clipped.y2 == 720

    def test_to_xyxy(self):
        bbox = BoundingBox(x1=10, y1=20, x2=30, y2=40)
        assert bbox.to_xyxy() == [10, 20, 30, 40]

    def test_to_xywh(self):
        bbox = BoundingBox(x1=10, y1=20, x2=30, y2=40)
        xywh = bbox.to_xywh()
        assert xywh[0] == 20  # cx
        assert xywh[1] == 30  # cy
        assert xywh[2] == 20  # w
        assert xywh[3] == 20  # h


# ---------------------------------------------------------------------------
# KeypointSet
# ---------------------------------------------------------------------------

class TestKeypointSet:
    def test_empty(self):
        kps = KeypointSet.empty()
        assert kps.xy.shape == (TOTAL_KEYPOINTS, 2)
        assert kps.confidence.shape == (TOTAL_KEYPOINTS,)
        assert np.all(kps.confidence == 0)

    def test_get_point(self):
        kps = KeypointSet.empty()
        kps.xy[0] = [100.5, 200.3]
        kps.confidence[0] = 0.95
        x, y, c = kps.get_point(0)
        assert x == pytest.approx(100.5)
        assert y == pytest.approx(200.3)
        assert c == pytest.approx(0.95)

    def test_valid_mask(self):
        kps = KeypointSet.empty()
        kps.confidence[0] = 0.5
        kps.confidence[1] = 0.2
        kps.confidence[2] = 0.8
        mask = kps.valid_mask(0.3)
        assert mask[0] == True
        assert mask[1] == False
        assert mask[2] == True

    def test_region_confidence(self):
        kps = KeypointSet.empty()
        kps.confidence[0] = 0.9
        kps.confidence[1] = 0.8
        kps.confidence[2] = 0.7
        avg = kps.region_confidence([0, 1, 2])
        assert avg == pytest.approx(0.8)

    def test_to_dict_sparse(self):
        kps = KeypointSet.empty()
        kps.xy[5] = [300, 400]
        kps.confidence[5] = 0.9
        d = kps.to_dict()
        assert "5" in d
        assert "0" not in d  # Zero confidence, excluded


# ---------------------------------------------------------------------------
# HeadOrientation
# ---------------------------------------------------------------------------

class TestHeadOrientation:
    def test_default_unknown(self):
        ho = HeadOrientation()
        assert ho.direction == DirectionLabel.UNKNOWN

    def test_to_dict(self):
        ho = HeadOrientation(yaw=-15.2, pitch=10.1, confidence=0.85,
                             direction=DirectionLabel.FORWARD)
        d = ho.to_dict()
        assert d["direction"] == "FORWARD"
        assert d["yaw"] == -15.2
        assert d["confidence"] == 0.85


# ---------------------------------------------------------------------------
# VisibilityInfo
# ---------------------------------------------------------------------------

class TestVisibilityInfo:
    def test_defaults(self):
        vi = VisibilityInfo()
        assert vi.overall == 0.0
        assert vi.is_occluded_by_person == False

    def test_to_dict(self):
        vi = VisibilityInfo(
            overall=0.82, head=0.95, left_hand=0.7, right_hand=0.65,
            camera_visibility=VisibilityLevel.GOOD,
        )
        d = vi.to_dict()
        assert d["camera_visibility"] == "GOOD"


# ---------------------------------------------------------------------------
# TrackedObject
# ---------------------------------------------------------------------------

class TestTrackedObject:
    def test_display_id(self):
        to = TrackedObject(track_id=17, bbox=BoundingBox(0, 0, 100, 100))
        assert to.display_id == "T17"


# ---------------------------------------------------------------------------
# StudentState
# ---------------------------------------------------------------------------

class TestStudentState:
    def test_full_serialization(self):
        kps = KeypointSet.empty()
        kps.xy[0] = [100, 200]
        kps.confidence[0] = 0.9

        student = StudentState(
            track_id="T5",
            seat_id="S2",
            bbox=BoundingBox(50, 50, 200, 300, confidence=0.9),
            keypoints=kps,
            head_orientation=HeadOrientation(
                yaw=-10, pitch=5, confidence=0.8,
                direction=DirectionLabel.FORWARD,
            ),
            visibility=VisibilityInfo(overall=0.85, head=0.95),
            body_geometry=BodyGeometry(
                shoulder_width_px=120, torso_lean_angle=3.2,
            ),
            desk_roi=DeskROI(
                bbox=BoundingBox(40, 200, 210, 350),
                confidence=0.75,
            ),
            seat_info=SeatInfo(seat_id="S2", position=(150, 200)),
            tracking_state=TrackingState.TRACKED,
            frames_tracked=150,
            timestamp=time.time(),
        )

        d = student.to_dict()
        assert d["track_id"] == "T5"
        assert d["seat_id"] == "S2"
        assert d["tracking_state"] == "TRACKED"
        assert d["bbox"] is not None
        assert d["keypoints"] is not None
        assert d["head_orientation"]["direction"] == "FORWARD"

        # Verify JSON serializability
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["track_id"] == "T5"


# ---------------------------------------------------------------------------
# PipelineOutput
# ---------------------------------------------------------------------------

class TestPipelineOutput:
    def test_empty_output(self):
        output = PipelineOutput(
            schema_version="1.0.0",
            frame_meta=FrameMeta(camera_id="CAM_01", frame_number=1),
            frame_health=FrameHealth(brightness=0.5, blur_score=100),
        )
        d = output.to_dict()
        assert d["schema_version"] == "1.0.0"
        assert d["students"] == []

        # JSON serializable
        json_str = json.dumps(d, default=str)
        assert "1.0.0" in json_str

    def test_with_students(self):
        output = PipelineOutput(
            schema_version="1.0.0",
            frame_meta=FrameMeta(camera_id="CAM_01", frame_number=42),
            students=[
                StudentState(track_id="T1", tracking_state=TrackingState.TRACKED),
                StudentState(track_id="T2", tracking_state=TrackingState.COASTING),
            ],
        )
        d = output.to_dict()
        assert len(d["students"]) == 2
        assert d["students"][0]["track_id"] == "T1"
        assert d["students"][1]["tracking_state"] == "COASTING"


# ---------------------------------------------------------------------------
# FrameHealth
# ---------------------------------------------------------------------------

class TestFrameHealth:
    def test_degraded(self):
        fh = FrameHealth(
            brightness=0.1, blur_score=10,
            status=FrameStatus.DEGRADED,
            stream_status=StreamStatus.CONNECTED,
        )
        d = fh.to_dict()
        assert d["status"] == "DEGRADED"
        assert d["stream_status"] == "CONNECTED"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class TestDetection:
    def test_default_person(self):
        det = Detection(bbox=BoundingBox(0, 0, 100, 200))
        assert det.class_id == 0
        assert det.class_name == "person"
