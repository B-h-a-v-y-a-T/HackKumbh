from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.perception import Part1PerceptionInput
from app.schemas.behaviour import Part2BehaviourInput
from app.schemas.verification import Part3VerificationInput
from app.schemas.event import NormalizedEvent
from app.integrations.part1_adapter import Part1Adapter
from app.integrations.part2_adapter import Part2Adapter
from app.integrations.part3_adapter import Part3Adapter
from app.services.alert_service import AlertService
from app.services.integration_service import IntegrationService
from app.integrations.mock_simulator import simulator
from app.core.websocket_manager import manager
from app.models.event import Event
import json

router = APIRouter(prefix="/integration", tags=["AI Module Integration"])

@router.post("/part1/perception", response_model=NormalizedEvent)
async def ingest_part1_perception(payload: Part1PerceptionInput, db: Session = Depends(get_db)):
    """
    Ingest live perception payload from Part 1 module.
    Converts via Part1Adapter -> NormalizedEvent -> DB -> Alert Service -> WebSocket broadcast.
    """
    try:
        normalized = Part1Adapter.adapt(payload)
        IntegrationService.update_module_heartbeat("part1", mode="LIVE")
        
        # Save event to DB
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

        # Check alert generation
        alert = AlertService.process_normalized_event(db, normalized.model_dump())
        
        # Broadcast real-time WebSocket update
        await manager.broadcast({
            "type": "PERCEPTION_EVENT",
            "event": normalized.model_dump(),
            "alert_updated": alert.id if alert else None
        })

        return normalized
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Part 1 Perception payload: {str(e)}")


@router.post("/part2/behaviour", response_model=NormalizedEvent)
async def ingest_part2_behaviour(payload: Part2BehaviourInput, db: Session = Depends(get_db)):
    """
    Ingest behavioural and spatial intelligence payload from Part 2 module.
    Converts via Part2Adapter -> NormalizedEvent -> DB -> Alert Service -> WebSocket broadcast.
    """
    try:
        normalized = Part2Adapter.adapt(payload)
        IntegrationService.update_module_heartbeat("part2", mode="LIVE")

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

        alert = AlertService.process_normalized_event(db, normalized.model_dump())

        await manager.broadcast({
            "type": "BEHAVIOUR_EVENT",
            "event": normalized.model_dump(),
            "alert_updated": alert.id if alert else None
        })

        return normalized
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Part 2 Behaviour payload: {str(e)}")


@router.post("/part3/verification", response_model=NormalizedEvent)
async def ingest_part3_verification(payload: Part3VerificationInput, db: Session = Depends(get_db)):
    """
    Ingest heavy second-pass contraband/verification payload from Part 3 module.
    Converts via Part3Adapter -> NormalizedEvent -> Updates live Alert state -> WebSocket broadcast.
    """
    try:
        normalized = Part3Adapter.adapt(payload)
        IntegrationService.update_module_heartbeat("part3", mode="LIVE")

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

        # Update existing alert with second-pass verifier findings
        alert = AlertService.update_with_part3_verification(db, payload.model_dump())

        await manager.broadcast({
            "type": "VERIFICATION_EVENT",
            "event": normalized.model_dump(),
            "alert_updated": alert.id if alert else None,
            "verification_status": payload.verification_status
        })

        return normalized
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Invalid Part 3 Verification payload: {str(e)}")


# Simulator controls
sim_router = APIRouter(prefix="/simulation", tags=["Mock AI Simulator Controls"])

@sim_router.post("/start")
async def start_simulation():
    simulator.start()
    await manager.broadcast({"type": "SIMULATION_STATE", "status": "RUNNING"})
    return {"status": "started"}

@sim_router.post("/pause")
async def pause_simulation():
    simulator.pause()
    await manager.broadcast({"type": "SIMULATION_STATE", "status": "PAUSED"})
    return {"status": "paused"}

@sim_router.post("/reset")
async def reset_simulation():
    simulator.reset()
    await manager.broadcast({"type": "SIMULATION_STATE", "status": "RESET"})
    return {"status": "reset"}

@sim_router.post("/trigger-stage/{stage}")
async def trigger_demo_stage(stage: int):
    if stage < 1 or stage > 7:
        raise HTTPException(status_code=400, detail="Stage must be between 1 and 7.")
    await simulator.trigger_stage(stage)
    return {"status": "triggered", "stage": stage}
