from datetime import datetime, timezone
from app.schemas.verification import Part3VerificationInput
from app.schemas.event import NormalizedEvent

class Part3Adapter:
    """
    Integration Adapter for Part 3 - Contraband and Heavy Verification Module.
    Converts heavy ROI second-pass verification results into normalized events and alert updates.
    """
    @staticmethod
    def adapt(input_data: Part3VerificationInput) -> NormalizedEvent:
        now_str = datetime.now(tz=timezone.utc).isoformat()
        
        event_type = "SECOND_PASS_VERIFIED"
        if input_data.object_detected and input_data.object_detected.upper() != "NONE":
            event_type = f"CONTRABAND_VERIFIED_{input_data.object_detected.upper()}"
        elif input_data.verification_status.upper() == "DISPROVED":
            event_type = "ALERT_DISPROVED_BY_VERIFIER"

        severity = "HIGH"
        if input_data.verified_risk >= 80 or input_data.object_detected in ["PHONE", "CHIT"]:
            severity = "CRITICAL"
        elif input_data.verification_status.upper() == "DISPROVED":
            severity = "LOW"

        now_ts = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        return NormalizedEvent(
            event_id=f"EVT_P3_{input_data.verification_id}_{now_ts}",
            source="PART_3",
            timestamp=now_str,
            exam_id="EXAM_001",
            camera_id="CAM_02",
            track_ids=input_data.track_ids,
            seat_ids=[],
            event_type=event_type,
            severity=severity,
            confidence=input_data.verification_confidence,
            risk_score=float(input_data.verified_risk * 100 if input_data.verified_risk <= 1.0 else input_data.verified_risk),
            evidence_references=[f"roi_crop_{input_data.verification_id}.jpg"],
            visibility_context=0.95,
            metadata={
                "verification_id": input_data.verification_id,
                "alert_id": input_data.alert_id,
                "window_start": input_data.window_start,
                "window_end": input_data.window_end,
                "verified_events": input_data.verified_events,
                "object_detected": input_data.object_detected,
                "live_risk": input_data.live_risk,
                "verified_risk": input_data.verified_risk,
                "verification_status": input_data.verification_status
            }
        )
