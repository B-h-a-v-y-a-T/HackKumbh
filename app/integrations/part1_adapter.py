from datetime import datetime, timezone
from app.schemas.perception import Part1PerceptionInput
from app.schemas.event import NormalizedEvent

class Part1Adapter:
    """
    Integration Adapter for Part 1 - Live Perception Module.
    Converts raw vision perception metrics into a normalized internal platform event.
    """
    @staticmethod
    def adapt(input_data: Part1PerceptionInput) -> NormalizedEvent:
        import uuid
        event_id = f"EVT_P1_{int(input_data.timestamp * 1000)}_{uuid.uuid4().hex[:6]}"
        iso_time = datetime.fromtimestamp(input_data.timestamp, tz=timezone.utc).isoformat()
        
        # Determine primary event type based on head direction and hand status
        event_type = "PERCEPTION_UPDATE"
        if input_data.head_direction and input_data.head_direction.upper() in ["LEFT", "RIGHT"]:
            event_type = f"HEAD_TURNING_{input_data.head_direction.upper()}"
        elif input_data.hand_visibility < 0.3:
            event_type = "HANDS_HIDDEN"
        elif input_data.writing_state == "SUSPENDED":
            event_type = "WRITING_SUSPENDED"

        # Determine severity from visibility and occlusion
        severity = "LOW"
        if input_data.visibility_score < 0.50 or input_data.occlusion_score > 0.60:
            severity = "MEDIUM"

        return NormalizedEvent(
            event_id=event_id,
            source="PART_1",
            timestamp=iso_time,
            exam_id="EXAM_001",
            camera_id=input_data.camera_id,
            track_ids=[input_data.track_id],
            seat_ids=[input_data.seat_id] if input_data.seat_id else [],
            event_type=event_type,
            severity=severity,
            confidence=input_data.head_confidence,
            visibility_context=input_data.visibility_score,
            occlusion_score=input_data.occlusion_score,
            metadata={
                "head_direction": input_data.head_direction,
                "hand_visibility": input_data.hand_visibility,
                "body_visibility": input_data.body_visibility,
                "occlusion_score": input_data.occlusion_score,
                "writing_state": input_data.writing_state,
                "bbox": input_data.bbox,
                "keypoints": input_data.keypoints,
                "yaw": input_data.yaw,
                "pitch": input_data.pitch,
                "roll": input_data.roll
            }
        )
