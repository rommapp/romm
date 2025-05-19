from endpoints.responses.stats import StatsReturn
from handler.database import db_stats_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get("")
def stats() -> StatsReturn:
    """Endpoint to return the current RomM stats

    Returns:
        dict: Dictionary with all the stats
    """

    return {
        "PLATFORMS_COUNT": db_stats_handler.get_platforms_count(),
        "PLATFORMS": db_stats_handler.get_platforms_filesize(),
        "ROMS": db_stats_handler.get_roms_count(),
        "SAVES": db_stats_handler.get_saves_count(),
        "STATES": db_stats_handler.get_states_count(),
        "SCREENSHOTS": db_stats_handler.get_screenshots_count(),
        "TOTAL_FILESIZE": db_stats_handler.get_total_filesize(),
    }
