from fastapi import APIRouter
from app.core.resource import get_hardware_metrics
from app.models.entities import HardwareMetrics

router = APIRouter()

@router.get("/resources", response_model=HardwareMetrics)
async def read_resources():
    return get_hardware_metrics()
