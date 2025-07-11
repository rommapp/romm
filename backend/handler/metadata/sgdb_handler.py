import asyncio
from typing import Final, NotRequired, TypedDict

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import SGDBDimension, SGDBType
from config import STEAMGRIDDB_API_KEY
from logger.logger import log

from .base_hander import MetadataHandler

# Used to display the Mobygames API status in the frontend
STEAMGRIDDB_API_ENABLED: Final = bool(STEAMGRIDDB_API_KEY)


class SGDBResource(TypedDict):
    thumb: str
    url: str
    type: str


class SGDBResult(TypedDict):
    name: str
    resources: list[SGDBResource]


class SGDBRom(TypedDict):
    sgdb_id: int | None
    url_cover: NotRequired[str]


class SGDBBaseHandler(MetadataHandler):
    def __init__(self) -> None:
        self.sgdb_service = SteamGridDBService()

    async def get_details(self, search_term: str) -> list[SGDBResult]:
        games = await self.sgdb_service.search_games(term=search_term)
        if not games:
            log.debug(f"Could not find '{search_term}' on SteamGridDB")
            return []

        tasks = [
            self._get_game_covers(game_id=game["id"], game_name=game["name"])
            for game in games
        ]
        results = await asyncio.gather(*tasks)

        return list(filter(None, results))

    async def get_details_by_name(self, search_term: str) -> SGDBRom:
        games = await self.sgdb_service.search_games(term=search_term)
        if not games:
            log.debug(f"Could not find '{search_term}' on SteamGridDB")
            return SGDBRom(sgdb_id=None)

        games = [game for game in games if game["name"].lower() == search_term.lower()]
        if not games:
            log.debug(f"No exact match found for '{search_term}' on SteamGridDB")
            return SGDBRom(sgdb_id=None)

        first_game = games[0]
        game_details = await self._get_game_covers(
            game_id=first_game["id"], game_name=first_game["name"]
        )

        first_resource = next(
            (res for res in game_details["resources"] if res["url"]), None
        )
        if first_resource:
            return SGDBRom(sgdb_id=first_game["id"], url_cover=first_resource["url"])

        return SGDBRom(sgdb_id=first_game["id"])

    async def _get_game_covers(self, game_id: int, game_name: str) -> SGDBResult:
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
            return SGDBResult(name=game_name, resources=[])

        return SGDBResult(
            name=game_name,
            resources=[
                SGDBResource(
                    thumb=cover["thumb"],
                    url=cover["url"],
                    type="animated" if cover["thumb"].endswith(".webm") else "static",
                )
                for cover in game_covers
            ],
        )


sgdb_handler = SGDBBaseHandler()
