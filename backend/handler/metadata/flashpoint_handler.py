import datetime
import json
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
import yarl
from fastapi import HTTPException, status

from config import FLASHPOINT_API_ENABLED
from logger.logger import log
from utils import get_version, is_valid_uuid
from utils.context import ctx_httpx_client

from .base_handler import MetadataHandler
from .base_handler import UniversalPlatformSlug as UPS


class FlashpointPlatform(TypedDict):
    slug: str
    flashpoint_id: int | None
    name: NotRequired[str]


class FlashpointGame(TypedDict):
    id: str
    title: str
    platform: str
    library: str
    series: str
    developer: str
    publisher: str
    source: str
    tags: list[str]
    original_description: str
    date_modified: str
    date_added: str
    play_mode: str
    status: str
    version: str
    release_date: str
    language: str
    notes: str


class FlashpointMetadata(TypedDict):
    franchises: list[str]
    companies: list[str]
    source: str
    genres: list[str]
    first_release_date: str
    game_modes: list[str]
    status: str
    version: str
    language: str
    notes: str


class FlashpointRom(TypedDict):
    flashpoint_id: str | None
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    flashpoint_metadata: NotRequired[FlashpointMetadata]


def extract_flashpoint_metadata(game: FlashpointGame) -> FlashpointMetadata:
    # Convert from "2003-08-30" format to unix timestamp
    first_release_date = ""
    if game.get("release_date"):
        try:
            date_obj = datetime.datetime.strptime(game["release_date"], "%Y-%m-%d")
            first_release_date = str(int(date_obj.timestamp()))
        except (ValueError, TypeError):
            first_release_date = ""

    return FlashpointMetadata(
        franchises=pydash.compact([game["series"]]),
        companies=pydash.uniq(pydash.compact([game["developer"], game["publisher"]])),
        source=game["source"],
        genres=game["tags"],
        first_release_date=first_release_date,
        game_modes=pydash.compact([game["play_mode"]]),
        status=game["status"],
        version=game["version"],
        language=game["language"],
        notes=game["notes"],
    )


class FlashpointHandler(MetadataHandler):
    """
    Handler for Flashpoint Project, a service for Flash games and browser-based content.
    Only supports the "browser" platform.
    """

    def __init__(self) -> None:
        self.base_url = "https://db-api.unstable.life"
        self.platforms_url = f"{self.base_url}/platforms"
        self.search_url = f"{self.base_url}/search"
        self.min_similarity_score: Final = 0.75

    @classmethod
    def is_enabled(cls) -> bool:
        return FLASHPOINT_API_ENABLED

    async def _request(self, url: str, query: dict) -> dict:
        """
        Sends a request to Flashpoint API.

        :param url: The API endpoint URL.
        :param query: A dictionary containing the query parameters.
        :return: A dictionary with the json result.
        :raises HTTPException: If the request fails or the service is unavailable.
        """
        httpx_client = ctx_httpx_client.get()

        filtered_query = {
            key: value
            for key, value in query.items()
            if value is not None and value != ""  # drop None and ""
        }
        if filtered_query:
            url = str(yarl.URL(url).update_query(**filtered_query))

        log.debug(
            "Flashpoint API request: URL=%s, Timeout=%s",
            url,
            60,
        )

        headers = {"user-agent": f"RomM/{get_version()}"}

        try:
            res = await httpx_client.get(url, headers=headers, timeout=60)
            res.raise_for_status()
            return res.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            log.warning(
                "Connection error: can't connect to Flashpoint API", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Flashpoint API, check your internet connection",
            ) from exc
        except json.JSONDecodeError as exc:
            log.error("Error decoding JSON response from Flashpoint API: %s", exc)
            return {}

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self._request(self.platforms_url, {})
        except Exception as e:
            log.error("Error checking Flashpoint API: %s", e)
            return False

        return bool(response)

    async def search_games(self, search_term: str) -> list[FlashpointGame]:
        """
        Search for games in Flashpoint database.

        :param search_term: The search term to look for.
        :return: A list of FlashpointGame objects.
        """
        try:
            response = await self._request(
                self.search_url,
                {
                    "smartSearch": search_term,
                    "filter": "true",
                },
            )

            if not response:
                return []

            games_data = json.loads(response) if isinstance(response, str) else response

            return [
                FlashpointGame(
                    {
                        "id": game_data["id"],
                        "title": game_data["title"],
                        "original_description": game_data.get(
                            "originalDescription", ""
                        ),
                        "platform": game_data.get("platform", ""),
                        "library": game_data.get("library", ""),
                        "series": game_data.get("series", []),
                        "developer": game_data.get("developer", ""),
                        "publisher": game_data.get("publisher", ""),
                        "source": game_data.get("source", ""),
                        "tags": game_data.get("tags", []),
                        "date_added": game_data.get("dateAdded", ""),
                        "date_modified": game_data.get("dateModified", ""),
                        "play_mode": game_data.get("playMode", ""),
                        "status": game_data.get("status", ""),
                        "version": game_data.get("version", ""),
                        "release_date": game_data.get("releaseDate", ""),
                        "language": game_data.get("language", ""),
                        "notes": game_data.get("notes", ""),
                    }
                )
                for game_data in games_data
            ]

        except Exception as exc:
            log.error("Error searching Flashpoint API: %s", exc)
            return []

    def get_platform(self, slug: str) -> FlashpointPlatform:
        """
        Get Flashpoint platform information.
        """
        if slug not in FLASHPOINT_PLATFORM_LIST:
            return FlashpointPlatform(slug=slug, flashpoint_id=None)

        platform = FLASHPOINT_PLATFORM_LIST[UPS(slug)]
        return FlashpointPlatform(
            slug=slug,
            name=platform["name"],
            flashpoint_id=platform["id"],
        )

    async def get_rom(self, fs_name: str, platform_slug: str) -> FlashpointRom:
        """
        Get ROM information from Flashpoint.

        :param fs_name: The filename to search for.
        :param platform_slug: The platform slug (must be "browser").
        :return: A FlashpointRom object.
        """
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return FlashpointRom(flashpoint_id=None)

        if platform_slug not in FLASHPOINT_PLATFORM_LIST:
            return FlashpointRom(flashpoint_id=None)

        # Check if the filename is a UUID
        fs_name_no_tags = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        if is_valid_uuid(fs_name_no_tags):
            return await self.get_rom_by_id(flashpoint_id=fs_name_no_tags)

        # Normalize the search term
        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        search_term = self.normalize_search_term(search_term, remove_punctuation=False)

        # Search for games
        games = await self.search_games(search_term)

        if not games:
            log.debug(f"Could not find '{search_term}' on Flashpoint")
            return FlashpointRom(flashpoint_id=None)

        # Find the best match
        game_names = [game["title"] for game in games]
        best_match, best_score = self.find_best_match(
            search_term,
            game_names,
            min_similarity_score=self.min_similarity_score,
        )

        if best_match:
            # Find the game data for the best match
            best_game = next(
                (game for game in games if game["title"] == best_match), None
            )

            if best_game:
                log.debug(
                    f"Found Flashpoint match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
                )

                return FlashpointRom(
                    flashpoint_id=best_game["id"],
                    name=best_game["title"],
                    summary=best_game["original_description"],
                    url_cover=f"https://infinity.unstable.life/images/Logos/{best_game['id'][:2]}/{best_game['id'][2:4]}/{best_game['id']}?type=jpg",
                    url_screenshots=[
                        f"https://infinity.unstable.life/images/Screenshots/{best_game['id'][:2]}/{best_game['id'][2:4]}/{best_game['id']}?type=jpg"
                    ],
                    flashpoint_metadata=extract_flashpoint_metadata(best_game),
                )

        log.debug(f"No good match found for '{search_term}' on Flashpoint")
        return FlashpointRom(flashpoint_id=None)

    async def get_matched_roms_by_name(
        self, fs_name: str, platform_slug: str
    ) -> list[FlashpointRom]:
        """
        Get ROM information by name from Flashpoint.

        Args:
            fs_name (str): The filesystem name of the ROM.
            platform_slug (str): The platform slug.
        """
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return []

        if platform_slug not in FLASHPOINT_PLATFORM_LIST:
            return []

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        search_term = self.normalize_search_term(search_term, remove_punctuation=False)

        games = await self.search_games(search_term)
        return [
            FlashpointRom(
                flashpoint_id=game["id"],
                name=game["title"],
                summary=game["original_description"],
                url_cover=f"https://infinity.unstable.life/images/Logos/{game['id'][:2]}/{game['id'][2:4]}/{game['id']}?type=jpg",
                url_screenshots=[
                    f"https://infinity.unstable.life/images/Screenshots/{game['id'][:2]}/{game['id'][2:4]}/{game['id']}?type=jpg"
                ],
                flashpoint_metadata=extract_flashpoint_metadata(game),
            )
            for game in games
        ]

    async def get_rom_by_id(self, flashpoint_id: str) -> FlashpointRom:
        """
        Get ROM information by Flashpoint ID.

        :param flashpoint_id: The Flashpoint game ID.
        :return: A FlashpointRom object.
        """
        if not FLASHPOINT_API_ENABLED:
            return FlashpointRom(flashpoint_id=None)

        if not flashpoint_id:
            return FlashpointRom(flashpoint_id=None)

        try:
            response = await self._request(
                self.search_url,
                {
                    "id": flashpoint_id,
                    "filter": "true",
                },
            )

            if not response:
                return FlashpointRom(flashpoint_id=None)

            games_data = json.loads(response) if isinstance(response, str) else response
            if (
                not games_data
                or not isinstance(games_data, list)
                or len(games_data) == 0
            ):
                return FlashpointRom(flashpoint_id=None)

            game_data = games_data[0]
            if not isinstance(game_data, dict):
                return FlashpointRom(flashpoint_id=None)

            if not game_data["id"]:
                return FlashpointRom(flashpoint_id=None)

            game = FlashpointGame(
                {
                    "id": game_data["id"],
                    "title": game_data["title"],
                    "original_description": game_data["originalDescription"],
                    "platform": game_data["platform"],
                    "library": game_data["library"],
                    "series": game_data["series"],
                    "developer": game_data["developer"],
                    "publisher": game_data["publisher"],
                    "source": game_data["source"],
                    "tags": game_data["tags"],
                    "date_added": game_data["dateAdded"],
                    "date_modified": game_data["dateModified"],
                    "play_mode": game_data["playMode"],
                    "status": game_data["status"],
                    "version": game_data["version"],
                    "release_date": game_data["releaseDate"],
                    "language": game_data["language"],
                    "notes": game_data["notes"],
                }
            )

            return FlashpointRom(
                flashpoint_id=game["id"],
                name=game["title"],
                summary=game["original_description"],
                url_cover=f"https://infinity.unstable.life/images/Logos/{game['id'][:2]}/{game['id'][2:4]}/{game['id']}?type=jpg",
                url_screenshots=[
                    f"https://infinity.unstable.life/images/Screenshots/{game['id'][:2]}/{game['id'][2:4]}/{game['id']}?type=jpg"
                ],
                flashpoint_metadata=extract_flashpoint_metadata(game),
            )

        except Exception as exc:
            log.error("Error getting ROM by ID from Flashpoint API: %s", exc)
            return FlashpointRom(flashpoint_id=None)


class SlugToFlashpointId(TypedDict):
    id: int
    name: str


FLASHPOINT_PLATFORM_LIST: dict[UPS, SlugToFlashpointId] = {
    UPS.BROWSER: {"id": 1, "name": "Browser (Flash/HTML5)"}
}
