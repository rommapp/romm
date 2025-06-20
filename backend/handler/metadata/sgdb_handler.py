import asyncio
from typing import Any, Final

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import SGDBDimension, SGDBType
from config import STEAMGRIDDB_API_KEY
from logger.logger import log

from .base_hander import MetadataHandler

# Used to display the Mobygames API status in the frontend
STEAMGRIDDB_API_ENABLED: Final = bool(STEAMGRIDDB_API_KEY)


class SGDBBaseHandler(MetadataHandler):
    def __init__(self) -> None:
        self.sgdb_service = SteamGridDBService()

    async def get_details(self, search_term: str) -> list[dict[str, Any]]:
        games = await self.sgdb_service.search_games(term=search_term)
        if not games:
            log.warning(f"Could not find '{search_term}' on SteamGridDB")
            return []

        tasks = [
            self._get_game_covers(game_id=game["id"], game_name=game["name"])
            for game in games
        ]
        results = await asyncio.gather(*tasks)

        return list(filter(None, results))

    async def _get_game_covers(
        self, game_id: int, game_name: str
    ) -> dict[str, Any] | None:
        game_covers = [
            cover
            async for cover in self.sgdb_service.iter_grids_for_game(
                game_id=game_id,
                dimensions=(
                    SGDBDimension.STEAM_VERTICAL,
                    SGDBDimension.GOG_GALAXY_TILE,
                    SGDBDimension.GOG_GALAXY_COVER,
                    SGDBDimension.SQUARE_512,
                    SGDBDimension.SQUARE_1024,
                ),
                types=(
                    SGDBType.STATIC,
                    SGDBType.ANIMATED,
                ),
            )
        ]
        if not game_covers:
            return None

        return {
            "name": game_name,
            "resources": [
                {
                    "thumb": cover["thumb"],
                    "url": cover["url"],
                    "type": (
                        "animated" if cover["thumb"].endswith(".webm") else "static"
                    ),
                }
                for cover in game_covers
            ],
        }


sgdb_handler = SGDBBaseHandler()
