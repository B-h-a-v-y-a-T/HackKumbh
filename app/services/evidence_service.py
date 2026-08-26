import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.event import Event
from app.models.review import HumanReview

class EvidenceService:
    @staticmethod
    def get_alert_evidence_package(db: Session, alert_id: str) -> Dict[str, Any]:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return {"error": f"Alert {alert_id} not found"}

        # Gather relevant events for this track
        events = db.query(Event).filter(
            Event.track_ids.like(f"%{alert.track_id}%")
        ).order_by(Event.timestamp.asc()).all()

        timeline = []
        part1_observations = []
        part2_findings = []
        part3_result = None

        for evt in events:
            meta = json.loads(evt.metadata_json) if evt.metadata_json else {}
            timeline.append({
                "id": evt.id,
                "timestamp": evt.timestamp.isoformat(),
                "event_type": evt.event_type,
                "source": evt.source,
                "severity": evt.severity,
                "confidence": evt.confidence,
                "details": meta
            })

            # Categorize by source for deep inspection
            if evt.source == "PART_1":
                head_dir = meta.get("head_direction", "UNKNOWN")
                hand_vis = meta.get("hand_visibility", 1.0)
                writing = meta.get("writing_state", "ACTIVE")
                part1_observations.append(
                    f"Camera {evt.camera_id}: Head direction {head_dir} (conf: {int(evt.confidence*100)}%), "
                    f"Hand visibility {int(hand_vis*100)}%, Writing state: {writing}."
                )
            elif evt.source == "PART_2":
                all_evts = meta.get("all_events") or [evt.event_type]
                duration = meta.get("duration_sec", 0.0)
                risk_val = meta.get("risk_score", 0)
                part2_findings.append(
                    f"Temporal risk score {int(risk_val)} ({evt.severity}). "
                    f"Flagged events: {', '.join(all_evts)} over {duration}s."
                )
            elif evt.source == "PART_3":
                part3_result = {
                    "verification_id": meta.get("verification_id", evt.id),
                    "object_detected": meta.get("object_detected", alert.object_detected or "NONE"),
                    "verification_confidence": evt.confidence,
                    "verified_risk": meta.get("verified_risk", 0.0),
                    "verification_status": meta.get("verification_status", "UNKNOWN"),
                    "verified_events": meta.get("verified_events", [])
                }

        # Check latest human review status
        latest_review = None
        rev = db.query(HumanReview).filter(HumanReview.alert_id == alert.id).order_by(HumanReview.reviewed_at.desc()).first()
        if rev:
            latest_review = {
                "id": rev.id,
                "decision": rev.decision,
                "notes": rev.notes,
                "reviewer_id": rev.reviewer_id,
                "reviewed_at": rev.reviewed_at.isoformat()
            }

        explainability = json.loads(alert.explainability_json) if alert.explainability_json else {}
        observed_behaviours = json.loads(alert.observed_behaviours) if alert.observed_behaviours else []

        return {
            "alert_id": alert.id,
            "exam_id": alert.exam_id,
            "track_id": alert.track_id,
            "seat_id": alert.seat_id,
            "risk_score": alert.risk_score,
            "peak_risk": alert.peak_risk,
            "priority": alert.priority,
            "status": alert.status,
            "confidence": alert.confidence,
            "verification_status": alert.verification_status,
            "object_detected": alert.object_detected,
            "low_visibility_flag": alert.low_visibility_flag,
            "created_at": alert.created_at.isoformat(),
            "observed_behaviours": observed_behaviours,
            "explainability": explainability,
            "timeline": timeline,
            "part1_observations": part1_observations,
            "part2_findings": part2_findings,
            "part3_result": part3_result,
            "latest_review": latest_review,
            "media_evidence": {
                "skeleton_replay_available": len(part1_observations) > 0,
                "roi_crop_available": alert.object_detected is not None,
                "video_snippet_available": len(part2_findings) > 0,
                "status_note": "ROI skeleton overlay frames render active. Verification confidence: " + str(int(alert.confidence*100)) + "%."
            }
        }

