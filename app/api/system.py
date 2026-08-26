from fastapi import APIRouter
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/system", tags=["System Health & Status"])

@router.get("/status")
def get_system_status():
    return IntegrationService.get_system_status()
