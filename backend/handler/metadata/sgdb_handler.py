import asyncio
from typing import Final, NotRequired, TypedDict

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import SGDBDimension, SGDBType
from config import STEAMGRIDDB_API_KEY
from Levenshtein import distance as levenshtein_distance
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
        self.max_levenshtein_distance: Final = 4

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

    async def get_details_by_names(self, game_names: list[str]) -> SGDBRom:
        for game_name in game_names:
            search_term = self.normalize_search_term(game_name, remove_articles=False)
            games = await self.sgdb_service.search_games(term=search_term)
            if not games:
                log.debug(f"Could not find '{search_term}' on SteamGridDB")
                continue

            # SGDB search is fuzzy so no need to split the search term by special characters
            search_term_normalized = self.normalize_search_term(
                search_term, remove_articles=False
            )

            # Calculate Levenshtein distances for all games and find the best match
            game_distances = []
            for game in games:
                game_name_normalized = self.normalize_search_term(
                    game["name"], remove_articles=False
                )
                distance = levenshtein_distance(
                    game_name_normalized, search_term_normalized
                )
                game_distances.append((game, distance))

            # Sort by distance (ascending) to get the best match first
            game_distances.sort(key=lambda x: x[1])

            # Try the best matches within the threshold
            for game, distance in game_distances:
                if distance <= self.max_levenshtein_distance:
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
                    if first_resource:
                        return SGDBRom(
                            sgdb_id=game["id"], url_cover=first_resource["url"]
                        )
                else:
                    return SGDBRom(sgdb_id=None)

        log.debug(f"No exact match found for '{', '.join(game_names)}' on SteamGridDB")
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
