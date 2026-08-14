from fastapi import Request

from endpoints.responses.stats import StatsReturn
from handler.auth.dependencies import get_permissions
from handler.database import db_stats_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get("")
def stats(request: Request, include_platform_stats: bool = False) -> StatsReturn:
    """Endpoint to return the current RomM stats

    Returns:
        dict: Dictionary with all the stats
    """

    # Exclude platforms/roms hidden from the caller (admins/anon: no filtering).
    hidden_platform_ids: list[int] = []
    hidden_rom_ids: list[int] = []
    if request.user.is_authenticated:
        perms = get_permissions(request)
        hidden_platform_ids = list(perms.hidden_platform_ids)
        hidden_rom_ids = list(perms.hidden_rom_ids)

    result: StatsReturn = {
        "PLATFORMS": db_stats_handler.get_platforms_count(
            hidden_platform_ids, hidden_rom_ids
        ),
        "ROMS": db_stats_handler.get_roms_count(hidden_platform_ids, hidden_rom_ids),
        "SAVES": db_stats_handler.get_saves_count(),
        "STATES": db_stats_handler.get_states_count(),
        "SCREENSHOTS": db_stats_handler.get_screenshots_count(),
        "TOTAL_FILESIZE_BYTES": db_stats_handler.get_total_filesize(
            hidden_platform_ids, hidden_rom_ids
        ),
    }

    if include_platform_stats:
        result["METADATA_COVERAGE"] = (
            db_stats_handler.get_metadata_coverage_by_platform(
                hidden_platform_ids, hidden_rom_ids
            )
        )
        result["REGION_BREAKDOWN"] = db_stats_handler.get_region_breakdown_by_platform(
            hidden_platform_ids, hidden_rom_ids
        )

    return result
