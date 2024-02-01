from endpoints.responses.filters import FiltersReturn
from fastapi import APIRouter

router = APIRouter()


@router.get("/filters")
def stats() -> FiltersReturn:
    """Endpoint to return the current RomM stats

    Returns:
        dict: Dictionary with all the stats
    """

    return {
        "genres": ["Role-playing (RPG)", "Turn-based strategy (TBS)", "Adventure"]
    }
