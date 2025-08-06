import asyncio
import re
from difflib import SequenceMatcher
from typing import Final, NotRequired, TypedDict

from adapters.services.steamgriddb import SteamGridDBService
from adapters.services.steamgriddb_types import SGDBDimension, SGDBType
from config import STEAMGRIDDB_API_KEY
from logger.logger import log

from .base_hander import MetadataHandler


# Levenshtein distance implementation using difflib
def levenshtein_distance(s1: str, s2: str) -> int:
    """Simple Levenshtein distance implementation using difflib"""
    return int((1 - SequenceMatcher(None, s1, s2).ratio()) * max(len(s1), len(s2)))


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
        self.max_levenshtein_distance: Final = 2
        self.min_sequence_ratio: Final = 0.85
        self.min_token_overlap_ratio: Final = 0.7
        self.min_similarity_score: Final = 0.75

    def _calculate_title_similarity(
        self, search_normalized: str, game_name: str
    ) -> float:
        """
        Calculate similarity between search term and game name using multiple metrics.
        Returns a score between 0 and 1, where 1 is a perfect match.
        """
        game_normalized = self.normalize_search_term(game_name, remove_articles=False)

        # Exact match gets the highest score
        if search_normalized == game_normalized:
            return 1.0

        # Split into tokens for word-based matching
        search_tokens = set(re.findall(r"\b\w+\b", search_normalized.lower()))
        game_tokens = set(re.findall(r"\b\w+\b", game_normalized.lower()))

        # Calculate token overlap ratio
        if search_tokens and game_tokens:
            intersection = search_tokens & game_tokens
            union = search_tokens | game_tokens
            token_overlap_ratio = len(intersection) / len(union)
        else:
            token_overlap_ratio = 0.0

        # Calculate sequence similarity (better for longer strings)
        sequence_ratio = SequenceMatcher(
            None, search_normalized, game_normalized
        ).ratio()

        # Calculate Levenshtein distance (normalized by max length)
        max_len = max(len(search_normalized), len(game_normalized))
        if max_len > 0:
            levenshtein_ratio = 1 - (
                levenshtein_distance(search_normalized, game_normalized) / max_len
            )
        else:
            levenshtein_ratio = 1.0

        # Token overlap is most important for game titles
        final_score = (
            token_overlap_ratio * 0.5 + sequence_ratio * 0.3 + levenshtein_ratio * 0.2
        )

        return final_score

    async def get_details(self, search_term: str) -> list[SGDBResult]:
        if not STEAMGRIDDB_API_ENABLED:
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
        if not STEAMGRIDDB_API_ENABLED:
            return SGDBRom(sgdb_id=None)

        for game_name in game_names:
            search_term = self.normalize_search_term(game_name, remove_articles=False)
            games = await self.sgdb_service.search_games(term=search_term)
            if not games:
                log.debug(f"Could not find '{search_term}' on SteamGridDB")
                continue

            game_scores = []
            for game in games:
                similarity_score = self._calculate_title_similarity(
                    search_term, game["name"]
                )
                game_scores.append((game, similarity_score))

            # Sort by similarity score (descending) to get the best match first
            game_scores.sort(key=lambda x: x[1], reverse=True)

            # Try the best matches within the threshold
            for game, score in game_scores:
                if score >= self.min_similarity_score:
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
                        log.debug(
                            f"Found match for '{search_term}' -> '{game['name']}' (score: {score:.3f})"
                        )
                        return SGDBRom(
                            sgdb_id=game["id"], url_cover=first_resource["url"]
                        )
                else:
                    # If the best match is below threshold, don't try others
                    break

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
