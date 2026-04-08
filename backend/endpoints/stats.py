from endpoints.responses.stats import StatsReturn
from handler.database import db_stats_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get("")
def stats(include_platform_stats: bool = False) -> StatsReturn:
    """Endpoint to return the current RomM stats

    Returns:
        dict: Dictionary with all the stats
    """

    result: StatsReturn = {
        "PLATFORMS": db_stats_handler.get_platforms_count(),
        "ROMS": db_stats_handler.get_roms_count(),
        "SAVES": db_stats_handler.get_saves_count(),
        "STATES": db_stats_handler.get_states_count(),
        "SCREENSHOTS": db_stats_handler.get_screenshots_count(),
        "TOTAL_FILESIZE_BYTES": db_stats_handler.get_total_filesize(),
    }

    if include_platform_stats:
        result["METADATA_COVERAGE"] = (
            db_stats_handler.get_metadata_coverage_by_platform()
        )
        result["REGION_BREAKDOWN"] = db_stats_handler.get_region_breakdown_by_platform()

    return result
