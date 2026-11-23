from fastapi import Response, status

from endpoints.responses.health import HealthReadyResponse
from handler.health_handler import is_ready
from utils.router import APIRouter

router = APIRouter(prefix="/health", tags=["system"])


@router.get(
    "/ready",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthReadyResponse,
            "description": "This process is still starting up or is shutting down.",
        }
    },
)
async def ready(response: Response) -> HealthReadyResponse:
    """Report whether this API process is ready to serve requests."""
    serving = is_ready()
    if not serving:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": serving}
