from datetime import datetime, timezone
from app.schemas.behaviour import Part2BehaviourInput
from app.schemas.event import NormalizedEvent

class Part2Adapter:
    """
    Integration Adapter for Part 2 - Behavioural and Spatial Intelligence Module.
    Converts temporal risk & behavioural signals into a normalized internal platform event.
    """
    @staticmethod
    def adapt(input_data: Part2BehaviourInput) -> NormalizedEvent:
        import uuid
        event_id = f"EVT_P2_{int(input_data.timestamp * 1000)}_{uuid.uuid4().hex[:6]}"
        iso_time = datetime.fromtimestamp(input_data.timestamp, tz=timezone.utc).isoformat()
        
        # Primary event string
        primary_event = input_data.events[0] if input_data.events else "UNUSUAL_BEHAVIOUR"
        
        # Map risk score to severity
        severity = "LOW"
        if input_data.risk_score >= 85 or input_data.risk_level.upper() == "CRITICAL":
            severity = "CRITICAL"
        elif input_data.risk_score >= 70 or input_data.risk_level.upper() == "HIGH":
            severity = "HIGH"
        elif input_data.risk_score >= 40 or input_data.risk_level.upper() == "MEDIUM":
            severity = "MEDIUM"

        track_ids = [input_data.track_id]
        if input_data.group_members:
            for member in input_data.group_members:
                if member not in track_ids:
                    track_ids.append(member)

        return NormalizedEvent(
            event_id=event_id,
            source="PART_2",
            timestamp=iso_time,
            exam_id="EXAM_001",
            camera_id="CAM_01", # Default or infer from seat
            track_ids=track_ids,
            seat_ids=[input_data.seat_id] if input_data.seat_id else [],
            event_type=primary_event,
            severity=severity,
            confidence=input_data.confidence,
            risk_score=float(input_data.risk_score),
            duration_sec=input_data.duration_sec,
            group_id=input_data.group_id,
            group_members=input_data.group_members or [],
            visibility_context=0.90,
            metadata={
                "all_events": input_data.events,
                "risk_score": input_data.risk_score,
                "risk_level": input_data.risk_level,
                "duration_sec": input_data.duration_sec,
                "baseline_deviation": input_data.baseline_deviation,
                "group_id": input_data.group_id,
                "group_risk": input_data.group_risk,
                "group_members": input_data.group_members or []
            }
        )
