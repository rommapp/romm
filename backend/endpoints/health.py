from fastapi import Response, status

from endpoints.responses.health import HealthReadyResponse
from handler.health_handler import ready_checks
from utils.router import APIRouter

router = APIRouter(prefix="/health", tags=["system"])


@router.get(
    "/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReadyResponse}},
)
def ready(response: Response) -> HealthReadyResponse:
    checks = ready_checks()
    if not all(
        check["ok"]
        for check in (
            checks["database"],
            checks["valkey"],
            checks["worker"],
            checks["migration"],
            checks["library"],
            checks["resources"],
        )
    ):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks
