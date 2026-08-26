"""
Part 1 → Part 2 Schema Adapter.

Converts Part 1 PipelineOutput (StudentState Schema 1.0.0) into
Part 2 FrameInput (TrackPose / Pydantic schema) so the
BehaviourRiskEngine can consume real perception data.

Key mappings:
  StudentState.keypoints (133-pt pixel)   → TrackPose.keypoints (17-pt COCO, normalized [0,1])
  StudentState.desk_roi                   → TrackPose.desk_zone
  StudentState.head_orientation           → TrackPose.additional_meta
  StudentState.body_geometry              → TrackPose.additional_meta
  StudentState.tracking_state (COASTING)  → reduced keypoint confidence
  StudentState (LOST)                     → excluded from FrameInput
"""
from __future__ import annotations

import time
from typing import List, Optional

from app.perception.core.data_models import PipelineOutput, StudentState
from app.perception.core.constants import TrackingState

from app.behaviour.schemas.pose import (
    FrameInput,
    TrackPose,
    Keypoint,
    BoundingBox,
    DeskZone,
    InvigilatorState,
)

# COCO-17 keypoint indices (in the 133-point layout)
_COCO17_INDICES = list(range(17))

# Confidence multiplier for COASTING (predicted) keypoints
_COASTING_CONF_SCALE = 0.4


def student_state_to_track_pose(
    student: StudentState,
    frame_w: int,
    frame_h: int,
    object_detections: Optional[List[dict]] = None,
    temporal_object_score: Optional[float] = None,
) -> Optional[TrackPose]:
    """
    Convert a single Part 1 StudentState into a Part 2 TrackPose.

    Returns None if the student is LOST or has no keypoints.

    Args:
        student: Part 1 StudentState instance.
        frame_w: Frame width in pixels (for normalization).
        frame_h: Frame height in pixels (for normalization).
        object_detections: Optional Part 3 object detections.
        temporal_object_score: Optional multi-frame accumulated object confidence.
    """
    # Exclude LOST tracks — they have no valid data
    if student.tracking_state == TrackingState.LOST:
        return None

    if student.keypoints is None:
        return None

    # Determine confidence scale (COASTING = predicted keypoints)
    is_coasting = student.tracking_state == TrackingState.COASTING
    conf_scale = _COASTING_CONF_SCALE if is_coasting else 1.0

    fw = max(frame_w, 1)
    fh = max(frame_h, 1)

    # Extract COCO-17 body keypoints (indices 0-16) and normalize to [0,1]
    keypoints: List[Keypoint] = []
    for idx in _COCO17_INDICES:
        x_px = float(student.keypoints.xy[idx, 0])
        y_px = float(student.keypoints.xy[idx, 1])
        conf = float(student.keypoints.confidence[idx]) * conf_scale
        keypoints.append(Keypoint(
            x=x_px / fw,
            y=y_px / fh,
            confidence=max(0.0, min(conf, 1.0)),
        ))

    # Bounding box (normalized)
    bbox: Optional[BoundingBox] = None
    if student.bbox is not None:
        bbox = BoundingBox(
            x_min=student.bbox.x1 / fw,
            y_min=student.bbox.y1 / fh,
            x_max=student.bbox.x2 / fw,
            y_max=student.bbox.y2 / fh,
            confidence=student.bbox.confidence,
        )

    # Desk zone from Part 1 DeskROI
    desk_zone: Optional[DeskZone] = None
    if student.desk_roi is not None and student.desk_roi.confidence > 0.1:
        droi = student.desk_roi.bbox
        desk_zone = DeskZone(
            seat_id=student.seat_id,
            x_min=droi.x1 / fw,
            y_min=droi.y1 / fh,
            x_max=droi.x2 / fw,
            y_max=droi.y2 / fh,
        )

    # Pack additional meta for Part 2 detectors that can use enriched data
    additional_meta: dict = {
        "is_coasting": is_coasting,
        "frames_tracked": student.frames_tracked,
        "frames_since_seen": student.frames_since_seen,
        "tracking_state": student.tracking_state.value,
    }

    if student.head_orientation is not None:
        abs_yaw = getattr(student.head_orientation, "absolute_yaw", student.head_orientation.yaw)
        abs_pitch = getattr(student.head_orientation, "absolute_pitch", student.head_orientation.pitch)
        abs_roll = getattr(student.head_orientation, "absolute_roll", student.head_orientation.roll)
        additional_meta["head_yaw"] = student.head_orientation.yaw
        additional_meta["head_pitch"] = student.head_orientation.pitch
        additional_meta["head_roll"] = student.head_orientation.roll
        additional_meta["head_abs_yaw"] = abs_yaw
        additional_meta["head_abs_pitch"] = abs_pitch
        additional_meta["head_abs_roll"] = abs_roll
        additional_meta["head_direction"] = student.head_orientation.direction.value
        additional_meta["head_conf"] = student.head_orientation.confidence
        additional_meta["head_crop_valid"] = student.head_orientation.crop_valid

    if student.body_geometry is not None:
        additional_meta["torso_lean_angle"] = student.body_geometry.torso_lean_angle
        additional_meta["shoulder_width_px"] = student.body_geometry.shoulder_width_px
        additional_meta["left_arm_ext"] = student.body_geometry.left_arm_extension
        additional_meta["right_arm_ext"] = student.body_geometry.right_arm_extension
        additional_meta["left_hand_pos"] = list(student.body_geometry.left_hand_position)
        additional_meta["right_hand_pos"] = list(student.body_geometry.right_hand_position)

    if student.visibility is not None:
        additional_meta["visibility_overall"] = student.visibility.overall
        additional_meta["visibility_head"] = student.visibility.head
        additional_meta["visibility_left_hand"] = student.visibility.left_hand
        additional_meta["visibility_right_hand"] = student.visibility.right_hand
        additional_meta["is_occluded"] = student.visibility.is_occluded_by_person

    return TrackPose(
        track_id=student.track_id,
        seat_id=student.seat_id,
        keypoints=keypoints,
        bbox=bbox,
        desk_zone=desk_zone,
        object_detections=object_detections,
        temporal_object_score=temporal_object_score,
        additional_meta=additional_meta,
    )


def pipeline_output_to_frame_input(
    output: PipelineOutput,
    frame_number: int,
    room_id: str = "EXAM_HALL_A",
    exam_phase: str = "IN_PROGRESS",
    object_detections_by_track: Optional[dict] = None,
    temporal_scores_by_track: Optional[dict] = None,
) -> FrameInput:
    """
    Convert a complete Part 1 PipelineOutput into a Part 2 FrameInput.

    Args:
        output: Part 1 PipelineOutput (Schema 1.0.0).
        frame_number: Sequential frame index for Part 2 frame_id.
        room_id: Exam room identifier.
        exam_phase: Current exam phase string.
        object_detections_by_track: Dict mapping track_id to list of object detections.
        temporal_scores_by_track: Dict mapping track_id to smoothed object confidence.
    """
    # Frame dimensions from health metadata
    frame_w = 1280
    frame_h = 720
    if output.frame_health:
        frame_w = max(output.frame_health.frame_width, 1) or 1280
        frame_h = max(output.frame_health.frame_height, 1) or 720

    # Timestamp in milliseconds
    timestamp_ms = 0.0
    if output.frame_meta:
        timestamp_ms = output.frame_meta.timestamp * 1000.0

    # Convert each StudentState
    tracks: List[TrackPose] = []
    for student in output.students:
        obj_dets = (object_detections_by_track or {}).get(student.track_id)
        temp_score = (temporal_scores_by_track or {}).get(student.track_id)
        tp = student_state_to_track_pose(
            student,
            frame_w,
            frame_h,
            object_detections=obj_dets,
            temporal_object_score=temp_score,
        )
        if tp is not None:
            tracks.append(tp)

    return FrameInput(
        frame_id=frame_number,
        timestamp_ms=timestamp_ms,
        room_id=room_id,
        tracks=tracks,
        invigilators=None,
        exam_phase=exam_phase,
    )
