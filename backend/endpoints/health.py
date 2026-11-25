from endpoints.responses.health import HealthLiveResponse
from utils.router import APIRouter

router = APIRouter(prefix="/health", tags=["system"])


@router.get("/live")
async def live() -> HealthLiveResponse:
    """Report that this API process is up, without touching the database or cache."""
    return {"status": "ok"}
