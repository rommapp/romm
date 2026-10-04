from fastapi import Request

from endpoints.responses.stats import StatsReturn
from handler.auth.dependencies import get_rom_visibility_filter
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

    visibility = get_rom_visibility_filter(request)

    result: StatsReturn = {
        "PLATFORMS": db_stats_handler.get_platforms_count(visibility),
        "ROMS": db_stats_handler.get_roms_count(visibility),
        "SAVES": db_stats_handler.get_saves_count(),
        "STATES": db_stats_handler.get_states_count(),
        "SCREENSHOTS": db_stats_handler.get_screenshots_count(),
        "TOTAL_FILESIZE_BYTES": db_stats_handler.get_total_filesize(visibility),
    }

    if include_platform_stats:
        result["METADATA_COVERAGE"] = (
            db_stats_handler.get_metadata_coverage_by_platform(visibility)
        )
        result["REGION_BREAKDOWN"] = db_stats_handler.get_region_breakdown_by_platform(
            visibility
        )

    return result
