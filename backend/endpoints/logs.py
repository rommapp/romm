from fastapi import Request

from decorators.auth import protected_route
from endpoints.responses.log import LogEntrySchema
from endpoints.sockets.logs import get_recent_logs
from handler.auth.constants import Scope
from logger.log_stream_handler import LOG_BUFFER_SIZE
from utils.router import APIRouter

router = APIRouter(
    prefix="/logs",
    tags=["logs"],
)

# Largest backfill the buffer holds — derived from the producer's ring buffer
# so the two never drift.
MAX_LOG_LIMIT = LOG_BUFFER_SIZE


@protected_route(router.get, "", [Scope.USERS_WRITE])
async def get_logs(
    request: Request, limit: int = MAX_LOG_LIMIT
) -> list[LogEntrySchema]:
    """Return the most recent backend log lines for backfill (admin only).

    Args:
        request (Request): FastAPI Request object.
        limit (int): Maximum number of recent lines to return.

    Returns:
        list[LogEntrySchema]: Recent log lines, oldest-first.
    """
    bounded = max(1, min(limit, MAX_LOG_LIMIT))
    entries = await get_recent_logs(bounded)
    return [LogEntrySchema(**entry) for entry in entries]
