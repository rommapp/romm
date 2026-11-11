from fastapi import Request, Response, status
from fastapi.responses import PlainTextResponse

from config import ROMM_METRICS_ENABLED
from decorators.auth import protected_route
from endpoints.responses.health import (
    HealthLiveResponse,
    HealthReadyResponse,
    HealthStatusResponse,
)
from handler.auth.constants import Scope
from handler.health_handler import metrics_text, ready_checks, status_report
from utils.router import APIRouter

router = APIRouter(prefix="/health", tags=["system"])


@router.get("/live")
def live() -> HealthLiveResponse:
    return {"status": "ok"}


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


@protected_route(router.get, "/status", [Scope.LOGS_READ])
def health_status(request: Request) -> HealthStatusResponse:
    return status_report()


if ROMM_METRICS_ENABLED:

    @protected_route(
        router.get,
        "/metrics",
        [Scope.LOGS_READ],
        response_class=PlainTextResponse,
    )
    def metrics(request: Request) -> str:
        return metrics_text()
