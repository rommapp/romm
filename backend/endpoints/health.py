from fastapi import Response, status

from endpoints.responses.health import HealthReadyResponse
from handler.health_handler import is_ready
from utils.router import APIRouter

router = APIRouter(prefix="/health", tags=["system"])


@router.get(
    "/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReadyResponse}},
)
async def ready(response: Response) -> HealthReadyResponse:
    ready = is_ready()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": ready}
