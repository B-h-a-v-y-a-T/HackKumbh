"""
CopyCop — FastAPI Application Entry Point.

Lifespan handler initializes database, model registry, and background workers.
All models are loaded once and cached in the registry.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models.base import ModelRegistry
from app.storage import database as db
from app.workers import verification_worker

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _register_models(settings) -> None:
    """Register all models in the registry based on settings."""
    registry = ModelRegistry.get_instance()
    registry.set_device(settings.model_device)

    # Register Roboflow Phone Detector as primary live object detector
    try:
        from app.object_detection.roboflow_phone_detector import RoboflowPhoneDetector
        roboflow_detector = RoboflowPhoneDetector(
            model_id=getattr(settings, "roboflow_model_id", "phone-detection-3d9gh/1"),
            api_key=getattr(settings, "roboflow_api_key", None),
            confidence_threshold=getattr(settings, "roboflow_phone_confidence", 0.45),
            iou_threshold=getattr(settings, "roboflow_iou_threshold", 0.45),
            confirmation_frames=getattr(settings, "phone_confirmation_frames", 3),
        )
        registry.register_detector("live", roboflow_detector)
        logger.info("Registered Roboflow Phone Detector as primary live object detector")
    except Exception as ex:
        logger.warning("Could not instantiate RoboflowPhoneDetector: %s", ex)
        if settings.mock_mode:
            from app.models.yolo_detector import MockYOLO26SDetector
            registry.register_detector("live", MockYOLO26SDetector())
        else:
            from app.models.yolo_detector import YOLO26SDetector
            registry.register_detector("live", YOLO26SDetector(settings.yolo_custom_weights))

    if settings.mock_mode:
        from app.models.videomae_verifier import MockVideoMAEV2Verifier
        from app.models.rtdetr_verifier import MockRTDETRVerifier
        from app.models.vitpose_verifier import MockViTPoseVerifier

        registry.register_temporal_verifier("videomae", MockVideoMAEV2Verifier())
        registry.register_high_accuracy_detector("rtdetr", MockRTDETRVerifier())
        registry.register_pose_verifier("vitpose", MockViTPoseVerifier())
        logger.info("Registered MOCK verification models")
    else:
        from app.models.videomae_verifier import VideoMAEV2Verifier
        from app.models.rtdetr_verifier import RTDETRVerifier
        from app.models.vitpose_verifier import ViTPoseVerifier

        registry.register_temporal_verifier("videomae", VideoMAEV2Verifier(settings.videomae_model))
        registry.register_high_accuracy_detector("rtdetr", RTDETRVerifier(settings.rtdetr_weights))
        registry.register_pose_verifier("vitpose", ViTPoseVerifier(settings.vitpose_model))
        logger.info("Registered REAL verification models")

    # Load all models
    registry.load_all(settings.model_device)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    _setup_logging(settings.log_level)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Mock mode: {settings.mock_mode}")

    # Initialize database
    await db.init_database(settings.database_path)
    try:
        from app.database.session import engine, Base
        import app.models.alert, app.models.event, app.models.seat, app.models.review, app.models.group
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning("SQLAlchemy Base tables init note: %s", e)

    # Register and load models for Part 3
    _register_models(settings)

    # Start background verification worker (Part 3)
    try:
        await verification_worker.start_worker()
    except Exception as e:
        logger.warning("Verification worker note: %s", e)

    # Start high-throughput AsyncPipelineWorker (Parts 1, 2, 4)
    from app.pipeline.worker import AsyncPipelineWorker, set_worker
    worker = AsyncPipelineWorker(mock_mode=settings.mock_mode)
    set_worker(worker)
    worker.start()
    logger.info("AsyncPipelineWorker initialized and running")

    logger.info(f"{settings.app_name} ready on {settings.host}:{settings.port}")
    yield

    # Shutdown
    logger.info("Shutting down...")
    from app.pipeline.worker import get_worker
    worker = get_worker()
    if worker:
        worker.stop()
    try:
        await verification_worker.stop_worker()
    except Exception:
        pass
    await db.close_database()
    ModelRegistry.reset()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Privacy-first AI video analytics for examination monitoring. "
            "Produces structured evidence for human review. "
            "Never produces automatic cheating verdicts."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static media directory for examination recordings
    media_dir = Path("media")
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    # Register bhavya2 branch routers
    from app.api.health import router as health_router
    from app.api.roi import router as roi_router
    from app.api.verification import router as verification_router
    from app.api.evidence import router as evidence_router
    from app.api.metrics import router as metrics_router
    from app.api.live import router as live_router
    from app.api.invigilator import router as invigilator_router
    from app.api.websocket import router as ws_router
    from app.api.video_analysis import router as video_analysis_router
    from app.api.reports import router as reports_router

    app.include_router(live_router, prefix="/api/v1")
    app.include_router(live_router, prefix="/api")
    app.include_router(video_analysis_router, prefix="/api/v1")
    app.include_router(video_analysis_router, prefix="/api")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api")
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(roi_router)
    app.include_router(roi_router, prefix="/api")
    app.include_router(verification_router)
    app.include_router(verification_router, prefix="/api")
    app.include_router(evidence_router)
    app.include_router(evidence_router, prefix="/api")
    app.include_router(metrics_router)
    app.include_router(metrics_router, prefix="/api")
    app.include_router(invigilator_router)
    app.include_router(invigilator_router, prefix="/api")
    app.include_router(ws_router)                            # /ws/live

    # Mount overview / dashboard platform routers if present
    try:
        from app.api import alerts, events, exams, coverage, groups, privacy, timeline, system, integration
        for pfx in ["/api", "/api/v1"]:
            app.include_router(alerts.router, prefix=pfx)
            app.include_router(events.router, prefix=pfx)
            app.include_router(exams.router, prefix=pfx)
            app.include_router(coverage.router, prefix=pfx)
            app.include_router(groups.router, prefix=pfx)
            app.include_router(privacy.router, prefix=pfx)
            app.include_router(timeline.router, prefix=pfx)
            app.include_router(system.router, prefix=pfx)
            app.include_router(integration.router, prefix=pfx)
            app.include_router(integration.sim_router, prefix=pfx)
    except Exception as e:
        logger.debug("Additional platform routers note: %s", e)

    # Static assets and dashboard
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(str(static_dir / "index.html"))

    dashboard_file = Path(__file__).resolve().parent.parent / "dashboard.html"
    if dashboard_file.exists():
        @app.get("/dashboard", include_in_schema=False)
        async def serve_dashboard():
            return FileResponse(str(dashboard_file))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
