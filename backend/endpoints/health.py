import os

from fastapi import APIRouter, Response, status
from redis.exceptions import RedisError
from rq import Worker
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import LIBRARY_BASE_PATH, RESOURCES_BASE_PATH
from endpoints.responses.health import HealthLiveResponse, HealthReadyResponse
from handler.database.base_handler import sync_engine
from handler.redis_handler import redis_client

router = APIRouter(prefix="/health", tags=["system"])


@router.get("/live")
def live() -> HealthLiveResponse:
    return {"status": "ok"}


@router.get(
    "/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReadyResponse}},
)
def ready(response: Response) -> HealthReadyResponse:
    checks: HealthReadyResponse = {
        "database": _database_answers(),
        "valkey": _valkey_answers(),
        "worker": _worker_registered(),
        "library": os.access(LIBRARY_BASE_PATH, os.R_OK),
        "resources": os.access(RESOURCES_BASE_PATH, os.W_OK),
    }
    if not all(checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks


def _database_answers() -> bool:
    try:
        with sync_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


def _valkey_answers() -> bool:
    try:
        return bool(redis_client.ping())
    except RedisError:
        return False


def _worker_registered() -> bool:
    try:
        return len(Worker.all(connection=redis_client)) > 0
    except RedisError:
        return False
