"""
Head Orientation and Gaze Direction Estimation.

Integrates:
1. SixDRepNet (RepVGG-A0 backbone): High-accuracy continuous 3D Euler angle estimation (Yaw, Pitch, Roll)
   on facial crops extracted from YOLO-Pose keypoints.
2. Exponential Moving Average (EMA) temporal smoothing to eliminate frame-to-frame angular jitter.
3. Dual-threshold hysteresis state machine for robust discrete direction classification:
   - FORWARD: Focused straight ahead on screen / exam.
   - LEFT / RIGHT: Turning head sideways / toward neighbor / away from workstation.
   - DOWN: Looking down at writing surface / desk paper.
   - UP: Head tilted upward / scanning ceiling or room.
4. Fallback Heuristic Estimator: Geometry-based keypoint vector estimation when SixDRepNet is disabled
   or facial crop is invalid/occluded.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.models.sixdrepnet import SixDRepNetEstimator
from app.perception.core.constants import (
    DEFAULT_KEYPOINT_CONF,
    DirectionLabel,
    KP_LEFT_EAR,
    KP_LEFT_EYE,
    KP_LEFT_SHOULDER,
    KP_NOSE,
    KP_RIGHT_EAR,
    KP_RIGHT_EYE,
    KP_RIGHT_SHOULDER,
)
from app.perception.core.data_models import (
    BoundingBox,
    HeadOrientation,
    KeypointSet,
    TrackedObject,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Internal State for SixDRepNet Pipeline
# ===========================================================================

class _TrackHeadPoseState:
    """Internal per-track temporal state for EMA smoothing, neutral baseline calibration, and hysteresis."""

    def __init__(self, track_id: int):
        self.track_id = track_id
        self.smoothed_yaw: float = 0.0
        self.smoothed_pitch: float = 0.0
        self.smoothed_roll: float = 0.0
        self.raw_yaw: float = 0.0
        self.raw_pitch: float = 0.0
        self.raw_roll: float = 0.0
        self.smoothed_rot_matrix: Optional[np.ndarray] = None
        self.arrow_vector: Optional[Tuple[float, float]] = None
        self.neutral_yaw: Optional[float] = None
        self.neutral_pitch: Optional[float] = None
        self.delta_yaw: float = 0.0
        self.delta_pitch: float = 0.0
        self.confidence: float = 0.0
        self.current_direction: DirectionLabel = DirectionLabel.UNKNOWN
        self.frames_since_inference: int = 0
        self.last_frame_num: int = 0
        self.last_nose_pos: Optional[Tuple[float, float]] = None


# ===========================================================================
# Heuristic Fallback Estimator
# ===========================================================================

class HeadOrientationEstimator:
    """
    Fallback 2D geometry-based head orientation estimator.
    Used when SixDRepNet is disabled or when facial crops fail validation.
    """

    def __init__(
        self,
        yaw_threshold_deg: float = 16.0,
        pitch_down_threshold_deg: float = -18.0,
        pitch_up_threshold_deg: float = 14.0,
        min_keypoint_conf: float = 0.20,
        min_landmark_confidence: Optional[float] = None,
    ):
        self.yaw_thresh = yaw_threshold_deg
        self.pitch_down_thresh = pitch_down_threshold_deg
        self.pitch_up_thresh = pitch_up_threshold_deg
        self.min_conf = min_landmark_confidence if min_landmark_confidence is not None else min_keypoint_conf

    def estimate(self, keypoints: KeypointSet) -> HeadOrientation:
        """Estimate 3D Euler angles and discrete direction from 2D keypoints using robust multi-cue geometry."""
        nose = keypoints.get_point(KP_NOSE)
        l_eye = keypoints.get_point(KP_LEFT_EYE)
        r_eye = keypoints.get_point(KP_RIGHT_EYE)
        l_ear = keypoints.get_point(KP_LEFT_EAR)
        r_ear = keypoints.get_point(KP_RIGHT_EAR)
        l_sh = keypoints.get_point(KP_LEFT_SHOULDER)
        r_sh = keypoints.get_point(KP_RIGHT_SHOULDER)

        valid_facial = [pt for pt in [nose, l_eye, r_eye, l_ear, r_ear] if pt[2] >= self.min_conf]
        if len(valid_facial) < 1 and nose[2] < self.min_conf:
            return HeadOrientation(
                yaw=0.0,
                pitch=0.0,
                roll=0.0,
                confidence=0.1,
                direction=DirectionLabel.FORWARD,
                is_smoothed=False,
                crop_valid=False,
            )

        avg_conf = float(np.mean([pt[2] for pt in valid_facial])) if valid_facial else 0.5

        # Yaw estimation from multiple redundant geometric cues
        yaw_deg = 0.0
        has_l_eye = l_eye[2] >= self.min_conf
        has_r_eye = r_eye[2] >= self.min_conf
        has_l_ear = l_ear[2] >= self.min_conf
        has_r_ear = r_ear[2] >= self.min_conf
        has_shoulders = l_sh[2] >= self.min_conf and r_sh[2] >= self.min_conf

        # Cue 1: Eye midpoint and asymmetry
        if has_l_eye and has_r_eye:
            eye_mid_x = (l_eye[0] + r_eye[0]) / 2.0
            eye_span = max(abs(r_eye[0] - l_eye[0]), 5.0)
            offset = (nose[0] - eye_mid_x) / (eye_span * 0.5)
            yaw_deg = float(np.clip(offset * 52.0, -90.0, 90.0))
        elif has_l_eye and not has_r_eye:
            # Right eye occluded by head turn
            yaw_deg = 42.0
        elif has_r_eye and not has_l_eye:
            # Left eye occluded by head turn
            yaw_deg = -42.0
        elif has_l_ear and not has_r_ear:
            yaw_deg = 38.0
        elif has_r_ear and not has_l_ear:
            yaw_deg = -38.0

        # Cue 2: Ear-to-Nose geometry verification
        if has_l_ear and has_r_ear:
            ear_mid_x = (l_ear[0] + r_ear[0]) / 2.0
            ear_span = max(abs(r_ear[0] - l_ear[0]), 10.0)
            ear_offset = (nose[0] - ear_mid_x) / (ear_span * 0.5)
            ear_yaw = float(np.clip(ear_offset * 55.0, -90.0, 90.0))
            if abs(yaw_deg) < 5.0:
                yaw_deg = ear_yaw
            else:
                yaw_deg = (yaw_deg * 0.65) + (ear_yaw * 0.35)

        # Cue 3: Nose offset from shoulder axis (torso frame)
        if has_shoulders and nose[2] >= self.min_conf:
            sh_mid_x = (l_sh[0] + r_sh[0]) / 2.0
            sh_span = max(abs(r_sh[0] - l_sh[0]), 15.0)
            sh_offset = (nose[0] - sh_mid_x) / (sh_span * 0.5)
            if abs(sh_offset) > 0.25 and abs(yaw_deg) < 14.0:
                yaw_deg = float(np.clip(sh_offset * 45.0, -90.0, 90.0))

        # Pitch estimation from vertical drop
        pitch_deg = 0.0
        if has_l_eye and has_r_eye:
            eye_mid_y = (l_eye[1] + r_eye[1]) / 2.0
            eye_span = max(abs(r_eye[0] - l_eye[0]), 5.0)
            nose_drop = (nose[1] - eye_mid_y) / (eye_span * 0.5)
            pitch_deg = float(np.clip((0.52 - nose_drop) * 45.0, -90.0, 90.0))
        elif has_shoulders and nose[2] >= self.min_conf:
            sh_mid_y = (l_sh[1] + r_sh[1]) / 2.0
            sh_span = max(abs(r_sh[0] - l_sh[0]), 15.0)
            head_drop = (sh_mid_y - nose[1]) / sh_span
            if head_drop < 0.20:
                pitch_deg = -25.0  # Slouched / looking down
            elif head_drop > 0.65:
                pitch_deg = 25.0   # Looking straight up

        # Roll estimation
        roll_deg = 0.0
        if has_l_eye and has_r_eye:
            dy = r_eye[1] - l_eye[1]
            dx = r_eye[0] - l_eye[0]
            roll_deg = float(math.degrees(math.atan2(dy, max(abs(dx), 0.001))))

        # Direction classification with responsive thresholds
        direction = DirectionLabel.FORWARD
        if yaw_deg < -self.yaw_thresh:
            direction = DirectionLabel.LEFT
        elif yaw_deg > self.yaw_thresh:
            direction = DirectionLabel.RIGHT
        elif pitch_deg < self.pitch_down_thresh:
            direction = DirectionLabel.DOWN
        elif pitch_deg > self.pitch_up_thresh:
            direction = DirectionLabel.UP

        yaw_rad = math.radians(yaw_deg)
        pitch_rad = math.radians(pitch_deg)
        dx_raw = math.sin(yaw_rad)
        dy_raw = -math.cos(yaw_rad) * math.sin(pitch_rad)
        forward_z = math.cos(yaw_rad) * math.cos(pitch_rad)
        dx_proj = dx_raw
        dy_proj = dy_raw + (0.22 * max(forward_z, 0.0))
        mag = math.sqrt(dx_proj * dx_proj + dy_proj * dy_proj)
        arrow_vec = (round(float(dx_proj / mag), 4), round(float(dy_proj / mag), 4)) if mag > 1e-4 else (0.0, 1.0)

        return HeadOrientation(
            yaw=round(yaw_deg, 1),
            pitch=round(pitch_deg, 1),
            roll=round(roll_deg, 1),
            confidence=round(avg_conf, 3),
            direction=direction,
            is_smoothed=False,
            crop_valid=True,
            absolute_yaw=round(yaw_deg, 1),
            absolute_pitch=round(pitch_deg, 1),
            absolute_roll=round(roll_deg, 1),
            rotation_matrix=None,
            arrow_vector=arrow_vec,
        )


# ===========================================================================
# SixDRepNet Pipeline
# ===========================================================================

class SixDRepNetHeadPosePipeline:
    """
    Batched, smoothed, and hysteresis-stabilized head pose pipeline using SixDRepNet.
    """

    def __init__(
        self,
        estimator: Optional[SixDRepNetEstimator] = None,
        enabled: bool = True,
        inference_interval: int = 1,
        ema_alpha: float = 0.45,
        alpha: Optional[float] = None,
        yaw_threshold_deg: float = 22.0,
        yaw_threshold: Optional[float] = None,
        yaw_exit_threshold_deg: float = 14.0,
        yaw_exit_threshold: Optional[float] = None,
        pitch_down_threshold_deg: float = -20.0,
        pitch_down_threshold: Optional[float] = None,
        pitch_down_exit_deg: float = -14.0,
        pitch_up_threshold_deg: float = 18.0,
        pitch_up_exit_deg: float = 12.0,
        min_crop_width: int = 24,
        min_crop_w: Optional[int] = None,
        min_crop_height: int = 24,
        min_crop_h: Optional[int] = None,
        min_keypoint_conf: float = 0.25,
    ):
        self.estimator = estimator or SixDRepNetEstimator.get_instance()
        self.enabled = enabled
        self.interval = inference_interval
        self.alpha = alpha if alpha is not None else ema_alpha
        self.yaw_enter = yaw_threshold if yaw_threshold is not None else yaw_threshold_deg
        self.yaw_exit = yaw_exit_threshold if yaw_exit_threshold is not None else yaw_exit_threshold_deg
        self.pitch_down_enter = pitch_down_threshold if pitch_down_threshold is not None else pitch_down_threshold_deg
        self.pitch_down_exit = pitch_down_exit_deg
        self.pitch_up_enter = pitch_up_threshold_deg
        self.pitch_up_exit = pitch_up_exit_deg
        self.min_crop_w = min_crop_w if min_crop_w is not None else min_crop_width
        self.min_crop_h = min_crop_h if min_crop_h is not None else min_crop_height
        self.min_conf = min_keypoint_conf

        self._states: Dict[int, _TrackHeadPoseState] = {}
        self.heuristic_estimator = HeadOrientationEstimator(
            yaw_threshold_deg=self.yaw_enter,
            pitch_down_threshold_deg=self.pitch_down_enter,
            pitch_up_threshold_deg=self.pitch_up_enter,
            min_keypoint_conf=min_keypoint_conf,
        )

    def reset_track(self, track_id: int):
        """Reset internal temporal state for a given track."""
        if track_id in self._states:
            del self._states[track_id]

    def extract_head_crop(
        self,
        frame: np.ndarray,
        keypoints: Optional[KeypointSet] = None,
        bbox: Optional[BoundingBox] = None,
    ) -> Tuple[Optional[np.ndarray], float, bool]:
        """
        Extracts a clean, aspect-ratio-preserved bounding crop centered on the head.
        """
        img_h, img_w = frame.shape[:2]

        if not keypoints or keypoints.xy is None or len(keypoints.confidence) == 0:
            if bbox:
                # Fallback to upper 30% of person bounding box
                bx1, by1, bx2, by2 = bbox.x1, bbox.y1, bbox.x2, bbox.y2
                bh = by2 - by1
                hy2 = by1 + (bh * 0.32)
                hx1 = max(0, int(bx1))
                hy1 = max(0, int(by1))
                hx2 = min(img_w, int(bx2))
                hy2 = min(img_h, int(hy2))
                if (hx2 - hx1) >= self.min_crop_w and (hy2 - hy1) >= self.min_crop_h:
                    return frame[hy1:hy2, hx1:hx2], float(bbox.confidence * 0.5), True
            return None, 0.0, False

        nose = keypoints.get_point(KP_NOSE)
        l_eye = keypoints.get_point(KP_LEFT_EYE)
        r_eye = keypoints.get_point(KP_RIGHT_EYE)
        l_ear = keypoints.get_point(KP_LEFT_EAR)
        r_ear = keypoints.get_point(KP_RIGHT_EAR)
        l_sh = keypoints.get_point(KP_LEFT_SHOULDER)
        r_sh = keypoints.get_point(KP_RIGHT_SHOULDER)

        head_pts = [pt for pt in [nose, l_eye, r_eye, l_ear, r_ear] if pt[2] >= self.min_conf]

        if len(head_pts) < 1:
            if bbox:
                bx1, by1, bx2, by2 = bbox.x1, bbox.y1, bbox.x2, bbox.y2
                bh = by2 - by1
                hy2 = by1 + (bh * 0.32)
                hx1 = max(0, int(bx1))
                hy1 = max(0, int(by1))
                hx2 = min(img_w, int(bx2))
                hy2 = min(img_h, int(hy2))
                if (hx2 - hx1) >= self.min_crop_w and (hy2 - hy1) >= self.min_crop_h:
                    crop = frame[hy1:hy2, hx1:hx2]
                    return crop, float(bbox.confidence * 0.5), True
            return None, 0.0, False

        # Compute bounding rectangle of facial landmarks
        xs = [pt[0] for pt in head_pts]
        ys = [pt[1] for pt in head_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        
        # Estimate head scale from shoulder span or eye span
        head_size = max(max_x - min_x, max_y - min_y, 30.0)
        if l_sh[2] >= self.min_conf and r_sh[2] >= self.min_conf:
            sh_span = abs(r_sh[0] - l_sh[0])
            head_size = max(head_size, sh_span * 0.75)

        # Expand box for full head context (including hair, chin, forehead)
        pad = head_size * 0.65
        x1 = max(0, int(center_x - pad))
        y1 = max(0, int(center_y - (pad * 1.15)))  # Extra room above for forehead/hair
        x2 = min(img_w, int(center_x + pad))
        y2 = min(img_h, int(center_y + (pad * 0.85)))

        crop_w = x2 - x1
        crop_h = y2 - y1

        if crop_w < self.min_crop_w or crop_h < self.min_crop_h:
            return None, 0.0, False

        crop = frame[y1:y2, x1:x2]
        avg_conf = float(np.mean([pt[2] for pt in head_pts]))
        return crop, avg_conf, True

    def process_batch(
        self,
        frame: np.ndarray,
        tracked_objects: List[TrackedObject],
        keypoints_map: Dict[int, KeypointSet],
        frame_number: int,
    ) -> Dict[int, HeadOrientation]:
        """
        Processes all active tracks in a single batched pass.
        """
        results: Dict[int, HeadOrientation] = {}
        if not tracked_objects:
            return results

        # Clean up stale track states
        active_tids = {t.track_id for t in tracked_objects}
        for tid in list(self._states.keys()):
            if tid not in active_tids:
                del self._states[tid]

        # Determine which tracks need SixDRepNet inference this frame
        inference_indices = []
        crops_to_infer = []
        track_inference_info = []

        for track in tracked_objects:
            tid = track.track_id
            kps = keypoints_map.get(tid, KeypointSet.empty())

            if tid not in self._states:
                self._states[tid] = _TrackHeadPoseState(tid)

            state = self._states[tid]
            state.frames_since_inference += 1

            crop, conf, is_valid = self.extract_head_crop(frame, kps, track.bbox)

            if not is_valid or crop is None:
                # Use heuristic fallback
                heuristic_orient = self.heuristic_estimator.estimate(kps)
                results[tid] = heuristic_orient
                continue

            # Motion trigger check
            nose = kps.get_point(KP_NOSE)
            motion_triggered = False
            if nose[2] >= self.min_conf:
                if state.last_nose_pos is not None:
                    dist = math.hypot(nose[0] - state.last_nose_pos[0], nose[1] - state.last_nose_pos[1])
                    if dist > 8.0:
                        motion_triggered = True
                state.last_nose_pos = (nose[0], nose[1])

            # Check if inference is due
            needs_infer = (
                (state.frames_since_inference >= self.interval) or
                motion_triggered or
                (state.last_frame_num == 0)
            )

            if self.enabled and self.estimator and self.estimator.is_ready and needs_infer:
                inference_indices.append(tid)
                crops_to_infer.append(crop)
                track_inference_info.append((tid, conf))
            else:
                # Reuse/smooth previous angles and increment interval counter
                state.frames_since_inference += 1
                results[tid] = self._build_head_orientation(state, conf)

        # Run batched GPU inference for due tracks
        if crops_to_infer and self.estimator and self.estimator.is_ready:
            pitches, yaws, rolls, matrices = self.estimator.predict_batch(crops_to_infer, return_matrices=True)

            for i, (tid, conf) in enumerate(track_inference_info):
                state = self._states[tid]
                raw_yaw = float(yaws[i])
                raw_pitch = float(pitches[i])
                raw_roll = float(rolls[i])
                raw_mat = matrices[i]

                # First observation: initialize smoothed state and baseline directly
                if state.last_frame_num == 0 or state.neutral_yaw is None:
                    state.smoothed_yaw = raw_yaw
                    state.smoothed_pitch = raw_pitch
                    state.smoothed_roll = raw_roll
                    state.smoothed_rot_matrix = raw_mat
                    # Clamp initial neutral baseline to near 0 (frontal camera axis).
                    # A person looking sideways on frame 1 is already turned, not neutral.
                    state.neutral_yaw = float(np.clip(raw_yaw, -10.0, 10.0))
                    state.neutral_pitch = float(np.clip(raw_pitch, -10.0, 10.0))
                else:
                    # Exponential Moving Average (EMA) on continuous absolute angles
                    state.smoothed_yaw = (self.alpha * raw_yaw) + ((1.0 - self.alpha) * state.smoothed_yaw)
                    state.smoothed_pitch = (self.alpha * raw_pitch) + ((1.0 - self.alpha) * state.smoothed_pitch)
                    state.smoothed_roll = (self.alpha * raw_roll) + ((1.0 - self.alpha) * state.smoothed_roll)
                    if raw_mat is not None:
                        if state.smoothed_rot_matrix is None:
                            state.smoothed_rot_matrix = raw_mat
                        else:
                            state.smoothed_rot_matrix = (self.alpha * raw_mat) + ((1.0 - self.alpha) * state.smoothed_rot_matrix)

                # Compute relative rotation (delta) from resting desk orientation for behaviour classification
                raw_delta_yaw = state.smoothed_yaw - state.neutral_yaw
                raw_delta_pitch = state.smoothed_pitch - state.neutral_pitch

                # Slow adaptive update of neutral baseline ONLY during normal forward desk focus
                if abs(raw_delta_yaw) < 12.0:
                    state.neutral_yaw = (0.995 * state.neutral_yaw) + (0.005 * state.smoothed_yaw)
                if abs(raw_delta_pitch) < 10.0:
                    state.neutral_pitch = (0.995 * state.neutral_pitch) + (0.005 * state.smoothed_pitch)

                state.neutral_yaw = float(np.clip(state.neutral_yaw, -10.0, 10.0))
                state.neutral_pitch = float(np.clip(state.neutral_pitch, -10.0, 10.0))

                state.delta_yaw = state.smoothed_yaw - state.neutral_yaw
                state.delta_pitch = state.smoothed_pitch - state.neutral_pitch

                # Compute normalized 2D image arrow projection vector from absolute 3D head orientation
                yaw_rad = math.radians(state.smoothed_yaw)
                pitch_rad = math.radians(state.smoothed_pitch)
                dx_raw = math.sin(yaw_rad)
                dy_raw = -math.cos(yaw_rad) * math.sin(pitch_rad)
                forward_z = math.cos(yaw_rad) * math.cos(pitch_rad)
                dx_proj = dx_raw
                dy_proj = dy_raw + (0.22 * max(forward_z, 0.0))
                mag = math.sqrt(dx_proj * dx_proj + dy_proj * dy_proj)
                if mag > 1e-4:
                    state.arrow_vector = (round(float(dx_proj / mag), 4), round(float(dy_proj / mag), 4))
                else:
                    state.arrow_vector = (0.0, 1.0)

                state.raw_yaw = raw_yaw
                state.raw_pitch = raw_pitch
                state.raw_roll = raw_roll
                state.confidence = conf
                state.last_frame_num = frame_number
                state.frames_since_inference = 0

                # Direction classification with hysteresis on relative delta angles (for behaviour)
                state.current_direction = self._classify_hysteresis(
                    state.delta_yaw, state.delta_pitch, state.current_direction, conf
                )

                results[tid] = self._build_head_orientation(state, conf)

        # Fallback for tracks without results yet
        for track in tracked_objects:
            if track.track_id not in results:
                kps = keypoints_map.get(track.track_id, KeypointSet.empty())
                results[track.track_id] = self.heuristic_estimator.estimate(kps)

        return results

    def _classify_hysteresis(
        self,
        yaw: float,
        pitch: float,
        prev_direction: DirectionLabel,
        confidence: float,
    ) -> DirectionLabel:
        """
        Classifies discrete head orientation with dual-threshold hysteresis.
        Lateral head turns (LEFT/RIGHT) take precedence over vertical tilt.
        """
        if confidence < 0.25:
            return DirectionLabel.UNKNOWN

        # 1. Lateral head turn state machine with hysteresis
        if prev_direction == DirectionLabel.LEFT:
            if yaw > -self.yaw_exit:
                # Exited LEFT -> check RIGHT / DOWN / UP / FORWARD
                if yaw > self.yaw_enter:
                    return DirectionLabel.RIGHT
                if pitch < self.pitch_down_enter:
                    return DirectionLabel.DOWN
                if pitch > self.pitch_up_enter:
                    return DirectionLabel.UP
                return DirectionLabel.FORWARD
            return DirectionLabel.LEFT

        elif prev_direction == DirectionLabel.RIGHT:
            if yaw < self.yaw_exit:
                # Exited RIGHT -> check LEFT / DOWN / UP / FORWARD
                if yaw < -self.yaw_enter:
                    return DirectionLabel.LEFT
                if pitch < self.pitch_down_enter:
                    return DirectionLabel.DOWN
                if pitch > self.pitch_up_enter:
                    return DirectionLabel.UP
                return DirectionLabel.FORWARD
            return DirectionLabel.RIGHT

        # 2. Check entrance into lateral turn (takes precedence over down/up)
        if yaw < -self.yaw_enter:
            return DirectionLabel.LEFT
        if yaw > self.yaw_enter:
            return DirectionLabel.RIGHT

        # 3. Vertical pitch hysteresis
        if prev_direction == DirectionLabel.DOWN:
            if pitch > self.pitch_down_exit:
                if pitch > self.pitch_up_enter:
                    return DirectionLabel.UP
                return DirectionLabel.FORWARD
            return DirectionLabel.DOWN

        elif prev_direction == DirectionLabel.UP:
            if pitch < self.pitch_up_exit:
                if pitch < self.pitch_down_enter:
                    return DirectionLabel.DOWN
                return DirectionLabel.FORWARD
            return DirectionLabel.UP

        # 4. Standard pitch entry
        if pitch < self.pitch_down_enter:
            return DirectionLabel.DOWN
        if pitch > self.pitch_up_enter:
            return DirectionLabel.UP

        return DirectionLabel.FORWARD

    def _build_head_orientation(
        self, state: _TrackHeadPoseState, confidence: float
    ) -> HeadOrientation:
        """Construct canonical HeadOrientation dataclass from internal track state."""
        rot_mat_list = (
            state.smoothed_rot_matrix.tolist()
            if state.smoothed_rot_matrix is not None
            else None
        )
        return HeadOrientation(
            yaw=round(float(state.delta_yaw), 1),              # Behaviour relative delta yaw
            pitch=round(float(state.delta_pitch), 1),          # Behaviour relative delta pitch
            roll=round(float(state.smoothed_roll), 1),
            confidence=round(float(confidence), 3),
            direction=state.current_direction,
            is_smoothed=True,
            crop_valid=True,
            absolute_yaw=round(float(state.smoothed_yaw), 1),    # Physical absolute yaw
            absolute_pitch=round(float(state.smoothed_pitch), 1),# Physical absolute pitch
            absolute_roll=round(float(state.smoothed_roll), 1),
            rotation_matrix=rot_mat_list,
            arrow_vector=state.arrow_vector,
        )
