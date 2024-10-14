import yarl
from decorators.auth import protected_route
from endpoints.responses.retroachievements import RetroAchievementsGameSchema
from exceptions.endpoint_exceptions import RomNotFoundInRetroAchievementsException
from fastapi import Request
from handler.metadata.ra_handler import RetroAchievementsHandler
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.get, "/retroachievements/{id}", ["roms.read"])
async def get_rom_retroachievements(
    request: Request, id: int
) -> RetroAchievementsGameSchema:
    """Get rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id

    Returns:
        RetroAchievementsGameSchema: User and Game info from retro achivements
    """

    url = yarl.URL(
        "https://retroachievements.org/API/API_GetGameInfoAndUserProgress.php"
    ).with_query(
        g=[id],
        a=["1"],
        u=[request.user.ra_username],
        z=[request.user.ra_username],
        y=[request.user.ra_api_key],
    )

    game_with_details = await RetroAchievementsHandler._request(
        RetroAchievementsHandler, str(url)
    )

    if not game_with_details:
        raise RomNotFoundInRetroAchievementsException(id)

    return RetroAchievementsGameSchema.model_validate(game_with_details)
