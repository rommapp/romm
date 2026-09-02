import re
from datetime import datetime, timezone
from typing import Final, NotRequired, TypedDict

from adapters.services.steam import SteamService
from adapters.services.steam_types import SteamAppDetails, SteamPlatforms
from config import STEAM_API_ENABLED
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from logger.logger import log

from .base_handler import BaseRom, MetadataHandler

# Half-Life 2: never region locked, so a fetch failing means Steam is down.
STEAM_HEARTBEAT_APP_ID: Final[int] = 220

STEAM_PLATFORMS: Final[frozenset[UPS]] = frozenset({UPS.WIN, UPS.LINUX, UPS.MAC})

# Regex to detect Steam app ID tags in filenames like (steam-12345)
STEAM_TAG_REGEX = re.compile(r"\(steam-(\d+)\)", re.IGNORECASE)

# Steam category IDs mapped onto the game-mode vocabulary the other providers use.
STEAM_CATEGORY_GAME_MODES: Final[dict[int, str]] = {
    1: "Multiplayer",
    2: "Single player",
    9: "Co-operative",
    20: "Massively Multiplayer Online (MMO)",
    24: "Split screen",
    37: "Split screen",
    38: "Co-operative",
    39: "Co-operative",
}


class SteamMetadata(TypedDict):
    # Shared keys keep the other providers' names and shapes, so the UI reads
    # Steam through the same components.
    total_rating: NotRequired[str]
    first_release_date: NotRequired[int]
    genres: NotRequired[list[str]]
    companies: NotRequired[list[str]]
    publishers: NotRequired[list[str]]
    developers: NotRequired[list[str]]
    game_modes: NotRequired[list[str]]
    # Steam-specific extras.
    platforms: NotRequired[SteamPlatforms]
    controller_support: NotRequired[str]
    metacritic_url: NotRequired[str]
    website: NotRequired[str]
    is_free: NotRequired[bool]
    required_age: NotRequired[int]


class SteamRom(BaseRom):
    steam_id: int | None
    steam_metadata: NotRequired[SteamMetadata]


def _parse_release_date(raw_date: str) -> int | None:
    """Convert Steam's release date into an epoch timestamp, or None if coarse.

    The store mixes "10 Dec, 2020" and "Dec 10, 2020" across apps, and returns
    year-only or quarter values for unreleased ones.
    """
    for date_format in ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(raw_date, date_format)
        except ValueError:
            continue
        return int(parsed.replace(tzinfo=timezone.utc).timestamp())

    return None


def extract_steam_metadata(details: SteamAppDetails) -> SteamMetadata:
    """Extract metadata from a Steam store payload."""
    metadata = SteamMetadata()

    genres = [
        genre["description"]
        for genre in details.get("genres", [])
        if genre.get("description")
    ]
    if genres:
        metadata["genres"] = genres

    developers = [dev for dev in details.get("developers", []) if dev]
    publishers = [pub for pub in details.get("publishers", []) if pub]
    if developers:
        metadata["developers"] = developers
    if publishers:
        metadata["publishers"] = publishers

    # dict.fromkeys dedupes while keeping developers ahead of publishers.
    companies = list(dict.fromkeys(developers + publishers))
    if companies:
        metadata["companies"] = companies

    game_modes = list(
        dict.fromkeys(
            mode
            for category in details.get("categories", [])
            if (mode := STEAM_CATEGORY_GAME_MODES.get(category.get("id", 0)))
        )
    )
    if game_modes:
        metadata["game_modes"] = game_modes

    metacritic = details.get("metacritic")
    if metacritic:
        if metacritic.get("score"):
            metadata["total_rating"] = str(metacritic["score"])
        if metacritic.get("url"):
            metadata["metacritic_url"] = metacritic["url"]

    release_date = details.get("release_date")
    if release_date and not release_date.get("coming_soon"):
        timestamp = _parse_release_date(release_date.get("date", ""))
        if timestamp is not None:
            metadata["first_release_date"] = timestamp

    platforms = details.get("platforms")
    if platforms:
        metadata["platforms"] = platforms

    if details.get("controller_support"):
        metadata["controller_support"] = details["controller_support"]

    website = details.get("website")
    if website:
        metadata["website"] = website

    if details.get("is_free") is not None:
        metadata["is_free"] = bool(details["is_free"])

    required_age = details.get("required_age")
    if required_age:
        try:
            metadata["required_age"] = int(required_age)
        except (TypeError, ValueError):
            pass

    return metadata


class SteamHandler(MetadataHandler):
    """
    Handler for the Steam storefront, which covers the PC platforms only.
    """

    def __init__(self) -> None:
        self.steam_service = SteamService()
        self.min_similarity_score: Final[float] = 0.85

    @classmethod
    def is_enabled(cls) -> bool:
        return STEAM_API_ENABLED

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            details = await self.steam_service.get_app_details(
                STEAM_HEARTBEAT_APP_ID, filters="basic"
            )
        except Exception as exc:
            log.error("Error checking Steam API: %s", exc)
            return False

        return details is not None

    async def get_rom(self, fs_name: str, platform_slug: str) -> SteamRom:
        """
        Get ROM information from the Steam storefront.

        :param fs_name: The filename to search for.
        :param platform_slug: The platform slug, used to skip non-PC platforms.
        :return: A SteamRom object.
        """
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return SteamRom(steam_id=None)

        # Skip non-PC platforms rather than spend requests that cannot match.
        if platform_slug not in STEAM_PLATFORMS:
            return SteamRom(steam_id=None)

        tag_match = STEAM_TAG_REGEX.search(fs_name)
        if tag_match:
            return await self.get_rom_by_id(int(tag_match.group(1)))

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        search_term = self.normalize_search_term(search_term, remove_punctuation=False)
        if not search_term:
            return SteamRom(steam_id=None)

        return await self._search_and_match(search_term)

    async def get_rom_by_id(self, steam_id: int) -> SteamRom:
        """Build a ROM from a known Steam app ID."""
        if not self.is_enabled():
            return SteamRom(steam_id=None)

        details = await self.steam_service.get_app_details(steam_id)
        if not details:
            log.debug("Could not find Steam app %s", steam_id)
            return SteamRom(steam_id=None)

        return await self._build_rom(details)

    async def _search_and_match(self, search_term: str) -> SteamRom:
        apps = await self.steam_service.search_apps(search_term)

        # The storefront returns DLC, soundtracks and tools alongside games.
        candidates = [
            app
            for app in apps
            if app.get("type") == "app" and app.get("id") and app.get("name")
        ]
        if not candidates:
            log.debug("Could not find '%s' on Steam", search_term)
            return SteamRom(steam_id=None)

        best_match, best_score = self.find_best_match(
            search_term,
            [app["name"] for app in candidates],
            min_similarity_score=self.min_similarity_score,
        )
        if not best_match:
            log.debug("No good match found for '%s' on Steam", search_term)
            return SteamRom(steam_id=None)

        best_app = next(app for app in candidates if app["name"] == best_match)
        details = await self.steam_service.get_app_details(best_app["id"])

        # `type` on a search hit is the store's coarse kind; only the app page
        # distinguishes a game from a demo, video or piece of hardware.
        if not details or details.get("type") != "game":
            log.debug(
                "Steam match for '%s' -> '%s' is not a game, skipping",
                search_term,
                best_match,
            )
            return SteamRom(steam_id=None)

        log.debug(
            "Found Steam match for '%s' -> '%s' (score: %.3f)",
            search_term,
            best_match,
            best_score,
        )
        return await self._build_rom(details)

    async def _build_rom(self, details: SteamAppDetails) -> SteamRom:
        app_id = details["steam_appid"]
        rom = SteamRom(
            steam_id=app_id,
            name=details["name"],
            url_cover=await self._resolve_cover_url(app_id, details),
            url_screenshots=[
                screenshot["path_full"]
                for screenshot in details.get("screenshots", [])
                if screenshot.get("path_full")
            ],
            steam_metadata=extract_steam_metadata(details),
        )

        summary = details.get("short_description")
        if summary:
            rom["summary"] = summary

        return rom

    async def _resolve_cover_url(self, app_id: int, details: SteamAppDetails) -> str:
        """Prefer the portrait capsule, falling back to the landscape header."""
        capsule_url = await self.steam_service.get_library_capsule_url(app_id)
        return capsule_url or details.get("header_image", "")
