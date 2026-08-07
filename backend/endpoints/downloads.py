from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Query, Request

from decorators.auth import protected_route
from endpoints.responses.downloads import DownloadLogPage, DownloadStatsOverview
from handler.auth.constants import Scope
from handler.database import db_download_handler
from models.download_event import DownloadSource
from utils.router import APIRouter

router = APIRouter(
    prefix="/stats/downloads",
    tags=["downloads"],
)

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365


def _window_start(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# Every route here is admin-gated: the log carries usernames, IPs and user
# agents, which no non-admin should be able to read.


@protected_route(router.get, "", [Scope.USERS_READ])
def get_download_overview(
    request: Request,
    days: Annotated[
        int,
        Query(
            description="Size of the trailing window used for the timeline and windowed totals.",
            ge=1,
            le=MAX_WINDOW_DAYS,
        ),
    ] = DEFAULT_WINDOW_DAYS,
    top_limit: Annotated[
        int,
        Query(
            description="How many entries to return in the top-roms list.",
            ge=1,
            le=100,
        ),
    ] = 10,
) -> DownloadStatsOverview:
    """Aggregate download statistics for the admin center (admin only)."""
    since = _window_start(days)

    return DownloadStatsOverview(
        summary=db_download_handler.get_summary(since=since),
        top_roms=db_download_handler.get_top_roms(limit=top_limit),
        by_platform=db_download_handler.get_downloads_by_platform(),
        by_source=db_download_handler.get_downloads_by_source(),
        timeline=db_download_handler.get_timeline(days=days),
    )


@protected_route(router.get, "/log", [Scope.USERS_READ])
def get_download_log(
    request: Request,
    limit: Annotated[int, Query(description="Page size.", ge=1, le=200)] = 50,
    offset: Annotated[int, Query(description="Rows to skip.", ge=0)] = 0,
    rom_id: Annotated[
        int | None, Query(description="Only downloads of this rom.", ge=1)
    ] = None,
    user_id: Annotated[
        int | None, Query(description="Only downloads by this user.", ge=1)
    ] = None,
    platform_id: Annotated[
        int | None, Query(description="Only downloads from this platform.", ge=1)
    ] = None,
    source: Annotated[
        DownloadSource | None, Query(description="Only downloads from this source.")
    ] = None,
    days: Annotated[
        int | None,
        Query(
            description="Only downloads from the last N days.",
            ge=1,
            le=MAX_WINDOW_DAYS,
        ),
    ] = None,
) -> DownloadLogPage:
    """Paginated per-download log, newest first (admin only)."""
    return db_download_handler.get_download_log(
        limit=limit,
        offset=offset,
        rom_id=rom_id,
        user_id=user_id,
        platform_id=platform_id,
        source=source,
        since=_window_start(days) if days else None,
    )


@protected_route(router.post, "/resync", [Scope.USERS_WRITE])
def resync_download_counters(request: Request) -> dict[str, int]:
    """Rebuild the per-rom counters from the event log (admin only)."""
    return {"roms_with_downloads": db_download_handler.resync_rom_counters()}
