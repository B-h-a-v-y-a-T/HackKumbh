import asyncio
import time
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.schemas.perception import Part1PerceptionInput
from app.schemas.behaviour import Part2BehaviourInput
from app.schemas.verification import Part3VerificationInput
from app.integrations.part1_adapter import Part1Adapter
from app.integrations.part2_adapter import Part2Adapter
from app.integrations.part3_adapter import Part3Adapter
from app.services.alert_service import AlertService
from app.services.integration_service import IntegrationService
from app.core.websocket_manager import manager
from app.database.session import SessionLocal
from app.models.event import Event

def _save_event_to_db(db: Session, normalized) -> Event:
    db_event = Event(
        id=normalized.event_id,
        source=normalized.source,
        exam_id=normalized.exam_id,
        camera_id=normalized.camera_id,
        track_ids=json.dumps(normalized.track_ids),
        seat_ids=json.dumps(normalized.seat_ids),
        event_type=normalized.event_type,
        severity=normalized.severity,
        confidence=normalized.confidence,
        visibility_context=normalized.visibility_context,
        metadata_json=json.dumps(normalized.metadata)
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

class MockAISimulator:
    """
    Realistic Mock AI Data Simulator powering Part 4 standalone operation.
    Sends data through the EXACT same integration adapters used by real Part 1, 2, and 3 modules!
    """
    def __init__(self):
        self.is_running = False
        self.speed = 1.0
        self.current_stage = 0
        self.step_counter = 0
        self.loop_task: Optional[asyncio.Task] = None
        self.keypoint_task: Optional[asyncio.Task] = None

    def start(self):
        self.is_running = True
        try:
            loop = asyncio.get_running_loop()
            if self.loop_task is None or self.loop_task.done():
                self.loop_task = loop.create_task(self._auto_progression_loop())
            if self.keypoint_task is None or self.keypoint_task.done():
                self.keypoint_task = loop.create_task(self._live_keypoint_emitter_loop())
        except RuntimeError:
            pass

    def pause(self):
        self.is_running = False
        if self.loop_task and not self.loop_task.done():
            self.loop_task.cancel()
            self.loop_task = None
        if self.keypoint_task and not self.keypoint_task.done():
            self.keypoint_task.cancel()
            self.keypoint_task = None

    def reset(self):
        self.pause()
        self.current_stage = 0
        self.step_counter = 0

        # Reset integration service state/heartbeats
        IntegrationService.reset()

        # Database connection to clean and reset state
        db = SessionLocal()
        try:
            from sqlalchemy import text
            # Clear all simulated events, alerts, reviews, audit logs, group interactions, evidence, and tracks
            db.execute(text("DELETE FROM events"))
            db.execute(text("DELETE FROM alerts"))
            db.execute(text("DELETE FROM human_reviews"))
            db.execute(text("DELETE FROM audit_logs"))
            db.execute(text("DELETE FROM group_interactions"))
            db.execute(text("DELETE FROM evidences"))
            db.execute(text("DELETE FROM anonymous_tracks"))

            # Reset seating grid to initial state
            db.execute(text("UPDATE seats SET visibility_status = 'GOOD', visibility_score = 0.92"))
            db.execute(text("UPDATE seats SET visibility_status = 'POOR', visibility_score = 0.42 WHERE seat_label = 'B4'"))
            db.execute(text("UPDATE seats SET visibility_status = 'PARTIAL', visibility_score = 0.68 WHERE seat_label IN ('B3', 'C7', 'E12')"))
            db.execute(text("UPDATE seats SET visibility_status = 'BLIND_SPOT', visibility_score = 0.18 WHERE seat_label = 'D8'"))

            # Recreate basic anonymous tracks T17, T18, T19 as baseline
            db.execute(text("INSERT OR REPLACE INTO anonymous_tracks (id, exam_id, track_id, current_seat, first_seen, last_seen, active) VALUES "
                            "('TRK_T17', 'EXAM_001', 'T17', 'B4', datetime('now'), datetime('now'), 1), "
                            "('TRK_T18', 'EXAM_001', 'T18', 'B5', datetime('now'), datetime('now'), 1), "
                            "('TRK_T19', 'EXAM_001', 'T19', 'B6', datetime('now'), datetime('now'), 1)"))
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error resetting database in MockAISimulator: {e}")
        finally:
            db.close()

    def set_speed(self, speed: float):
        self.speed = max(0.2, min(speed, 10.0))

    async def _auto_progression_loop(self):
        """
        Automatically advances through stages 1 -> 7 at timed intervals when simulation is running.
        """
        try:
            if self.current_stage == 0:
                await self.trigger_stage(1)

            while self.is_running and self.current_stage < 7:
                await asyncio.sleep(4.0 / self.speed)
                if not self.is_running:
                    break
                next_stage = self.current_stage + 1
                await self.trigger_stage(next_stage)

            if self.current_stage >= 7 and self.is_running:
                self.is_running = False
                await manager.broadcast({"type": "SIMULATION_STATE", "status": "COMPLETED", "stage": 7})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in simulation auto progression loop: {e}")

    async def trigger_stage(self, stage: int):
        """Manually trigger a hackathon demo story stage (1 through 7)"""
        self.current_stage = stage
        db = SessionLocal()
        try:
            now_ts = time.time()
            if stage == 1:
                # Stage 1: Clean exam start
                event_p1 = Part1Adapter.adapt(Part1PerceptionInput(
                    timestamp=now_ts,
                    camera_id="CAM_01",
                    track_id="T17",
                    seat_id="B4",
                    head_direction="FORWARD",
                    yaw=0.04,
                    pitch=-0.02,
                    roll=0.01,
                    head_confidence=0.95,
                    hand_visibility=0.92,
                    body_visibility=0.95,
                    visibility_score=0.92
                ))
                # Also broadcast live perception event for T18, T19, etc.
                event_p1_t18 = Part1Adapter.adapt(Part1PerceptionInput(
                    timestamp=now_ts,
                    camera_id="CAM_01",
                    track_id="T18",
                    seat_id="B5",
                    head_direction="RIGHT",
                    yaw=0.45,
                    pitch=0.10,
                    roll=0.05,
                    head_confidence=0.92,
                    hand_visibility=0.85,
                    body_visibility=0.90,
                    visibility_score=0.88
                ))
                _save_event_to_db(db, event_p1)
                _save_event_to_db(db, event_p1_t18)
                IntegrationService.update_module_heartbeat("part1", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 1, "message": "Exam started. 120 students detected, 8 cameras online."})
                await manager.broadcast({"type": "PERCEPTION_EVENT", "data": event_p1.model_dump()})
                await manager.broadcast({"type": "PERCEPTION_EVENT", "data": event_p1_t18.model_dump()})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p1.model_dump()})

            elif stage == 2:
                # Stage 2: Head turning
                event_p2 = Part2Adapter.adapt(Part2BehaviourInput(
                    timestamp=now_ts,
                    track_id="T17",
                    seat_id="B4",
                    risk_score=34,
                    risk_level="LOW",
                    events=["NEIGHBOUR_GAZE"],
                    duration_sec=2.5,
                    confidence=0.89
                ))
                _save_event_to_db(db, event_p2)
                alert = AlertService.process_normalized_event(db, event_p2.model_dump())
                IntegrationService.update_module_heartbeat("part2", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 2, "message": "Head turning towards adjacent desk detected."})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p2.model_dump()})
                if alert:
                    await manager.broadcast({"type": "ALERT_UPDATE", "data": alert.id})

            elif stage == 3:
                # Stage 3: Repeated turning -> Medium risk
                event_p2 = Part2Adapter.adapt(Part2BehaviourInput(
                    timestamp=now_ts,
                    track_id="T17",
                    seat_id="B4",
                    risk_score=61,
                    risk_level="MEDIUM",
                    events=["NEIGHBOUR_GAZE", "HEAD_TURNING_RIGHT"],
                    duration_sec=5.2,
                    confidence=0.91
                ))
                _save_event_to_db(db, event_p2)
                alert = AlertService.process_normalized_event(db, event_p2.model_dump())
                IntegrationService.update_module_heartbeat("part2", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 3, "message": "Repeated head turning escalated to MEDIUM risk."})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p2.model_dump()})
                if alert:
                    await manager.broadcast({"type": "ALERT_UPDATE", "data": alert.id})

            elif stage == 4:
                # Stage 4: Torso rotation & unusual hand movement -> High risk alert
                event_p2 = Part2Adapter.adapt(Part2BehaviourInput(
                    timestamp=now_ts,
                    track_id="T17",
                    seat_id="B4",
                    risk_score=78,
                    risk_level="HIGH",
                    events=["NEIGHBOUR_GAZE", "TORSO_ROTATE", "UNUSUAL_HAND_MOVEMENT"],
                    duration_sec=8.4,
                    confidence=0.92
                ))
                _save_event_to_db(db, event_p2)
                alert = AlertService.process_normalized_event(db, event_p2.model_dump())
                IntegrationService.update_module_heartbeat("part2", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 4, "message": "Torso rotation & hand movement triggered HIGH risk alert."})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p2.model_dump()})
                if alert:
                    await manager.broadcast({"type": "ALERT_UPDATE", "data": alert.id})

            elif stage == 5:
                # Stage 5: Group correlation T17, T18, T19
                event_p2 = Part2Adapter.adapt(Part2BehaviourInput(
                    timestamp=now_ts,
                    track_id="T17",
                    seat_id="B4",
                    risk_score=84,
                    risk_level="HIGH",
                    events=["NEIGHBOUR_GAZE", "CORRELATED_MOVEMENT"],
                    duration_sec=9.0,
                    group_id="G3",
                    group_members=["T17", "T18", "T19"],
                    group_risk=84,
                    confidence=0.88
                ))
                _save_event_to_db(db, event_p2)
                alert = AlertService.process_normalized_event(db, event_p2.model_dump())
                IntegrationService.update_module_heartbeat("part2", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 5, "message": "Group intelligence cluster G3 formed across T17/T18/T19."})
                await manager.broadcast({"type": "GROUP_UPDATE", "group_id": "G3", "members": ["T17", "T18", "T19"], "risk": 84})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p2.model_dump()})
                if alert:
                    await manager.broadcast({"type": "ALERT_UPDATE", "data": alert.id})

            elif stage == 6:
                # Stage 6: Part 3 heavy second-pass verification arrives!
                event_p3 = Part3Adapter.adapt(Part3VerificationInput(
                    verification_id="V104",
                    alert_id="A104",
                    track_ids=["T17", "T18"],
                    window_start="10:42:18",
                    window_end="10:42:27",
                    verified_events=["REPEATED_NEIGHBOUR_GAZE", "OBJECT_INTERACTION"],
                    object_detected="PHONE",
                    verification_confidence=0.94,
                    live_risk=0.78,
                    verified_risk=0.91,
                    verification_status="CONFIRMED"
                ))
                _save_event_to_db(db, event_p3)
                alert = AlertService.update_with_part3_verification(db, {
                    "alert_id": None,
                    "track_ids": ["T17"],
                    "verification_status": "CONFIRMED",
                    "object_detected": "PHONE",
                    "verified_risk": 0.91,
                    "verification_confidence": 0.94
                })
                IntegrationService.update_module_heartbeat("part3", mode="SIMULATED")
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 6, "message": "Part 3 heavy verification confirmed PHONE contraband."})
                await manager.broadcast({"type": "EVENT_NEW", "data": event_p3.model_dump()})
                if alert:
                    await manager.broadcast({"type": "ALERT_VERIFIED", "data": alert.id, "object": "PHONE"})

            elif stage == 7:
                # Stage 7: Invigilator decision
                await manager.broadcast({"type": "STAGE_UPDATE", "stage": 7, "message": "Invigilator human review in progress."})

        finally:
            db.close()

    async def _live_keypoint_emitter_loop(self):
        """
        Continuously generates and broadcasts high-frequency pose updates (e.g., 2Hz / every 500ms)
        to animate the skeleton keypoints in real time.
        """
        import math
        import random
        from datetime import datetime
        
        t = 0.0
        while self.is_running:
            try:
                # Retrieve active alerts to fetch the exact current risk scores/priorities
                # so the Skeleton View is 100% synchronized with the central risk engine
                db = SessionLocal()
                active_alerts = {}
                try:
                    from app.models.alert import Alert
                    alerts = db.query(Alert).filter(Alert.status != "DISMISSED").all()
                    for alert in alerts:
                        active_alerts[alert.seat_id] = {
                            "risk_score": alert.risk_score,
                            "priority": alert.priority,
                            "status": alert.status
                        }
                except Exception as e:
                    print(f"Error querying active alerts in emitter loop: {e}")
                finally:
                    db.close()

                poses = {}
                rows = ["A", "B", "C", "D", "E", "F"]
                for r in rows:
                    for col in range(1, 21):
                        seat_label = f"{r}{col}"
                        track_id = f"T{col}"
                        if seat_label == "B4":
                            track_id = "T17"
                        elif seat_label == "B5":
                            track_id = "T18"
                        elif seat_label == "B6":
                            track_id = "T19"

                        # Check if there is an active alert for this seat
                        alert_info = active_alerts.get(seat_label)
                        risk_score = alert_info["risk_score"] if alert_info else 15
                        priority = alert_info["priority"] if alert_info else "LOW"
                        status = alert_info["status"] if alert_info else "NORMAL"

                        # Base values for normal behavior
                        yaw = 0.0
                        pitch = 0.0
                        roll = 0.0
                        left_hand_x = 0.0
                        left_hand_y = 0.0
                        right_hand_x = 0.0
                        right_hand_y = 0.0
                        torso_tilt = 0.0

                        # Calculate biological breathing micro-movements
                        # Standard breathing frequency: 0.25 Hz (once every 4 seconds)
                        breathing_offset = 0.8 * math.sin(2 * math.pi * 0.25 * t + hash(seat_label) % 10)

                        # Small micro-movements of hands and head (typing, shift)
                        seed_val = hash(seat_label) + int(t * 2)
                        random.seed(seed_val)
                        
                        # Add a tiny random shake to hands to simulate typing or writing
                        left_hand_x += random.uniform(-1.5, 1.5)
                        left_hand_y += random.uniform(-1.5, 1.5)
                        right_hand_x += random.uniform(-1.5, 1.5)
                        right_hand_y += random.uniform(-1.5, 1.5)

                        # Tiny head drift
                        yaw += random.uniform(-0.04, 0.04)
                        pitch += random.uniform(-0.02, 0.02)

                        # Handle Stage-specific active anomalies (T17 B4, T18 B5, T19 B6)
                        stage = self.current_stage
                        
                        if seat_label == "B4":  # T17
                            if stage == 1:
                                # Normal baseline
                                yaw += 0.05 * math.sin(t)
                            elif stage == 2:
                                # Start looking right towards B5 (NEIGHBOUR_GAZE)
                                target_yaw = 0.65
                                yaw = target_yaw + 0.1 * math.sin(t * 2.0)
                                pitch += 0.05 * math.cos(t)
                            elif stage == 3:
                                # Repeated gaze deviation (HEAD_TURNING_RIGHT)
                                target_yaw = 0.85
                                # Oscillate head gaze from center to B5
                                yaw = (target_yaw / 2.0) + (target_yaw / 2.0) * math.sin(t * 3.0)
                                left_hand_y += 3.0 * math.sin(t)
                            elif stage == 4:
                                # Torso rotate and unusual hand movement
                                yaw = 0.75 + 0.15 * math.sin(t * 4.0)
                                torso_tilt = 4.5 * math.sin(t * 2.0)
                                roll = 0.45 * math.cos(t * 2.0)
                                # Large hand gestures
                                left_hand_y -= 12.0 + 8.0 * math.sin(t * 5.0)
                                left_hand_x += 4.0 * math.cos(t * 5.0)
                            elif stage == 5:
                                # Correlated movement in group G3
                                yaw = 0.60 + 0.25 * math.sin(t * 3.0)
                                torso_tilt = 3.0 * math.sin(t * 3.0)
                                right_hand_y -= 8.0 + 4.0 * math.sin(t * 4.0)
                            elif stage == 6:
                                # Looking down at phone (contraband)
                                pitch = -0.75 + 0.08 * math.sin(t)
                                yaw = 0.15 * math.sin(t * 0.5)
                                # Raised hands together under desk holding a device
                                left_hand_x = 10.0 + 2.0 * math.sin(t)
                                left_hand_y = -10.0 + 2.0 * math.cos(t)
                                right_hand_x = -10.0 + 2.0 * math.cos(t)
                                right_hand_y = -10.0 + 2.0 * math.sin(t)
                            elif stage == 7:
                                # Confirmed / Under Review
                                yaw = 0.1 * math.sin(t)
                                pitch = 0.2 * math.cos(t)

                        elif seat_label == "B5":  # T18
                            if stage == 5:
                                # Correlated movement in G3 (looking left towards B4)
                                yaw = -0.55 + 0.25 * math.sin(t * 3.0 + 1.5)
                                torso_tilt = -3.0 * math.sin(t * 3.0 + 1.5)
                                left_hand_y -= 8.0 + 4.0 * math.sin(t * 4.0 + 1.5)
                            elif stage == 6:
                                # Also looking down / collaborating
                                pitch = -0.65 + 0.08 * math.sin(t + 1.0)
                                yaw = -0.45 + 0.15 * math.sin(t * 2.0)
                                left_hand_y = -6.0
                                right_hand_y = -6.0
                            elif stage == 7:
                                yaw = 0.1 * math.sin(t)

                        elif seat_label == "B6":  # T19
                            if stage == 5:
                                # Correlated movement in G3 (looking left towards B5)
                                yaw = -0.50 + 0.20 * math.sin(t * 3.0 + 3.0)
                                torso_tilt = -2.0 * math.sin(t * 3.0 + 3.0)
                            elif stage == 6:
                                yaw = -0.20 + 0.10 * math.sin(t)

                        poses[seat_label] = {
                            "track_id": track_id,
                            "seat_id": seat_label,
                            "yaw": float(yaw),
                            "pitch": float(pitch),
                            "roll": float(roll),
                            "left_hand_offset_x": float(left_hand_x),
                            "left_hand_offset_y": float(left_hand_y),
                            "right_hand_offset_x": float(right_hand_x),
                            "right_hand_offset_y": float(right_hand_y),
                            "breathing_offset": float(breathing_offset),
                            "torso_tilt": float(torso_tilt),
                            "risk_score": int(risk_score),
                            "priority": priority,
                            "status": status,
                            "last_updated": datetime.now().strftime("%H:%M:%S")
                        }

                # Broadcast current pose frame via WebSocket
                await manager.broadcast({
                    "type": "POSE_UPDATE",
                    "poses": poses
                })

                t += 0.5
                await asyncio.sleep(0.5 / self.speed)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in simulation live keypoint emitter: {e}")
                await asyncio.sleep(1.0)

simulator = MockAISimulator()
