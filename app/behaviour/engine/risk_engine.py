"""Unified Behaviour and Spatial Risk Engine."""
import time
import math
import numpy as np
from typing import Dict, List, Optional, Tuple

from app.behaviour.schemas.pose import FrameInput, TrackPose, filter_student_tracks
from app.behaviour.schemas.events import (
    TrackRiskOutput,
    GroupEventOutput,
    FrameAnalysisResponse,
    BehaviourEvent,
    ReasonCode,
    RiskStatus,
)
from app.behaviour.detectors.head_gaze import HeadGazeDetector
from app.behaviour.detectors.torso_posture import TorsoPostureDetector
from app.behaviour.detectors.hand_desk_zone import HandDeskZoneDetector
from app.behaviour.detectors.writing_activity import WritingActivityDetector
from app.behaviour.detectors.sequence_automaton import SequenceAutomaton
from app.behaviour.baseline.personal_baseline import PersonalBaselineManager
from app.behaviour.temporal.temporal_interface import CTRGCNTemporalAnalyzer
from app.behaviour.spatial_group.chain_detector import CoordinatedGroupDetector
from app.behaviour.spatial_group.hall_layout import ExamHallLayout
from app.behaviour.fp_control.fp_controller import FalsePositiveController


class BehaviourRiskEngine:
    """Core Risk Engine computing continuous individual and group risk scores.
    
    Adheres strictly to privacy principles: operates only on anonymous track_id and seat_id,
    never outputs 'Cheating', and uses leaky accumulation with smooth exponential decay.
    """

    def __init__(
        self,
        layout: Optional[ExamHallLayout] = None,
        attack_rate: float = 0.85,      # Speed at which sustained behavior ramps risk up
        decay_rate: float = 0.35,       # Exponential decay rate per second when behavior returns to normal
    ):
        from app.config import get_settings
        self.settings = get_settings()
        self.layout = layout or ExamHallLayout()
        self.attack_rate = attack_rate
        self.decay_rate = decay_rate

        # Subsystems
        self.head_detector = HeadGazeDetector(layout=self.layout)
        self.torso_detector = TorsoPostureDetector()
        self.hand_detector = HandDeskZoneDetector()
        self.writing_detector = WritingActivityDetector()
        self.sequence_automaton = SequenceAutomaton()
        self.baseline_mgr = PersonalBaselineManager()
        self.temporal_analyzer = CTRGCNTemporalAnalyzer()
        self.group_detector = CoordinatedGroupDetector(self.layout)
        self.fp_controller = FalsePositiveController(self.layout)

        # Dynamic continuous risk tracking: {track_id: {"risk": float, "last_timestamp_ms": float, "duration_sec": float}}
        self._risk_states: Dict[str, Dict] = {}

    def _get_risk_state(self, track_id: str, seat_id: Optional[str] = None) -> Dict:
        key = track_id
        if key not in self._risk_states:
            self._risk_states[key] = {
                "risk": 0.0,
                "last_timestamp_ms": None,
                "sustained_duration_sec": 0.0,
            }
        return self._risk_states[key]

    def reset(self):
        """Reset internal state across all tracks for a fresh video analysis run."""
        self._risk_states.clear()
        if hasattr(self.head_detector, "_track_states"):
            self.head_detector._track_states.clear()
        if hasattr(self.torso_detector, "_track_states"):
            self.torso_detector._track_states.clear()
        if hasattr(self.hand_detector, "_track_states"):
            self.hand_detector._track_states.clear()
        if hasattr(self.sequence_automaton, "_event_histories"):
            self.sequence_automaton._event_histories.clear()
        if hasattr(self.baseline_mgr, "_buffers"):
            self.baseline_mgr._buffers.clear()
        if hasattr(self.baseline_mgr, "_profiles"):
            self.baseline_mgr._profiles.clear()
        if hasattr(self.temporal_analyzer, "buffers"):
            self.temporal_analyzer.buffers.clear()

    def reset_track(self, track_id: str):
        """Reset internal state for a given track."""
        if track_id in self._risk_states:
            del self._risk_states[track_id]
        self.head_detector.reset_track(track_id)
        self.torso_detector.reset_track(track_id)
        self.sequence_automaton.reset_track(track_id)

    def process_frame(self, frame: FrameInput) -> FrameAnalysisResponse:
        """Processes a multi-track frame packet through all intelligence pipelines."""
        t_start = time.perf_counter()
        timestamp_ms = frame.timestamp_ms
        tracks = filter_student_tracks(frame.tracks, valid_seats=None)  # No seat filter: Part 1 seat IDs are pass-through

        gaze_results = {}
        torso_results = {}
        hand_results = {}
        writing_results = {}
        baseline_results = {}
        temporal_results = {}
        sequence_results = {}

        # 1. Run Batched Temporal Analysis (bypassed if CTR-GCN is disabled for live risk)
        if self.settings.ctr_gcn_enabled and self.settings.ctr_gcn_use_for_risk:
            temporal_results = self.temporal_analyzer.analyze_tracks_batch(tracks, timestamp_ms)
        else:
            temporal_results = {
                tr.track_id: self.temporal_analyzer._default_result(tr.track_id)
                for tr in tracks
            }

        # 2. Run Individual Detectors per Track
        for tr in tracks:
            gaze_res = self.head_detector.analyze(tr, timestamp_ms, all_tracks=tracks)
            torso_res = self.torso_detector.analyze(tr, timestamp_ms)
            hand_res = self.hand_detector.analyze(tr, timestamp_ms)
            writing_res = self.writing_detector.analyze(
                tr, timestamp_ms, is_head_turning=(gaze_res.gaze_direction in ["LEFT", "RIGHT"])
            )

            # Measure instantaneous kinetic energy for baseline
            kinetic_energy = hand_res.hand_velocity_px_sec * 0.05 + abs(gaze_res.yaw_deg) * 0.001

            # Baseline deviation
            is_suspicious_now = (
                gaze_res.is_neighbor_gaze or torso_res.is_rotated or hand_res.hand_outside_zone
            )
            base_res = self.baseline_mgr.update_and_evaluate(
                tr.track_id,
                current_yaw=gaze_res.yaw_deg,
                current_pitch=gaze_res.pitch_deg,
                current_torso_rot=torso_res.torso_rotation_deg,
                current_kinetic_energy=kinetic_energy,
                is_currently_suspicious=is_suspicious_now,
            )

            temp_res = temporal_results.get(tr.track_id) or self.temporal_analyzer._default_result(tr.track_id)

            # Collect raw events
            combined_events = (
                gaze_res.detected_events +
                torso_res.detected_events +
                hand_res.detected_events +
                writing_res.detected_events +
                temp_res.detected_events
            )

            # Sequence Automaton
            seq_res = self.sequence_automaton.record_events(
                tr.track_id, combined_events, timestamp_ms
            )

            gaze_results[tr.track_id] = gaze_res
            torso_results[tr.track_id] = torso_res
            hand_results[tr.track_id] = hand_res
            writing_results[tr.track_id] = writing_res
            baseline_results[tr.track_id] = base_res
            sequence_results[tr.track_id] = seq_res

        # 2. Run Spatial Group Intelligence (Chains & Coordinated Pairs)
        group_analysis = self.group_detector.analyze(
            tracks, gaze_results, hand_results, torso_results, timestamp_ms
        )

        # 3. Compute Final Risk per Track with False-Positive Control & Leaky Integrator
        track_outputs: List[TrackRiskOutput] = []

        for tr in tracks:
            t_id = tr.track_id
            gaze_res = gaze_results[t_id]
            torso_res = torso_results[t_id]
            hand_res = hand_results[t_id]
            writing_res = writing_results[t_id]
            base_res = baseline_results[t_id]
            temp_res = temporal_results[t_id]
            seq_res = sequence_results[t_id]

            # False Positive evaluation
            fp_decision = self.fp_controller.evaluate(
                track=tr,
                gaze_res=gaze_res,
                torso_res=torso_res,
                hand_res=hand_res,
                baseline_res=base_res,
                invigilators=frame.invigilators,
            )

            # Aggregate all active event strings
            active_events_set = set()
            for ev in (
                gaze_res.detected_events +
                torso_res.detected_events +
                hand_res.detected_events +
                writing_res.detected_events +
                temp_res.detected_events +
                seq_res.detected_events +
                group_analysis.detected_events_by_track.get(t_id, [])
            ):
                active_events_set.add(ev.value)

            # Aggregate all reason codes
            reason_codes_set = set()
            for rc in (
                gaze_res.reason_codes +
                torso_res.reason_codes +
                hand_res.reason_codes +
                writing_res.reason_codes +
                temp_res.reason_codes +
                seq_res.reason_codes
            ):
                reason_codes_set.add(rc)

            # Object & Contraband Evidence Integration (Part 3)
            obj_evidence_list = tr.object_detections or []
            temp_obj_score = tr.temporal_object_score or 0.0

            # Extract highest confidence and persistence from object evidence
            valid_objs = [d for d in obj_evidence_list if float(d.get("confidence", 0.0)) >= 0.20]
            has_chit = any(str(d.get("object_class", "")).lower() in ("paper_chit", "chit", "paper") for d in valid_objs)
            has_phone = any(
                str(d.get("object_class", "")).lower() in ("mobile_phone", "phone", "cell phone", "cellphone", "smartphone")
                or "phone" in str(d.get("object_class", "")).lower()
                for d in valid_objs
            )
            has_prohibited = any(str(d.get("object_class", "")).lower() in ("prohibited_object", "book", "electronics") for d in valid_objs)

            # Check visibility
            vis_val = 1.0
            if tr.additional_meta and "visibility_overall" in tr.additional_meta:
                vis_val = float(tr.additional_meta["visibility_overall"])
            vis_factor = min(max(vis_val, 0.25), 1.0)

            # Object evidence events and reason codes
            if has_phone:
                active_events_set.add("PHONE_DETECTED")
                active_events_set.add(BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value)
                reason_codes_set.add(ReasonCode.CONTRABAND_ROI_EVIDENCE)
            elif (has_chit or (temp_obj_score >= 0.45 and not has_phone)) and temp_obj_score >= 0.38:
                active_events_set.add(BehaviourEvent.PAPER_CHIT_DETECTED.value)
                reason_codes_set.add(ReasonCode.PAPER_CHIT_SUSPICION)
                reason_codes_set.add(ReasonCode.CONTRABAND_ROI_EVIDENCE)
            elif has_prohibited or temp_obj_score >= 0.45:
                active_events_set.add(BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value)
                reason_codes_set.add(ReasonCode.CONTRABAND_ROI_EVIDENCE)

            if vis_val < 0.35:
                reason_codes_set.add(ReasonCode.OCCLUSION_LOW_VISIBILITY)

            # Aggregate all active event strings
            active_events = sorted(list(active_events_set))

            if fp_decision.suppression_reason:
                reason_codes_set.add(fp_decision.suppression_reason)

            # Instantaneous Target Risk Calculation
            target_risk = 0.0
            raw_yaw_mag = abs(float(gaze_res.yaw_deg))

            # Head Pose & Neighbor / Screen Gaze
            # Looking towards neighbor / another screen / away from workstation
            is_looking_away = (
                BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value in active_events or
                BehaviourEvent.NEIGHBOUR_GAZE.value in active_events or
                BehaviourEvent.HEAD_TURN_LEFT.value in active_events or
                BehaviourEvent.HEAD_TURN_RIGHT.value in active_events or
                gaze_res.gaze_direction in ["LEFT", "RIGHT"] or
                raw_yaw_mag >= 16.0
            )

            # Continuous angle-based risk
            if is_looking_away:
                if raw_yaw_mag >= 16.0:
                    base_gaze_risk = 35.0 + min((raw_yaw_mag - 16.0) * 1.6, 50.0)
                else:
                    base_gaze_risk = 35.0
                target_risk = max(target_risk, base_gaze_risk)

            if BehaviourEvent.PROLONGED_NEIGHBOUR_GAZE.value in active_events or gaze_res.is_prolonged_neighbor_gaze:
                target_risk = max(target_risk, 82.0)
            elif BehaviourEvent.NEIGHBOUR_GAZE.value in active_events or gaze_res.is_neighbor_gaze:
                target_risk = max(target_risk, 60.0)

            # Progressive penalty for prolonged stationary staring at neighbor
            if gaze_res.neighbor_gaze_duration_sec >= 1.5 and is_looking_away:
                target_risk = max(target_risk, min(65.0 + (gaze_res.neighbor_gaze_duration_sec - 1.0) * 15.0, 95.0))

            if BehaviourEvent.REPEATED_HEAD_TURN.value in active_events and is_looking_away:
                target_risk += 15.0

            if BehaviourEvent.HEAD_UP_SEARCHING.value in active_events:
                target_risk = max(target_risk, 40.0)

            # Torso Posture
            if BehaviourEvent.TORSO_ROTATION.value in active_events or torso_res.is_rotated:
                rot_risk = 40.0 + min(abs(float(torso_res.torso_rotation_deg)) * 0.8, 35.0)
                target_risk = max(target_risk, rot_risk)

            # Hand & Desk Reach Kinetics
            if BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value in active_events or hand_res.hand_outside_zone:
                target_risk = max(target_risk, 50.0)

            if BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value in active_events or hand_res.is_reaching_neighbor:
                target_risk = max(target_risk, 75.0)

            if BehaviourEvent.UNUSUAL_HAND_MOVEMENT.value in active_events or hand_res.is_unusual_hand_movement:
                target_risk += 15.0

            if BehaviourEvent.WRITING_STOPPED_WHILE_LOOKING_AROUND.value in active_events:
                target_risk += 20.0

            if BehaviourEvent.SUSPICIOUS_SEQUENCE_DETECTED.value in active_events:
                target_risk = max(target_risk, 70.0)

            if BehaviourEvent.CHAIN_INFORMATION_FLOW.value in active_events:
                target_risk = max(target_risk, 85.0)
            elif BehaviourEvent.COORDINATED_HAND_EXCHANGE.value in active_events:
                target_risk = max(target_risk, 80.0)
            elif BehaviourEvent.COORDINATED_GAZE.value in active_events:
                target_risk = max(target_risk, 50.0)

            if "PHONE_DETECTED" in active_events:
                target_risk = max(target_risk, 85.0)
            elif BehaviourEvent.PAPER_CHIT_DETECTED.value in active_events:
                target_risk = max(target_risk, 75.0)
            elif BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value in active_events:
                target_risk = max(target_risk, 70.0)

            # Calibrated Object Evidence Strength
            obj_conf = 0.0
            if valid_objs:
                obj_conf = max(d.get("confidence", 0.0) for d in valid_objs)
            if temp_obj_score > 0.35:
                obj_conf = max(obj_conf, temp_obj_score)

            if obj_conf >= 0.35:
                norm_strength = min(max((obj_conf - 0.35) / 0.65, 0.0), 1.0)
                behaviour_boost = 1.35 if (
                    BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value in active_events or
                    BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value in active_events or
                    BehaviourEvent.TORSO_ROTATION.value in active_events
                ) else 1.0

                object_risk_contribution = norm_strength * 45.0 * behaviour_boost * vis_factor
                target_risk += object_risk_contribution

            # Normal Screen Focus: Looking forward at one's own screen or down at desk is 100% normal
            is_normal_screen_focus = (
                gaze_res.gaze_direction in ["FORWARD", "DOWN"] and
                raw_yaw_mag < 14.0 and
                not is_looking_away
            )

            has_physical_violation = bool(
                set(active_events) & {
                    BehaviourEvent.HAND_OUTSIDE_DESK_ZONE.value,
                    BehaviourEvent.REACHING_TOWARDS_NEIGHBOUR.value,
                    BehaviourEvent.PAPER_CHIT_DETECTED.value,
                    BehaviourEvent.OBJECT_EVIDENCE_DETECTED.value,
                    BehaviourEvent.COORDINATED_HAND_EXCHANGE.value,
                    BehaviourEvent.TORSO_ROTATION.value,
                }
            )
            if is_normal_screen_focus and not has_physical_violation:
                target_risk = 0.0

            # Scale target risk by baseline deviation
            if base_res.is_meaningful_deviation:
                target_risk *= (1.0 + min(base_res.deviation_score * 0.15, 0.6))

            # Apply False-Positive dampening factor
            target_risk *= fp_decision.risk_dampening_factor
            target_risk = min(target_risk, 100.0)

            # Leaky Integrator with Exponential Decay
            r_state = self._get_risk_state(t_id, tr.seat_id)
            dt_sec = 0.05  # default nominal frame dt
            if r_state["last_timestamp_ms"] is not None:
                dt_sec = max((timestamp_ms - r_state["last_timestamp_ms"]) / 1000.0, 0.001)
                if dt_sec > 2.0:
                    dt_sec = 0.05

            current_risk = r_state["risk"]

            is_actively_looking_away = (
                gaze_res.gaze_direction in ["LEFT", "RIGHT"] or
                is_looking_away or
                raw_yaw_mag >= 16.0
            )

            if target_risk > current_risk:
                # Responsive immediate jump on clear behavioral anomaly
                r_state["risk"] = max(current_risk + (target_risk - current_risk) * min(self.attack_rate * dt_sec * 10.0, 1.0), target_risk * 0.82)
                r_state["sustained_duration_sec"] += dt_sec
            elif is_actively_looking_away:
                # When looking steadily at neighbor's screen, MAINTAIN high risk without decaying
                r_state["risk"] = max(current_risk, target_risk)
                r_state["sustained_duration_sec"] += dt_sec
            else:
                # Decay: exponential decay towards normal ONLY when student looks back to FORWARD / DOWN
                decay_factor = math.exp(-self.decay_rate * dt_sec * 2.5)
                r_state["risk"] = current_risk * decay_factor
                if r_state["risk"] < 6.0:
                    r_state["risk"] = 0.0
                    r_state["sustained_duration_sec"] = 0.0
                else:
                    r_state["sustained_duration_sec"] = max(r_state["sustained_duration_sec"] - dt_sec, 0.0)

            r_state["last_timestamp_ms"] = timestamp_ms
            final_risk_score = int(round(r_state["risk"]))

            # Confidence
            conf = min(max(gaze_res.confidence - fp_decision.confidence_penalty, 0.1), 0.98)

            # Classify status (Never Cheating)
            if final_risk_score < 25:
                status = RiskStatus.NORMAL
                if not reason_codes_set:
                    reason_codes_set.add(ReasonCode.NORMAL_TEST_TAKING)
            elif final_risk_score < 50:
                status = RiskStatus.MONITORING
            elif final_risk_score < 75:
                status = RiskStatus.UNUSUAL_BEHAVIOUR
            else:
                status = RiskStatus.SUSPICIOUS_BEHAVIOUR

            group_id = group_analysis.track_to_group_map.get(t_id)

            track_outputs.append(
                TrackRiskOutput(
                    track_id=t_id,
                    seat_id=tr.seat_id,
                    risk_score=final_risk_score,
                    confidence=round(conf, 2),
                    events=active_events,
                    group_id=group_id,
                    duration_sec=round(r_state["sustained_duration_sec"], 1),
                    baseline_deviation=round(base_res.deviation_score, 2),
                    reason_codes=sorted(list(reason_codes_set)),
                    status=status,
                    gaze_angle_deg=gaze_res.yaw_deg,
                    torso_angle_deg=torso_res.torso_rotation_deg,
                    hand_outside_zone=hand_res.hand_outside_zone,
                    writing_active=writing_res.is_writing,
                    is_suppressed_by_context=fp_decision.is_suppressed,
                    object_evidence=obj_evidence_list if obj_evidence_list else None,
                    temporal_object_score=round(temp_obj_score, 3) if temp_obj_score > 0 else None,
                )
            )

        latency_ms = (time.perf_counter() - t_start) * 1000.0

        return FrameAnalysisResponse(
            frame_id=frame.frame_id,
            timestamp_ms=timestamp_ms,
            room_id=frame.room_id,
            tracks=track_outputs,
            groups=group_analysis.group_events,
            global_invigilator_context={
                "invigilator_count": len(frame.invigilators or []),
                "exam_phase": frame.exam_phase,
                "chains_count": len(group_analysis.active_chains),
            },
            system_latency_ms=round(latency_ms, 2),
        )
