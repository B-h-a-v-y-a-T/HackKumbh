import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.event import Event
from app.models.review import HumanReview
from app.models.group import GroupInteraction
from app.services.explainability_service import ExplainabilityService
from app.services.risk_service import RiskService

class AlertService:
    @staticmethod
    def process_normalized_event(db: Session, event_data: Dict[str, Any]) -> Optional[Alert]:
        """
        Receives a normalized event dict, updates existing alert or creates a new alert.
        """
        track_ids = event_data.get("track_ids", [])
        seat_ids = event_data.get("seat_ids", [])
        if not track_ids:
            return None

        primary_track = track_ids[0]
        primary_seat = seat_ids[0] if seat_ids else "Unassigned"
        event_type = event_data.get("event_type", "UNKNOWN")
        source = event_data.get("source", "UNKNOWN")
        metadata = event_data.get("metadata", {})
        visibility = event_data.get("visibility_context", 0.90)
        confidence = event_data.get("confidence", 0.85)

        # Handle group interaction tracking
        group_id = event_data.get("group_id") or metadata.get("group_id")
        group_members = event_data.get("group_members") or metadata.get("group_members", [])
        if group_id and group_members:
            existing_grp = db.query(GroupInteraction).filter(GroupInteraction.group_id == group_id).first()
            now_dt = datetime.now(timezone.utc)
            if not existing_grp:
                grp_risk = metadata.get("group_risk", event_data.get("risk_score", 84))
                new_grp = GroupInteraction(
                    id=f"GRP_{int(now_dt.timestamp() * 1000)}",
                    group_id=group_id,
                    exam_id=event_data.get("exam_id", "EXAM_001"),
                    member_tracks=json.dumps(group_members),
                    group_risk=int(grp_risk or 84),
                    pattern_description=f"Correlated temporal behavioural pattern across tracks {', '.join(group_members)}.",
                    window_start=now_dt,
                    window_end=now_dt
                )
                db.add(new_grp)
                db.commit()

        # Look up active existing alert for this track
        existing_alert = db.query(Alert).filter(
            Alert.track_id == primary_track,
            Alert.exam_id == event_data.get("exam_id", "EXAM_001"),
            Alert.status == "ACTIVE"
        ).order_by(Alert.updated_at.desc()).first()

        risk_score = metadata.get("risk_score", 45) if source == "PART_2" else (85 if "CONTRABAND" in event_type or "PHONE" in event_type else 35)
        if event_data.get("risk_score") is not None:
            risk_score = int(event_data["risk_score"])
        duration_sec = event_data.get("duration_sec") or metadata.get("duration_sec", 4.0)

        if existing_alert:
            # Update existing alert
            behaviours = json.loads(existing_alert.observed_behaviours) if existing_alert.observed_behaviours else []
            if event_type not in behaviours:
                behaviours.append(event_type)
            
            existing_alert.observed_behaviours = json.dumps(behaviours)
            existing_alert.risk_score = max(existing_alert.risk_score, int(risk_score))
            existing_alert.peak_risk = max(existing_alert.peak_risk, existing_alert.risk_score)
            existing_alert.duration_sec += float(duration_sec)
            existing_alert.confidence = round((existing_alert.confidence + confidence) / 2.0, 2)
            existing_alert.low_visibility_flag = (visibility < 0.50)
            if group_id:
                existing_alert.group_id = group_id
            
            # Recompute priority
            existing_alert.priority = RiskService.calculate_priority(
                existing_alert.risk_score, existing_alert.confidence, visibility
            )

            # Recompute explainability
            explain_dict = ExplainabilityService.generate_explanation(
                track_id=primary_track,
                seat_id=primary_seat,
                risk_score=existing_alert.risk_score,
                observed_behaviours=behaviours,
                duration_sec=existing_alert.duration_sec,
                visibility_score=visibility,
                confidence=existing_alert.confidence,
                group_id=existing_alert.group_id,
                group_members=group_members,
                object_detected=existing_alert.object_detected,
                verification_status=existing_alert.verification_status
            )
            existing_alert.explainability_json = json.dumps(explain_dict)
            existing_alert.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_alert)
            return existing_alert

        else:
            # Create new alert if risk > 30 or severity != LOW
            if risk_score < 30 and event_data.get("severity") == "LOW":
                return None

            import uuid
            now_dt = datetime.now(timezone.utc)
            alert_id = f"ALT_{int(now_dt.timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
            behaviours = [event_type]
            priority = RiskService.calculate_priority(int(risk_score), confidence, visibility)
            
            explain_dict = ExplainabilityService.generate_explanation(
                track_id=primary_track,
                seat_id=primary_seat,
                risk_score=int(risk_score),
                observed_behaviours=behaviours,
                duration_sec=float(duration_sec),
                visibility_score=visibility,
                confidence=confidence,
                group_id=group_id,
                group_members=group_members,
                object_detected=None,
                verification_status="LIVE_DETECTION"
            )

            new_alert = Alert(
                id=alert_id,
                exam_id=event_data.get("exam_id", "EXAM_001"),
                track_id=primary_track,
                seat_id=primary_seat,
                risk_score=int(risk_score),
                peak_risk=int(risk_score),
                priority=priority,
                status="ACTIVE",
                confidence=confidence,
                observed_behaviours=json.dumps(behaviours),
                duration_sec=float(duration_sec),
                low_visibility_flag=(visibility < 0.50),
                verification_status="LIVE_DETECTION",
                group_id=group_id,
                object_detected=None,
                explainability_json=json.dumps(explain_dict),
                created_at=now_dt,
                updated_at=now_dt
            )
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)
            return new_alert

    @staticmethod
    def update_with_part3_verification(db: Session, verification_data: Dict[str, Any]) -> Optional[Alert]:
        """
        Updates existing alert with Part 3 heavy second-pass verification output.
        """
        alert_id = verification_data.get("alert_id")
        alert = db.query(Alert).filter(Alert.id == alert_id).first() if alert_id else None
        
        if not alert and verification_data.get("track_ids"):
            track_id = verification_data["track_ids"][0]
            alert = db.query(Alert).filter(Alert.track_id == track_id).order_by(Alert.updated_at.desc()).first()

        if not alert:
            return None

        status_str = verification_data.get("verification_status", "CONFIRMED").upper()
        object_det = verification_data.get("object_detected", "NONE")
        v_risk = verification_data.get("verified_risk", 0.80)
        verified_risk = int(v_risk * 100 if v_risk <= 1.0 else v_risk)
        v_conf = verification_data.get("verification_confidence", 0.90)

        if status_str == "CONFIRMED":
            alert.verification_status = "SECOND_PASS_CONFIRMED"
            alert.risk_score = max(alert.risk_score, verified_risk)
            alert.peak_risk = max(alert.peak_risk, alert.risk_score)
            alert.object_detected = object_det
            alert.confidence = round((alert.confidence + v_conf) / 2.0, 2)
            alert.priority = RiskService.calculate_priority(alert.risk_score, alert.confidence, 0.90)
        elif status_str == "DISPROVED":
            alert.verification_status = "SECOND_PASS_DISPROVED"
            alert.risk_score = min(alert.risk_score, 25)
            alert.priority = "LOW"

        behaviours = json.loads(alert.observed_behaviours) if alert.observed_behaviours else []
        explain_dict = ExplainabilityService.generate_explanation(
            track_id=alert.track_id,
            seat_id=alert.seat_id or "Unassigned",
            risk_score=alert.risk_score,
            observed_behaviours=behaviours,
            duration_sec=alert.duration_sec,
            visibility_score=0.90,
            confidence=alert.confidence,
            group_id=alert.group_id,
            object_detected=alert.object_detected,
            verification_status=alert.verification_status
        )
        alert.explainability_json = json.dumps(explain_dict)
        alert.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(alert)
        return alert
