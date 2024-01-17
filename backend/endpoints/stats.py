from endpoints.responses.stats import StatsReturn
from fastapi import APIRouter
from handler import dbstatsh

router = APIRouter()


@router.get("/stats")
def stats() -> StatsReturn:
    """Endpoint to return the current RomM stats

    Returns:
        dict: Dictionary with all the stats
    """

    return {
        "PLATFORMS": dbstatsh.get_platforms_count(),
        "ROMS": dbstatsh.get_roms_count(),
        "SAVES": dbstatsh.get_saves_count(),
        "STATES": dbstatsh.get_states_count(),
        "SCREENSHOTS": dbstatsh.get_screenshots_count(),
        "FILESIZE": dbstatsh.get_total_filesize(),
    }
