"""
Real-time debug visualization overlay — redesigned for clarity.

Clean, readable overlay with:
- Large text labels
- Semi-transparent info panels
- Color-coded states
- Prominent head direction arrows
- Clear skeleton rendering
"""

from __future__ import annotations

import logging
import math
import os
from typing import Optional

import cv2
import numpy as np

from app.perception.core.constants import (
    UPPER_BODY_SKELETON,
    KP_NOSE,
    KP_LEFT_EYE,
    KP_RIGHT_EYE,
    KP_LEFT_EAR,
    KP_RIGHT_EAR,
    KP_LEFT_SHOULDER,
    KP_RIGHT_SHOULDER,
    KP_LEFT_ELBOW,
    KP_RIGHT_ELBOW,
    KP_LEFT_WRIST,
    KP_RIGHT_WRIST,
    TrackingState,
    VisibilityLevel,
    DirectionLabel,
    DEFAULT_KEYPOINT_CONF,
)
from app.perception.core.data_models import PipelineOutput, StudentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clean color palette (BGR)
# ---------------------------------------------------------------------------
# Bounding boxes
CLR_TRACKED = (0, 230, 118)     # Bright green
CLR_COASTING = (50, 180, 255)   # Warm orange
CLR_NEW = (255, 180, 50)        # Sky blue
CLR_LOST = (100, 100, 100)      # Gray

# Skeleton
CLR_SKELETON_LINE = (255, 255, 100)   # Light cyan
CLR_SKELETON_JOINT = (255, 255, 255)  # White dots

# Head
CLR_HEAD_ARROW = (80, 80, 255)  # Bright red
CLR_HEAD_TEXT = (80, 80, 255)   # Same red

# Labels
CLR_LABEL_BG = (30, 30, 30)    # Dark background
CLR_LABEL_TEXT = (255, 255, 255)  # White text

# Visibility bar
CLR_VIS_GOOD = (0, 220, 100)   # Green
CLR_VIS_PARTIAL = (0, 200, 255)  # Orange
CLR_VIS_POOR = (0, 80, 255)    # Red
CLR_VIS_BG = (60, 60, 60)      # Bar background

# HUD
CLR_HUD_BG = (20, 20, 20)      # Panel background
CLR_HUD_TEXT = (200, 200, 200)  # Light gray text
CLR_HUD_ACCENT = (0, 230, 118)  # Green accent

# Desk ROI
CLR_DESK = (180, 80, 255)      # Purple


class DebugVisualizer:
    """
    Clean, readable debug overlay for the perception pipeline.

    Args:
        enabled: Master toggle.
        show_skeleton: Draw body skeleton.
        show_bbox: Draw bounding boxes.
        show_track_id: Show track IDs.
        show_seat_id: Show seat IDs.
        show_head_direction: Draw head arrows.
        show_visibility: Show visibility bars.
        show_desk_roi: Draw desk regions.
        show_fps: Show performance HUD.
        show_frame_health: Show stream health.
        keypoint_conf_threshold: Min confidence to draw keypoint.
    """

    def __init__(
        self,
        enabled: bool = True,
        show_skeleton: bool = True,
        show_bbox: bool = False,  # Clean UI: Human bounding boxes removed from normal view
        show_track_id: bool = True,
        show_seat_id: bool = True,
        show_head_direction: bool = True,
        show_visibility: bool = False,
        show_desk_roi: bool = False,
        show_fps: bool = False,
        show_hands: bool = False,
        show_frame_health: bool = False,
        keypoint_conf_threshold: float = DEFAULT_KEYPOINT_CONF,
    ):
        self.enabled = enabled
        self.show_skeleton = show_skeleton
        self.show_bbox = show_bbox
        self.show_track_id = show_track_id
        self.show_seat_id = show_seat_id
        self.show_head_direction = show_head_direction
        self.show_visibility = show_visibility
        self.show_desk_roi = show_desk_roi
        self.show_fps = False
        self.show_hands = show_hands
        self.show_frame_health = False
        self.kp_conf = keypoint_conf_threshold

    def draw(
        self,
        frame: np.ndarray,
        output: Optional[PipelineOutput] = None,
        risk_by_track: Optional[Dict[str, Any]] = None,
        roboflow_detections: Optional[List[Dict[str, Any]]] = None,
        roboflow_metrics: Optional[Dict[str, Any]] = None,
    ) -> Optional[np.ndarray]:
        """Draw complete debug visualization on a copy of the frame."""
        if not self.enabled:
            return None

        canvas = frame.copy()

        # 1. Draw students (Skeletons + Compact Labels + Tight Object Evidence Boxes)
        if output is not None and getattr(output, "students", None):
            tracked_students = [s for s in output.students if s.tracking_state == TrackingState.TRACKED]
            coasting_students = [s for s in output.students if s.tracking_state == TrackingState.COASTING]

            active_to_draw = list(tracked_students)
            for cs in coasting_students:
                if cs.bbox:
                    overlaps = any(
                        cs.bbox.iou(ts.bbox) >= 0.25
                        for ts in tracked_students
                        if ts.bbox
                    )
                    if not overlaps and cs.frames_since_seen <= 15:  # Brief coasting only (<0.6s)
                        active_to_draw.append(cs)

            for s in active_to_draw:
                self._draw_student(canvas, s, risk_by_track=risk_by_track)

        # 2. Draw Roboflow Phone Detections & Evidence Overlay
        if roboflow_detections or roboflow_metrics:
            self._draw_roboflow_overlay(canvas, roboflow_detections or [], roboflow_metrics or {})

        return canvas

    def _draw_roboflow_overlay(
        self,
        frame: np.ndarray,
        phone_detections: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> None:
        """Draw Roboflow phone / calculator detections and high-visibility evidence overlay."""
        for det in phone_detections:
            bbox = det.get("bbox") or []
            conf = float(det.get("confidence", 0.0))
            cls_name = str(det.get("class_name", "PHONE")).upper()
            is_permitted = det.get("is_permitted", False) or (cls_name == "CALCULATOR")

            if len(bbox) == 4 and conf >= 0.15:
                x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

                if is_permitted or cls_name == "CALCULATOR":
                    box_color = (0, 220, 100)      # Emerald Green
                    bg_color = (0, 160, 70)
                    label = f"CALCULATOR (Permitted) {int(conf * 100)}%"
                else:
                    box_color = (0, 0, 235)        # Crimson Red
                    bg_color = (0, 0, 200)
                    label = f"PHONE {int(conf * 100)}%"

                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 0.45
                (tw, th), _ = cv2.getTextSize(label, font, scale, 1)

                cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), bg_color, -1)
                cv2.putText(frame, label, (x1 + 4, max(12, y1 - 4)), font, scale, (255, 255, 255), 1, cv2.LINE_AA)

    # ===================================================================
    # Student overlay
    # ===================================================================

    def _draw_student(
        self,
        frame: np.ndarray,
        s: StudentState,
        risk_by_track: Optional[Dict[str, Any]] = None,
    ):
        """Draw clean student representation: skeleton, compact label, and tight object evidence boxes."""
        risk_info = risk_by_track.get(s.track_id) if risk_by_track else None
        risk_score = 0
        if risk_info is not None:
            if hasattr(risk_info, "risk_score"):
                risk_score = int(risk_info.risk_score)
            elif isinstance(risk_info, dict):
                risk_score = int(risk_info.get("risk_score", 0))
            elif isinstance(risk_info, (int, float)):
                risk_score = int(risk_info)

        # Risk-aware accent color
        if risk_score >= 80:
            status_color = (0, 0, 235)       # Critical: Crimson Red
        elif risk_score >= 60:
            status_color = (0, 165, 255)     # High: Amber Orange
        elif risk_score >= 30:
            status_color = (255, 200, 0)     # Watch: Cyan
        else:
            status_color = (0, 230, 118)     # Low: Green

        # 1. Skeleton (Primary visual representation of human)
        if self.show_skeleton and s.keypoints:
            is_coasting = (s.tracking_state == TrackingState.COASTING)
            self._draw_skeleton(frame, s.keypoints, is_coasting=is_coasting)

        # 2. Head direction arrow
        if self.show_head_direction and s.head_orientation:
            if s.head_orientation.direction != DirectionLabel.UNKNOWN:
                self._draw_head_arrow(frame, s)

        # 3. Compact Student Label (No human box rectangle)
        self._draw_compact_label(frame, s, status_color, risk_score=risk_score)

        # 4. Tight Object Bounding Boxes (ONLY for verified contraband evidence)
        objs = getattr(risk_info, "object_evidence", None) or []
        for obj in objs:
            if isinstance(obj, dict):
                cls_name = obj.get("object_class", "unknown_object")
                conf = float(obj.get("confidence", 0.0))
                bbox = obj.get("bbox") or []
            else:
                cls_name = getattr(obj, "object_class", "unknown_object")
                conf = float(getattr(obj, "confidence", 0.0))
                bbox = getattr(obj, "bbox", []) or []

            # Only draw object box if confidence meets threshold and valid box exists
            if conf >= 0.45 and len(bbox) == 4:
                ox1, oy1, ox2, oy2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                # Ensure tight box dimensions
                if (ox2 - ox1) > 0 and (oy2 - oy1) > 0:
                    obj_color = (0, 165, 255) if cls_name == "paper_chit" else (0, 0, 235)
                    cv2.rectangle(frame, (ox1, oy1), (ox2, oy2), obj_color, 2, cv2.LINE_AA)

                    clean_cls = cls_name.replace("_", " ").upper()
                    obj_label = f"{clean_cls} {int(conf * 100)}%"

                    # Compact pill label for object
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 0.40
                    (tw, th), _ = cv2.getTextSize(obj_label, font, scale, 1)
                    cv2.rectangle(frame, (ox1, max(0, oy1 - th - 6)), (ox1 + tw + 6, oy1), (15, 15, 15), -1)
                    cv2.putText(frame, obj_label, (ox1 + 3, max(10, oy1 - 3)), font, scale, obj_color, 1, cv2.LINE_AA)

    def _draw_compact_label(
        self,
        frame: np.ndarray,
        s: StudentState,
        color: tuple,
        risk_score: int = 0,
    ):
        """Draw a compact, uncluttered status tag above the student's head."""
        parts = []
        if self.show_track_id:
            parts.append(s.track_id)
        if self.show_seat_id and s.seat_id != "UNASSIGNED":
            parts.append(f"Seat {s.seat_id}")

        if risk_score >= 80:
            parts.append(f"CRITICAL {risk_score}")
        elif risk_score >= 60:
            parts.append(f"HIGH {risk_score}")
        elif risk_score >= 30:
            parts.append(f"WATCH {risk_score}")
        else:
            parts.append(f"RISK {risk_score}")

        label = " | ".join(parts)

        # Position above head/nose keypoint or top of bbox
        if s.keypoints:
            nose_x, nose_y, conf = s.keypoints.get_point(KP_NOSE)
            if conf > 0.15:
                x = int(nose_x)
                y = int(nose_y) - 18
            elif s.bbox:
                x = int(s.bbox.x1)
                y = int(s.bbox.y1) - 8
            else:
                return
        elif s.bbox:
            x = int(s.bbox.x1)
            y = int(s.bbox.y1) - 8
        else:
            return

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.44
        thick = 1
        (tw, th), baseline = cv2.getTextSize(label, font, scale, thick)

        # Background pill
        pad = 5
        cv2.rectangle(
            frame,
            (x - pad, y - th - pad - 2),
            (x + tw + pad, y + baseline + pad - 2),
            color, -1, cv2.LINE_AA,
        )

        # Text
        text_color = (0, 0, 0) if (color[0] + color[1] + color[2] > 300) else (255, 255, 255)
        cv2.putText(frame, label, (x, y), font, scale, text_color, thick, cv2.LINE_AA)

    def _draw_skeleton(self, frame: np.ndarray, kps, is_coasting: bool = False):
        """Draw upper-body skeleton with clean lines and visible joints."""
        line_color = CLR_COASTING if is_coasting else CLR_SKELETON_LINE
        joint_color = (200, 220, 255) if is_coasting else CLR_SKELETON_JOINT
        line_thick = 1 if is_coasting else 2

        # Dual threshold for bone connectivity
        min_joint_conf = 0.15 if is_coasting else 0.18
        pair_high_conf = 0.20 if is_coasting else 0.25

        # Lines
        for i, j in UPPER_BODY_SKELETON:
            xi, yi, ci = kps.get_point(i)
            xj, yj, cj = kps.get_point(j)

            # Valid if both meet standard threshold or at least one is strong and other above minimum
            is_valid_bone = (ci >= self.kp_conf and cj >= self.kp_conf) or (
                min(ci, cj) >= min_joint_conf and max(ci, cj) >= pair_high_conf
            )
            if is_valid_bone:
                cv2.line(
                    frame,
                    (int(xi), int(yi)), (int(xj), int(yj)),
                    line_color, line_thick, cv2.LINE_AA,
                )

        # Joints — draw over lines
        important_joints = [
            KP_NOSE, KP_LEFT_EYE, KP_RIGHT_EYE,
            KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER,
            KP_LEFT_ELBOW, KP_RIGHT_ELBOW,
            KP_LEFT_WRIST, KP_RIGHT_WRIST,
        ]
        for idx in important_joints:
            x, y, c = kps.get_point(idx)
            if c >= min_joint_conf:
                # Larger dots for shoulders and wrists
                r = 4 if idx in (KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER, KP_LEFT_WRIST, KP_RIGHT_WRIST) else 3
                if is_coasting:
                    r = max(2, r - 1)
                cv2.circle(frame, (int(x), int(y)), r, joint_color, -1, cv2.LINE_AA)
                cv2.circle(frame, (int(x), int(y)), r, line_color, 1, cv2.LINE_AA)

    def _draw_head_arrow(self, frame: np.ndarray, s: StudentState):
        """Draw an accurate head direction vector / gaze indicator."""
        if s.keypoints is None or s.head_orientation is None:
            return

        # Find reliable anchor point (nose or eye midpoint)
        nose_x, nose_y, nose_c = s.keypoints.get_point(KP_NOSE)
        l_x, l_y, l_c = s.keypoints.get_point(KP_LEFT_EYE)
        r_x, r_y, r_c = s.keypoints.get_point(KP_RIGHT_EYE)

        if nose_c >= 0.20:
            anchor_x, anchor_y = nose_x, nose_y
        elif l_c >= 0.20 and r_c >= 0.20:
            anchor_x, anchor_y = (l_x + r_x) / 2.0, (l_y + r_y) / 2.0
        elif s.bbox:
            anchor_x = (s.bbox.x1 + s.bbox.x2) / 2.0
            anchor_y = s.bbox.y1 + (s.bbox.height * 0.18)
        else:
            return

        # Absolute physical head orientation for physical direction visualization
        abs_yaw = getattr(s.head_orientation, "absolute_yaw", s.head_orientation.yaw)
        abs_pitch = getattr(s.head_orientation, "absolute_pitch", s.head_orientation.pitch)
        abs_roll = getattr(s.head_orientation, "absolute_roll", s.head_orientation.roll)
        delta_yaw = s.head_orientation.yaw
        delta_pitch = s.head_orientation.pitch
        direction = s.head_orientation.direction
        conf = max(0.4, s.head_orientation.confidence)

        if direction == DirectionLabel.UNKNOWN:
            return

        # Starting anchor dot at nose / facial landmark
        cv2.circle(frame, (int(anchor_x), int(anchor_y)), 3, CLR_HEAD_ARROW, -1, cv2.LINE_AA)

        # Retrieve or compute normalized 2D image vector from physical 3D head pose
        arrow_len = 40.0
        if getattr(s.head_orientation, "arrow_vector", None) is not None:
            dx_norm, dy_norm = s.head_orientation.arrow_vector
        else:
            yaw_clamped = float(np.clip(abs_yaw, -90.0, 90.0))
            pitch_clamped = float(np.clip(abs_pitch, -60.0, 60.0))
            rad_yaw = math.radians(yaw_clamped)
            rad_pitch = math.radians(pitch_clamped)
            dx_raw = math.sin(rad_yaw)
            dy_raw = -math.cos(rad_yaw) * math.sin(rad_pitch)
            forward_z = math.cos(rad_yaw) * math.cos(rad_pitch)
            dx_p = dx_raw
            dy_p = dy_raw + (0.22 * max(forward_z, 0.0))
            m = math.sqrt(dx_p * dx_p + dy_p * dy_p)
            dx_norm, dy_norm = (dx_p / m, dy_p / m) if m > 1e-4 else (0.0, 1.0)

        gaze_end = (int(anchor_x + (dx_norm * arrow_len)), int(anchor_y + (dy_norm * arrow_len)))

        # Color coding for gaze ray
        if direction in (DirectionLabel.LEFT, DirectionLabel.RIGHT):
            ray_color = (0, 165, 255)  # Amber orange for lateral head turn
            ray_thick = 3
        elif direction == DirectionLabel.DOWN:
            ray_color = (255, 200, 0)  # Cyan for looking down at desk paper
            ray_thick = 2
        elif direction == DirectionLabel.UP:
            ray_color = (0, 200, 255)  # Yellow for searching up
            ray_thick = 2
        else:
            ray_color = (0, 230, 118)  # Bright green for normal forward focus
            ray_thick = 2

        # Draw primary gaze ray arrow
        cv2.arrowedLine(
            frame,
            (int(anchor_x), int(anchor_y)),
            gaze_end,
            ray_color, ray_thick, cv2.LINE_AA, tipLength=0.30,
        )

        font = cv2.FONT_HERSHEY_SIMPLEX
        debug_mode = os.environ.get("DEBUG_HEAD_POSE", "false").lower() == "true"
        if debug_mode:
            # Extended debug inspection overlay
            lines = [
                f"ABS Y:{int(abs_yaw):+d} P:{int(abs_pitch):+d}",
                f"dY:{int(delta_yaw):+d} dP:{int(delta_pitch):+d}",
                f"DIR:{direction.value}",
                f"VEC:({dx_norm:+.2f}, {dy_norm:+.2f})",
            ]
            for idx, text_line in enumerate(lines):
                cv2.putText(
                    frame, text_line,
                    (int(anchor_x) + 8, int(anchor_y) - 18 + (idx * 11)),
                    font, 0.30, (0, 255, 255), 1, cv2.LINE_AA,
                )
        else:
            # Standard compact angle badge
            badge_text = f"Y:{int(abs_yaw):+d} P:{int(abs_pitch):+d}"
            cv2.putText(
                frame, badge_text,
                (int(anchor_x) + 8, int(anchor_y) - 6),
                font, 0.34, (240, 240, 240), 1, cv2.LINE_AA,
            )


    def _draw_visibility_bar(self, frame: np.ndarray, s: StudentState):
        """Draw a clean visibility progress bar below the bounding box."""
        if s.visibility is None or s.bbox is None:
            return

        overall = s.visibility.overall
        cam_vis = s.visibility.camera_visibility

        if cam_vis == VisibilityLevel.GOOD:
            bar_clr = CLR_VIS_GOOD
        elif cam_vis == VisibilityLevel.PARTIAL:
            bar_clr = CLR_VIS_PARTIAL
        else:
            bar_clr = CLR_VIS_POOR

        x = int(s.bbox.x1)
        y = int(s.bbox.y2) + 4
        full_w = int(s.bbox.width)
        fill_w = int(full_w * overall)
        bar_h = 6

        # Background
        cv2.rectangle(frame, (x, y), (x + full_w, y + bar_h), CLR_VIS_BG, -1)
        # Fill
        if fill_w > 0:
            cv2.rectangle(frame, (x, y), (x + fill_w, y + bar_h), bar_clr, -1)

        # Percentage text
        pct_text = f"{int(overall * 100)}%"
        cv2.putText(
            frame, pct_text,
            (x + full_w + 5, y + bar_h),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, bar_clr, 1, cv2.LINE_AA,
        )

    # ===================================================================
    # HUD Panel
    # ===================================================================

    def _draw_hud(self, frame: np.ndarray, output: PipelineOutput):
        """Draw a clean HUD panel in the top-left corner."""
        meta = output.frame_meta
        h, w = frame.shape[:2]

        # Semi-transparent background panel
        panel_w = 220
        panel_h = 100
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (5 + panel_w, 5 + panel_h), CLR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Panel border
        cv2.rectangle(frame, (5, 5), (5 + panel_w, 5 + panel_h), CLR_HUD_ACCENT, 1, cv2.LINE_AA)

        # Content
        font = cv2.FONT_HERSHEY_SIMPLEX
        x, y = 15, 28

        # FPS (big and green)
        fps_text = f"FPS: {meta.pipeline_fps:.1f}"
        cv2.putText(frame, fps_text, (x, y), font, 0.6, CLR_HUD_ACCENT, 2, cv2.LINE_AA)
        y += 22

        # Latency
        lat_text = f"Latency: {meta.pipeline_latency_ms:.0f}ms"
        cv2.putText(frame, lat_text, (x, y), font, 0.45, CLR_HUD_TEXT, 1, cv2.LINE_AA)
        y += 18

        # Students
        n_students = len(output.students)
        n_tracked = sum(1 for s in output.students if s.tracking_state == TrackingState.TRACKED)
        stu_text = f"Students: {n_tracked}/{n_students}"
        cv2.putText(frame, stu_text, (x, y), font, 0.45, CLR_HUD_TEXT, 1, cv2.LINE_AA)
        y += 18

        # Frame number
        frame_text = f"Frame: {meta.frame_number}"
        cv2.putText(frame, frame_text, (x, y), font, 0.40, (140, 140, 140), 1, cv2.LINE_AA)

        # Stream health indicator (top-right)
        if self.show_frame_health and output.frame_health:
            self._draw_health_badge(frame, output)

    def _draw_health_badge(self, frame: np.ndarray, output: PipelineOutput):
        """Draw stream health badge in top-right corner."""
        health = output.frame_health
        if health is None:
            return

        h, w = frame.shape[:2]
        status = health.stream_status.value

        if status == "CONNECTED":
            clr = CLR_VIS_GOOD
            icon = "●"
        elif status == "RECONNECTING":
            clr = CLR_VIS_PARTIAL
            icon = "◐"
        else:
            clr = CLR_VIS_POOR
            icon = "○"

        text = f"{status}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(text, font, 0.4, 1)

        x = w - tw - 20
        y = 25

        # Background
        cv2.rectangle(frame, (x - 8, y - th - 5), (x + tw + 8, y + 8), CLR_HUD_BG, -1)

        # Status dot
        cv2.circle(frame, (x - 2, y - th // 2), 4, clr, -1, cv2.LINE_AA)

        # Text
        cv2.putText(frame, text, (x + 8, y), font, 0.4, clr, 1, cv2.LINE_AA)

    def _draw_help_bar(self, frame: np.ndarray):
        """Draw keyboard shortcuts at the bottom of the frame."""
        h, w = frame.shape[:2]

        bar_h = 22
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - bar_h), (w, h), CLR_HUD_BG, -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        help_text = "[Q] Quit   [S] Skeleton   [H] Head   [V] Visibility   [D] Desk   [T] Timing"
        cv2.putText(
            frame, help_text,
            (10, h - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1, cv2.LINE_AA,
        )

    # ===================================================================
    # Utilities
    # ===================================================================

    def _state_color(self, state: TrackingState) -> tuple:
        if state == TrackingState.TRACKED:
            return CLR_TRACKED
        elif state == TrackingState.COASTING:
            return CLR_COASTING
        elif state == TrackingState.NEW:
            return CLR_NEW
        return CLR_LOST

    # Toggle methods
    def toggle_visibility(self):
        self.show_visibility = not self.show_visibility
        logger.info("Visibility: %s", "ON" if self.show_visibility else "OFF")

    def toggle_skeleton(self):
        self.show_skeleton = not self.show_skeleton
        logger.info("Skeleton: %s", "ON" if self.show_skeleton else "OFF")

    def toggle_head_direction(self):
        self.show_head_direction = not self.show_head_direction
        logger.info("Head direction: %s", "ON" if self.show_head_direction else "OFF")

    def toggle_desk_roi(self):
        self.show_desk_roi = not self.show_desk_roi
        logger.info("Desk ROI: %s", "ON" if self.show_desk_roi else "OFF")
