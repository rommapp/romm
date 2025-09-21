import asyncio
from typing import Final, NotRequired, TypedDict

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import SGDBDimension, SGDBGame, SGDBType
from config import STEAMGRIDDB_API_KEY
from logger.logger import log

from .base_handler import MetadataHandler


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
        self.min_similarity_score: Final = 0.98

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(STEAMGRIDDB_API_KEY)

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self.sgdb_service.get_game_by_id(1)
        except Exception as e:
            log.error("Error checking SteamGridDB API: %s", e)
            return False

        return bool(response)

    async def get_rom_by_id(self, sgdb_id: int) -> SGDBRom:
        """Get ROM details by SteamGridDB ID."""
        if not self.is_enabled():
            return SGDBRom(sgdb_id=None)

        try:
            game = await self.sgdb_service.get_game_by_id(sgdb_id)
            if not game:
                return SGDBRom(sgdb_id=None)

            # Get covers for the game
            game_details = await self._get_game_covers(
                game_id=game["id"],
                game_name=game["name"],
                types=(SGDBType.STATIC,),
                is_nsfw=False,
                is_humor=False,
                is_epilepsy=False,
            )

            first_resource = next(
                (res for res in game_details["resources"] if res["url"]), None
            )

            result = SGDBRom(sgdb_id=game["id"])
            if first_resource:
                result["url_cover"] = first_resource["url"]
            return result
        except Exception as e:
            log.warning(f"Failed to fetch ROM by SteamGridDB ID {sgdb_id}: {e}")
            return SGDBRom(sgdb_id=None)

    async def get_details(self, search_term: str) -> list[SGDBResult]:
        if not self.is_enabled():
            return []

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

    async def get_details_by_names(self, game_names: list[str]) -> SGDBRom:
        if not self.is_enabled():
            return SGDBRom(sgdb_id=None)

        for game_name in game_names:
            search_term = self.normalize_search_term(game_name, remove_articles=False)
            games = await self.sgdb_service.search_games(term=search_term)
            if not games:
                log.debug(f"Could not find '{search_term}' on SteamGridDB")
                continue

            games_by_name: dict[str, SGDBGame] = {}
            for game in games:
                if (
                    game["name"] not in games_by_name
                    or game["id"] < games_by_name[game["name"]]["id"]
                ):
                    games_by_name[game["name"]] = game

            best_match, best_score = self.find_best_match(
                search_term,
                list(games_by_name.keys()),
                min_similarity_score=self.min_similarity_score,
            )
            if best_match:
                game_details = await self._get_game_covers(
                    game_id=games_by_name[best_match]["id"],
                    game_name=games_by_name[best_match]["name"],
                    types=(SGDBType.STATIC,),
                    is_nsfw=False,
                    is_humor=False,
                    is_epilepsy=False,
                )

                first_resource = next(
                    (res for res in game_details["resources"] if res["url"]), None
                )
                if first_resource:
                    log.debug(
                        f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
                    )
                    return SGDBRom(
                        sgdb_id=games_by_name[best_match]["id"],
                        url_cover=first_resource["url"],
                    )

        log.debug(f"No good match found for '{', '.join(game_names)}' on SteamGridDB")
        return SGDBRom(sgdb_id=None)

    async def _get_game_covers(
        self,
        game_id: int,
        game_name: str,
        dimensions: tuple[SGDBDimension, ...] = (
            SGDBDimension.STEAM_VERTICAL,
            SGDBDimension.GOG_GALAXY_TILE,
            SGDBDimension.GOG_GALAXY_COVER,
            SGDBDimension.SQUARE_512,
            SGDBDimension.SQUARE_1024,
        ),
        types: tuple[SGDBType, ...] = (SGDBType.STATIC, SGDBType.ANIMATED),
        is_nsfw: bool | None = None,
        is_humor: bool | None = None,
        is_epilepsy: bool | None = None,
    ) -> SGDBResult:
        game_covers = [
            cover
            async for cover in self.sgdb_service.iter_grids_for_game(
                game_id=game_id,
                dimensions=dimensions,
                types=types,
                is_nsfw=is_nsfw,
                is_humor=is_humor,
                is_epilepsy=is_epilepsy,
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
