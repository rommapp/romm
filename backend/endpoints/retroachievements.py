from anyio import Path
from decorators.auth import protected_route
from fastapi import Request
from utils.router import APIRouter
from handler.database import  db_rom_handler
from endpoints.responses.retroachievements import RetroAchievementsGameSchema
from exceptions.endpoint_exceptions import RomNotFoundInRetroAchievementsException
import asyncio
import http

import httpx
import yarl
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client

router = APIRouter()
async def _request(url: str, timeout: int = 120) -> dict:
    httpx_client = ctx_httpx_client.get()
    authorized_url = yarl.URL(url)
    try:
        res = await httpx_client.get(str(authorized_url), timeout=timeout)
        res.raise_for_status()
        return res.json()
    except httpx.NetworkError as exc:
        log.critical(
            "Connection error: can't connect to RetroAchievements", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Can't connect to RetroAchievements, check your internet connection",
        ) from exc
    except httpx.HTTPStatusError as err:
        if err.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
            # Retry after 2 seconds if rate limit hit
            await asyncio.sleep(2)
        else:
            # Log the error and return an empty dict if the request fails with a different code
            log.error(err)
            return {}
    except httpx.TimeoutException:
        # Retry the request once if it times out
        pass

    try:
        res = await httpx_client.get(url, timeout=timeout)
        res.raise_for_status()
    except (httpx.HTTPStatusError, httpx.TimeoutException) as err:
        if (
            isinstance(err, httpx.HTTPStatusError)
            and err.response.status_code == http.HTTPStatus.UNAUTHORIZED
        ):
            # Sometimes Mobygames returns 401 even with a valid API key
            return {}

        # Log the error and return an empty dict if the request fails with a different code
        log.error(err)
        return {}

    return res.json()



@protected_route(router.get, "/retroachievements/{id}", ["roms.read"])
async def get_rom_retroachievements(request: Request, id: int) -> RetroAchievementsGameSchema:
    """Get rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id

    Returns:
        RetroAchievementsGameSchema: User and Game info from retro achivements
    """

    url = yarl.URL("https://retroachievements.org/API/API_GetGameInfoAndUserProgress.php").with_query(
        g=[id],
        a=["1"],
        u=[request.user.ra_username],
        z=[request.user.ra_username],
        y=[request.user.ra_api_key],
    )

    game_with_details = await _request(str(url))

    if not game_with_details:
        raise RomNotFoundInRetroAchievementsException(id)

    return game_with_details

