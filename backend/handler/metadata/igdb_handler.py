import re
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from fastapi import status

from adapters.services.igdb import IGDBService
from adapters.services.igdb_types import (
    Game,
    GameType,
    mark_expanded,
    mark_list_expanded,
)
from config import IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, IS_PYTEST_RUN
from config.config_manager import config_manager as cm
from handler.redis_handler import async_cache
from logger.logger import log
from utils.context import ctx_httpx_client

from .base_handler import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    BaseRom,
    MetadataHandler,
)
from .base_handler import UniversalPlatformSlug as UPS

PS1_IGDB_ID: Final = 7
PS2_IGDB_ID: Final = 8
PSP_IGDB_ID: Final = 38
SWITCH_IGDB_ID: Final = 130
ARCADE_IGDB_IDS: Final = [52, 79, 80]

# Regex to detect IGDB ID tags in filenames like (igdb-12345)
IGDB_TAG_REGEX = re.compile(r"\(igdb-(\d+)\)", re.IGNORECASE)


class IGDBPlatform(TypedDict):
    slug: str
    igdb_id: int | None
    igdb_slug: NotRequired[str]
    name: NotRequired[str]
    category: NotRequired[str]
    generation: NotRequired[int]
    family_name: NotRequired[str]
    family_slug: NotRequired[str]
    url: NotRequired[str]
    url_logo: NotRequired[str]


class IGDBMetadataPlatform(TypedDict):
    igdb_id: int
    name: str


class IGDBAgeRating(TypedDict):
    rating: str
    category: str
    rating_cover_url: str


class IGDBRelatedGame(TypedDict):
    id: int
    name: str
    slug: str
    type: str
    cover_url: str


class IGDBMetadata(TypedDict):
    total_rating: str
    aggregated_rating: str
    first_release_date: int | None
    youtube_video_id: str | None
    genres: list[str]
    franchises: list[str]
    alternative_names: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[IGDBAgeRating]
    platforms: list[IGDBMetadataPlatform]
    expansions: list[IGDBRelatedGame]
    dlcs: list[IGDBRelatedGame]
    remasters: list[IGDBRelatedGame]
    remakes: list[IGDBRelatedGame]
    expanded_games: list[IGDBRelatedGame]
    ports: list[IGDBRelatedGame]
    similar_games: list[IGDBRelatedGame]


class IGDBRom(BaseRom):
    igdb_id: int | None
    slug: NotRequired[str]
    igdb_metadata: NotRequired[IGDBMetadata]


def build_related_game(
    handler: MetadataHandler, rom: Game, game_type: str
) -> IGDBRelatedGame:
    cover = rom.get("cover")
    assert mark_expanded(cover)
    cover_url = cover.get("url", "") if cover else ""

    return IGDBRelatedGame(
        id=rom["id"],
        slug=rom.get("slug", ""),
        name=rom.get("name", ""),
        cover_url=handler.normalize_cover_url(cover_url.replace("t_thumb", "t_1080p")),
        type=game_type,
    )


def extract_metadata_from_igdb_rom(self: MetadataHandler, rom: Game) -> IGDBMetadata:
    age_ratings = rom.get("age_ratings", [])
    alternative_names = rom.get("alternative_names", [])
    collections = rom.get("collections", [])
    dlcs = rom.get("dlcs", [])
    expanded_games = rom.get("expanded_games", [])
    expansions = rom.get("expansions", [])
    franchise = rom.get("franchise", None)
    franchises = rom.get("franchises", [])
    game_modes = rom.get("game_modes", [])
    genres = rom.get("genres", [])
    involved_companies = rom.get("involved_companies", [])
    platforms = rom.get("platforms", [])
    ports = rom.get("ports", [])
    remakes = rom.get("remakes", [])
    remasters = rom.get("remasters", [])
    similar_games = rom.get("similar_games", [])
    videos = rom.get("videos", [])

    # Narrow types for expandable fields we requested IGDB to be expanded.
    assert mark_expanded(franchise)
    assert mark_list_expanded(age_ratings)
    assert mark_list_expanded(alternative_names)
    assert mark_list_expanded(collections)
    assert mark_list_expanded(dlcs)
    assert mark_list_expanded(expanded_games)
    assert mark_list_expanded(expansions)
    assert mark_list_expanded(franchises)
    assert mark_list_expanded(game_modes)
    assert mark_list_expanded(genres)
    assert mark_list_expanded(involved_companies)
    assert mark_list_expanded(platforms)
    assert mark_list_expanded(ports)
    assert mark_list_expanded(remakes)
    assert mark_list_expanded(remasters)
    assert mark_list_expanded(similar_games)
    assert mark_list_expanded(videos)

    return IGDBMetadata(
        {
            "youtube_video_id": videos[0].get("video_id") if videos else None,
            "total_rating": str(round(rom.get("total_rating", 0.0), 2)),
            "aggregated_rating": str(round(rom.get("aggregated_rating", 0.0), 2)),
            "first_release_date": rom.get("first_release_date", None),
            "genres": [g.get("name", "") for g in genres if g.get("name")],
            "franchises": pydash.compact(
                [franchise.get("name") if franchise else None]
                + [f.get("name", "") for f in franchises if f.get("name")]
            ),
            "alternative_names": [
                n.get("name", "") for n in alternative_names if n.get("name")
            ],
            "collections": [c.get("name", "") for c in collections if c.get("name")],
            "game_modes": [g.get("name", "") for g in game_modes if g.get("name")],
            "companies": [
                c["company"]["name"] for c in involved_companies if c.get("company")
            ],
            "platforms": [
                IGDBMetadataPlatform(igdb_id=p["id"], name=p.get("name", ""))
                for p in platforms
            ],
            "age_ratings": [
                IGDB_AGE_RATINGS[rating_category]
                for r in age_ratings
                if (rating_category := r.get("rating_category")) in IGDB_AGE_RATINGS
            ],
            "expansions": [
                build_related_game(handler=self, rom=r, game_type="expansion")
                for r in expansions
            ],
            "dlcs": [
                build_related_game(handler=self, rom=r, game_type="dlc") for r in dlcs
            ],
            "remasters": [
                build_related_game(handler=self, rom=r, game_type="remaster")
                for r in remasters
            ],
            "remakes": [
                build_related_game(handler=self, rom=r, game_type="remake")
                for r in remakes
            ],
            "expanded_games": [
                build_related_game(handler=self, rom=r, game_type="expanded")
                for r in expanded_games
            ],
            "ports": [
                build_related_game(handler=self, rom=r, game_type="port") for r in ports
            ],
            "similar_games": [
                build_related_game(handler=self, rom=r, game_type="similar")
                for r in similar_games
            ],
        }
    )


# Mapping from scan.priority.region codes to IGDB game_localizations region identifiers
# IGDB's game_localizations provides regional titles and cover art, but NOT localized descriptions
REGION_TO_IGDB_LOCALE: dict[str, str | None] = {
    "us": None,  # United States - use default (no localization needed)
    "wor": None,  # World - use default
    "eu": "EU",  # Europe region
    "jp": "ja-JP",  # Japan
    "kr": "ko-KR",  # Korea
    "cn": "zh-CN",  # China (Simplified Chinese)
    "tw": "zh-TW",  # Taiwan (Traditional Chinese)
}


def get_igdb_preferred_locale() -> str | None:
    """Get IGDB locale from scan.priority.region configuration.

    Maps region priority codes to IGDB's game_localizations region identifiers.
    Returns the first matching region from the priority list, or None for default.

    Returns:
        IGDB region identifier (e.g., "ja-JP", "EU") or None for default
    """
    config = cm.get_config()

    # Check each region in priority order and return first match
    for region in config.SCAN_REGION_PRIORITY:
        igdb_locale = REGION_TO_IGDB_LOCALE.get(region.lower())
        if igdb_locale is not None:
            return igdb_locale

    return None


def extract_localized_data(rom: Game, preferred_locale: str | None) -> tuple[str, str]:
    """Extract localized name and cover URL based on preferred locale.

    Returns (name, cover_url) - falls back to default if locale not found.
    """
    default_name = rom.get("name", "")
    default_cover = pydash.get(rom, "cover.url", "")

    if not preferred_locale:
        return default_name, default_cover

    game_localizations = rom.get("game_localizations", [])
    if not game_localizations:
        return default_name, default_cover

    assert mark_list_expanded(game_localizations)

    for loc in game_localizations:
        region = loc.get("region")
        if not region:
            continue

        assert mark_expanded(region)

        # Match locale by region identifier (e.g., "ja-JP", "ko-KR", "EU")
        if region.get("identifier") == preferred_locale:
            localized_name = loc.get("name") or default_name
            localized_cover = loc.get("cover")

            if localized_cover:
                assert mark_expanded(localized_cover)
                cover_url = localized_cover.get("url", "") or default_cover
            else:
                cover_url = default_cover

            return localized_name, cover_url

    # Locale not found, fall back to default
    log.warning(
        f"IGDB locale '{preferred_locale}' not found for '{default_name}', using default"
    )
    return default_name, default_cover


def build_igdb_rom(
    handler: "IGDBHandler", rom: Game, preferred_locale: str | None
) -> "IGDBRom":
    """Build an IGDBRom from IGDB game data with localization support.

    Args:
        handler: IGDBHandler instance for URL normalization
        rom: Game data from IGDB API
        preferred_locale: Locale code (e.g., "ja-JP") or None

    Returns:
        IGDBRom with localized name/cover if available
    """
    rom_screenshots = rom.get("screenshots", [])
    assert mark_list_expanded(rom_screenshots)

    localized_name, localized_cover = extract_localized_data(rom, preferred_locale)

    return IGDBRom(
        igdb_id=rom["id"],
        slug=rom.get("slug", ""),
        name=localized_name,
        summary=rom.get("summary", ""),
        url_cover=handler.normalize_cover_url(localized_cover).replace(
            "t_thumb", "t_1080p"
        ),
        url_screenshots=[
            handler.normalize_cover_url(s.get("url", "")).replace("t_thumb", "t_720p")
            for s in rom_screenshots
        ],
        igdb_metadata=extract_metadata_from_igdb_rom(handler, rom),
    )


class IGDBHandler(MetadataHandler):
    def __init__(self) -> None:
        self.igdb_service = IGDBService(twitch_auth=TwitchAuth())
        self.pagination_limit = 200

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(IGDB_CLIENT_ID and IGDB_CLIENT_SECRET)

    @staticmethod
    def extract_igdb_id_from_filename(fs_name: str) -> int | None:
        """Extract IGDB ID from filename tag like (igdb-12345)."""
        match = IGDB_TAG_REGEX.search(fs_name)
        if match:
            return int(match.group(1))
        return None

    async def _search_rom(
        self, search_term: str, platform_igdb_id: int, with_game_type: bool = False
    ) -> Game | None:
        if not platform_igdb_id:
            return None

        if with_game_type:
            categories = (
                GameType.EXPANDED_GAME,
                GameType.MAIN_GAME,
                GameType.PORT,
                GameType.REMAKE,
                GameType.REMASTER,
            )
            game_type_filter = f"& game_type=({','.join(map(str, categories))})"
        else:
            game_type_filter = ""

        log.debug("Searching in games endpoint with game_type %s", game_type_filter)
        where_filter = f"platforms=[{platform_igdb_id}] {game_type_filter}"

        # Special case for ScummVM games
        # https://github.com/rommapp/romm/issues/2424
        scummvm_platform = self.get_platform(UPS.SCUMMVM)
        if scummvm_platform["igdb_id"] == platform_igdb_id:
            where_filter = f"keywords=[{platform_igdb_id}] {game_type_filter}"

        roms = await self.igdb_service.list_games(
            search_term=search_term,
            fields=GAMES_FIELDS,
            where=where_filter,
            limit=self.pagination_limit,
        )

        games_by_name: dict[str, Game] = {}
        for game in roms:
            game_name = game.get("name", "")
            if (
                game_name not in games_by_name
                or game["id"] < games_by_name[game_name]["id"]
            ):
                games_by_name[game_name] = game

        best_match, best_score = self.find_best_match(
            search_term,
            list(games_by_name.keys()),
        )
        if best_match:
            log.debug(
                f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
            )
            return games_by_name[best_match]

        log.debug("Searching expanded in search endpoint")
        roms_expanded = await self.igdb_service.search(
            fields=SEARCH_FIELDS,
            where=f'game.platforms=[{platform_igdb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*)',
            limit=self.pagination_limit,
        )

        if roms_expanded:
            log.debug(
                "Searching expanded in games endpoint for expanded game %s",
                roms_expanded[0]["game"],
            )
            extra_roms = await self.igdb_service.list_games(
                fields=GAMES_FIELDS,
                where=f"id={roms_expanded[0]['game']['id']}",
                limit=self.pagination_limit,
            )

            extra_games_by_name: dict[str, Game] = {}
            for game in extra_roms:
                game_name = game.get("name", "")
                if game_name not in extra_games_by_name:
                    extra_games_by_name[game_name] = game

            best_match, best_score = self.find_best_match(
                search_term,
                list(extra_games_by_name.keys()),
            )
            if best_match:
                log.debug(
                    f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
                )
                return extra_games_by_name[best_match]

            roms.extend(extra_roms)

        return None

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            roms = await self.igdb_service.list_games(
                fields=["id"],
                limit=1,
            )
        except Exception as e:
            log.error("Error checking IGDB API: %s", e)
            return False

        return bool(roms)

    def get_platform(self, slug: str) -> IGDBPlatform:
        if slug in IGDB_PLATFORM_LIST:
            platform = IGDB_PLATFORM_LIST[UPS(slug)]

            return IGDBPlatform(
                igdb_id=platform["id"],
                slug=slug,
                igdb_slug=platform["slug"],
                name=platform["name"],
                category=platform["category"],
                generation=platform["generation"],
                family_name=platform["family_name"],
                family_slug=platform["family_slug"],
                url=platform["url"],
                url_logo=self.normalize_cover_url(platform["url_logo"]),
            )

        if slug in IGDB_PLATFORM_VERSIONS:
            platform_version = IGDB_PLATFORM_VERSIONS[slug]
            main_platform = IGDB_PLATFORM_LIST[platform_version["platform_slug"]]

            return IGDBPlatform(
                igdb_id=main_platform["id"],
                slug=slug,
                igdb_slug=main_platform["slug"],
                name=platform_version["name"],
                category=main_platform["category"],
                generation=main_platform["generation"],
                family_name=main_platform["family_name"],
                family_slug=main_platform["family_slug"],
                url=platform_version["url"],
                url_logo=self.normalize_cover_url(
                    platform_version["url_logo"] or main_platform["url_logo"]
                ),
            )

        return IGDBPlatform(igdb_id=None, slug=slug)

    async def get_rom(self, fs_name: str, platform_igdb_id: int) -> IGDBRom:
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return IGDBRom(igdb_id=None)

        if not platform_igdb_id:
            return IGDBRom(igdb_id=None)

        # Check for IGDB ID tag in filename first
        igdb_id_from_tag = self.extract_igdb_id_from_filename(fs_name)
        if igdb_id_from_tag:
            log.debug(f"Found IGDB ID tag in filename: {igdb_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(igdb_id_from_tag)
            if rom_by_id["igdb_id"]:
                log.debug(
                    f"Successfully matched ROM by IGDB ID tag: {fs_name} -> {igdb_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"IGDB ID {igdb_id_from_tag} from filename tag not found in IGDB"
                )

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = IGDBRom(igdb_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(fs_name)
        if platform_igdb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS2, PSP)
        match = SONY_SERIAL_REGEX.search(fs_name, re.IGNORECASE)
        if platform_igdb_id == PS1_IGDB_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        if platform_igdb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        if platform_igdb_id == PSP_IGDB_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        # Support for switch titleID filename format
        match = SWITCH_TITLEDB_REGEX.search(fs_name)
        if platform_igdb_id == SWITCH_IGDB_ID and match:
            search_term, index_entry = await self._switch_titledb_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = IGDBRom(
                    igdb_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for switch productID filename format
        match = SWITCH_PRODUCT_ID_REGEX.search(fs_name)
        if platform_igdb_id == SWITCH_IGDB_ID and match:
            search_term, index_entry = await self._switch_productid_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = IGDBRom(
                    igdb_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for MAME arcade filename format
        if platform_igdb_id in ARCADE_IGDB_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)

        log.debug("Searching for %s on IGDB with game_type", search_term)
        rom = await self._search_rom(search_term, platform_igdb_id, with_game_type=True)
        if not rom:
            log.debug("Searching for %s on IGDB without game_type", search_term)
            rom = await self._search_rom(search_term, platform_igdb_id)

        # IGDB search is fuzzy so no need to split the search term by special characters
        if not rom:
            return fallback_rom

        return build_igdb_rom(self, rom, get_igdb_preferred_locale())

    async def get_rom_by_id(self, igdb_id: int) -> IGDBRom:
        if not self.is_enabled():
            return IGDBRom(igdb_id=None)

        roms = await self.igdb_service.list_games(
            fields=GAMES_FIELDS,
            where=f"id={igdb_id}",
            limit=self.pagination_limit,
        )
        if not roms:
            return IGDBRom(igdb_id=None)

        return build_igdb_rom(self, roms[0], get_igdb_preferred_locale())

    async def get_matched_rom_by_id(self, igdb_id: int) -> IGDBRom | None:
        if not self.is_enabled():
            return None

        rom = await self.get_rom_by_id(igdb_id)
        return rom if rom["igdb_id"] else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_igdb_id: int | None
    ) -> list[IGDBRom]:
        if not self.is_enabled():
            return []

        if not platform_igdb_id:
            return []

        matched_roms = await self.igdb_service.list_games(
            search_term=search_term,
            fields=GAMES_FIELDS,
            where=f"platforms=[{platform_igdb_id}]",
            limit=self.pagination_limit,
        )

        alternative_matched_roms = await self.igdb_service.search(
            fields=SEARCH_FIELDS,
            where=f'game.platforms=[{platform_igdb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*)',
            limit=self.pagination_limit,
        )

        if alternative_matched_roms:
            id_filter = " | ".join(
                list(
                    map(
                        lambda rom: (
                            f'id={pydash.get(rom, "game.id", "")}'
                            if "game" in rom.keys()
                            else f'id={rom.get("id", "")}'
                        ),
                        alternative_matched_roms,
                    )
                )
            )
            alternative_roms = await self.igdb_service.list_games(
                fields=GAMES_FIELDS,
                where=id_filter,
                limit=self.pagination_limit,
            )
            matched_roms.extend(alternative_roms)

        # Use a dictionary to keep track of unique ids
        unique_ids: dict[int, Game] = {}

        # Use a list comprehension to filter duplicates based on the 'id' key
        matched_roms = [
            unique_ids.setdefault(rom["id"], rom)
            for rom in matched_roms
            if rom["id"] not in unique_ids
        ]

        preferred_locale = get_igdb_preferred_locale()
        return [build_igdb_rom(self, rom, preferred_locale) for rom in matched_roms]


class TwitchAuth(MetadataHandler):
    def __init__(self):
        self.BASE_URL = "https://id.twitch.tv/oauth2/token"
        self.params = {
            "client_id": IGDB_CLIENT_ID,
            "client_secret": IGDB_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
        self.masked_params = self._mask_sensitive_values(self.params)
        self.timeout = 10

    @classmethod
    def is_enabled(cls) -> bool:
        return IGDBHandler.is_enabled()

    async def _update_twitch_token(self) -> str:
        if not self.is_enabled():
            return ""

        token = None
        expires_in = 0

        httpx_client = ctx_httpx_client.get()
        try:
            log.debug(
                "API request: URL=%s, Params=%s, Timeout=%s",
                self.BASE_URL,
                self.masked_params,
                self.timeout,
            )
            res = await httpx_client.post(
                url=self.BASE_URL,
                params=self.params,
                timeout=self.timeout,
            )

            if res.status_code == status.HTTP_400_BAD_REQUEST:
                log.critical("IGDB Error: Invalid IGDB_CLIENT_ID or IGDB_CLIENT_SECRET")
                return ""

            response_json = res.json()
            token = response_json.get("access_token", "")
            expires_in = response_json.get("expires_in", 0)
        except httpx.NetworkError:
            log.critical("Can't connect to IGDB, check your internet connection.")
            return ""

        if not token or expires_in == 0:
            return ""

        # Set token in Redis to expire some seconds before it actually expires.
        await async_cache.set("romm:twitch_token", token, ex=expires_in - 10)

        log.info("Twitch token fetched!")

        return token

    async def get_oauth_token(self) -> str:
        # Use a fake token when running tests
        if IS_PYTEST_RUN:
            return "test_token"

        if not self.is_enabled():
            return ""

        # Fetch the token cache
        token = await async_cache.get("romm:twitch_token")
        if not token:
            log.info("Twitch token invalid: fetching a new one...")
            return await self._update_twitch_token()

        return token


SEARCH_FIELDS = ("game.id", "name")

GAMES_FIELDS = (
    "id",
    "name",
    "slug",
    "summary",
    "total_rating",
    "aggregated_rating",
    "first_release_date",
    "artworks.url",
    "cover.url",
    "screenshots.url",
    "platforms.id",
    "platforms.name",
    "alternative_names.name",
    "genres.name",
    "franchise.name",
    "franchises.name",
    "collections.name",
    "game_modes.name",
    "involved_companies.company.name",
    "expansions.id",
    "expansions.slug",
    "expansions.name",
    "expansions.cover.url",
    "expanded_games.id",
    "expanded_games.slug",
    "expanded_games.name",
    "expanded_games.cover.url",
    "dlcs.id",
    "dlcs.name",
    "dlcs.slug",
    "dlcs.cover.url",
    "remakes.id",
    "remakes.slug",
    "remakes.name",
    "remakes.cover.url",
    "remasters.id",
    "remasters.slug",
    "remasters.name",
    "remasters.cover.url",
    "ports.id",
    "ports.slug",
    "ports.name",
    "ports.cover.url",
    "similar_games.id",
    "similar_games.slug",
    "similar_games.name",
    "similar_games.cover.url",
    "age_ratings.rating_category",
    "videos.video_id",
    "game_localizations.id",
    "game_localizations.name",
    "game_localizations.cover.url",
    "game_localizations.region.identifier",
    "game_localizations.region.category",
)


IGDB_PLATFORM_CATEGORIES: dict[int, str] = {
    0: "Unknown",
    1: "Console",
    2: "Arcade",
    3: "Platform",
    4: "Operating System",
    5: "Portable Console",
    6: "Computer",
}

IGDB_AGE_RATING_ORGS: dict[int, str] = {
    0: "Unknown",
    1: "ESRB",
    2: "PEGI",
    3: "CERO",
    4: "USK",
    5: "GRAC",
    6: "CLASS_IND",
    7: "ACB",
}

IGDB_AGE_RATINGS: dict[int, IGDBAgeRating] = {
    1: {
        "rating": "RP",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_rp.png",
    },
    2: {
        "rating": "EC",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_ec.png",
    },
    3: {
        "rating": "E",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_e.png",
    },
    4: {
        "rating": "E10+",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_e10.png",
    },
    5: {
        "rating": "T",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_t.png",
    },
    6: {
        "rating": "M",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_m.png",
    },
    7: {
        "rating": "AO",
        "category": IGDB_AGE_RATING_ORGS[1],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_ao.png",
    },
    8: {
        "rating": "3",
        "category": IGDB_AGE_RATING_ORGS[2],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_3.png",
    },
    9: {
        "rating": "7",
        "category": IGDB_AGE_RATING_ORGS[2],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_7.png",
    },
    10: {
        "rating": "12",
        "category": IGDB_AGE_RATING_ORGS[2],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_12.png",
    },
    11: {
        "rating": "16",
        "category": IGDB_AGE_RATING_ORGS[2],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_16.png",
    },
    12: {
        "rating": "18",
        "category": IGDB_AGE_RATING_ORGS[2],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_18.png",
    },
    13: {
        "rating": "A",
        "category": IGDB_AGE_RATING_ORGS[3],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_a.png",
    },
    14: {
        "rating": "B",
        "category": IGDB_AGE_RATING_ORGS[3],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_b.png",
    },
    15: {
        "rating": "C",
        "category": IGDB_AGE_RATING_ORGS[3],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_c.png",
    },
    16: {
        "rating": "D",
        "category": IGDB_AGE_RATING_ORGS[3],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_d.png",
    },
    17: {
        "rating": "Z",
        "category": IGDB_AGE_RATING_ORGS[3],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_z.png",
    },
    18: {
        "rating": "0",
        "category": IGDB_AGE_RATING_ORGS[4],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_0.png",
    },
    19: {
        "rating": "6",
        "category": IGDB_AGE_RATING_ORGS[4],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_6.png",
    },
    20: {
        "rating": "12",
        "category": IGDB_AGE_RATING_ORGS[4],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_12.png",
    },
    21: {
        "rating": "16",
        "category": IGDB_AGE_RATING_ORGS[4],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_16.png",
    },
    22: {
        "rating": "18",
        "category": IGDB_AGE_RATING_ORGS[4],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_18.png",
    },
    23: {
        "rating": "ALL",
        "category": IGDB_AGE_RATING_ORGS[5],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_all.png",
    },
    24: {
        "rating": "12+",
        "category": IGDB_AGE_RATING_ORGS[5],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_12.png",
    },
    25: {
        "rating": "15+",
        "category": IGDB_AGE_RATING_ORGS[5],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_15.png",
    },
    26: {
        "rating": "19+",
        "category": IGDB_AGE_RATING_ORGS[5],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_19.png",
    },
    27: {
        "rating": "TESTING",
        "category": IGDB_AGE_RATING_ORGS[5],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_testing.png",
    },
    28: {
        "rating": "L",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_l.png",
    },
    29: {
        "rating": "10",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_10.png",
    },
    30: {
        "rating": "12",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_12.png",
    },
    31: {
        "rating": "14",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_14.png",
    },
    32: {
        "rating": "16",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_16.png",
    },
    33: {
        "rating": "18",
        "category": IGDB_AGE_RATING_ORGS[6],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_18.png",
    },
    34: {
        "rating": "G",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_g.png",
    },
    35: {
        "rating": "PG",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_pg.png",
    },
    36: {
        "rating": "M",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_m.png",
    },
    37: {
        "rating": "MA 15+",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_ma15.png",
    },
    38: {
        "rating": "R 18+",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_r18.png",
    },
    39: {
        "rating": "RC",
        "category": IGDB_AGE_RATING_ORGS[7],
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_rc.png",
    },
}


class SlugToIGDB(TypedDict):
    id: int
    slug: str
    name: str
    category: str
    generation: int
    family_name: str
    family_slug: str
    url: str
    url_logo: str


IGDB_PLATFORM_LIST: dict[UPS, SlugToIGDB] = {
    UPS.APVS: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 2,
        "id": 139,
        "name": "1292 Advanced Programmable Video System",
        "slug": "1292-advanced-programmable-video-system",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yfdqsudagw0av25dawjr.jpg",
    },
    UPS._3DO: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 5,
        "id": 50,
        "name": "3DO Interactive Multiplayer",
        "slug": "3do",
        "url": "https://www.igdb.com/platforms/3do",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7u.jpg",
    },
    UPS.N3DS: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 8,
        "id": 37,
        "name": "Nintendo 3DS",
        "slug": "3ds",
        "url": "https://www.igdb.com/platforms/3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln6.jpg",
    },
    UPS.N64DD: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 5,
        "id": 416,
        "name": "Nintendo 64DD",
        "slug": "64dd",
        "url": "https://www.igdb.com/platforms/64dd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj8.jpg",
    },
    UPS.ACORN_ARCHIMEDES: {
        "category": "Computer",
        "family_name": "Acorn",
        "family_slug": "acorn",
        "generation": -1,
        "id": 116,
        "name": "Acorn Archimedes",
        "slug": "acorn-archimedes",
        "url": "https://www.igdb.com/platforms/acorn-archimedes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plas.jpg",
    },
    UPS.ACORN_ELECTRON: {
        "category": "Computer",
        "family_name": "Acorn",
        "family_slug": "acorn",
        "generation": -1,
        "id": 134,
        "name": "Acorn Electron",
        "slug": "acorn-electron",
        "url": "https://www.igdb.com/platforms/acorn-electron",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8d.jpg",
    },
    UPS.ACPC: {
        "category": "Computer",
        "family_name": "Amstrad",
        "family_slug": "amstrad",
        "generation": -1,
        "id": 25,
        "name": "Amstrad CPC",
        "slug": "acpc",
        "url": "https://www.igdb.com/platforms/acpc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnh.jpg",
    },
    UPS.ADVANCED_PICO_BEENA: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 6,
        "id": 507,
        "name": "Advanced Pico Beena",
        "slug": "advanced-pico-beena",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plou.jpg",
    },
    UPS.AIRCONSOLE: {
        "category": "Platform",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 389,
        "name": "AirConsole",
        "slug": "airconsole",
        "url": "https://www.igdb.com/platforms/airconsole",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkq.jpg",
    },
    UPS.AMAZON_FIRE_TV: {
        "category": "Platform",
        "family_name": "Amazon",
        "family_slug": "amazon",
        "generation": -1,
        "id": 132,
        "name": "Amazon Fire TV",
        "slug": "amazon-fire-tv",
        "url": "https://www.igdb.com/platforms/amazon-fire-tv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl91.jpg",
    },
    UPS.AMIGA: {
        "category": "Computer",
        "family_name": "Amiga",
        "family_slug": "amiga",
        "generation": -1,
        "id": 16,
        "name": "Amiga",
        "slug": "amiga",
        "url": "https://www.igdb.com/platforms/amiga",
        "url_logo": "",
    },
    UPS.AMIGA_CD32: {
        "category": "Console",
        "family_name": "Amiga",
        "family_slug": "amiga",
        "generation": 5,
        "id": 114,
        "name": "Amiga CD32",
        "slug": "amiga-cd32",
        "url": "https://www.igdb.com/platforms/amiga-cd32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7v.jpg",
    },
    UPS.AMSTRAD_GX4000: {
        "category": "Console",
        "family_name": "Amstrad",
        "family_slug": "amstrad",
        "generation": 3,
        "id": 506,
        "name": "Amstrad GX4000",
        "slug": "amstrad-gx4000",
        "url": "https://www.igdb.com/platforms/amstrad-gx4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plot.jpg",
    },
    UPS.AMSTRAD_PCW: {
        "category": "Computer",
        "family_name": "Amstrad",
        "family_slug": "amstrad",
        "generation": -1,
        "id": 154,
        "name": "Amstrad PCW",
        "slug": "amstrad-pcw",
        "url": "https://www.igdb.com/platforms/amstrad-pcw",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf7.jpg",
    },
    UPS.ANALOGUEELECTRONICS: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 1,
        "id": 100,
        "name": "Analogue electronics",
        "slug": "analogueelectronics",
        "url": "https://www.igdb.com/platforms/analogueelectronics",
        "url_logo": "",
    },
    UPS.ANDROID: {
        "category": "Operating System",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 34,
        "name": "Android",
        "slug": "android",
        "url": "https://www.igdb.com/platforms/android",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln3.jpg",
    },
    UPS.APPLE_IIGS: {
        "category": "Computer",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": -1,
        "id": 115,
        "name": "Apple IIGS",
        "slug": "apple-iigs",
        "url": "https://www.igdb.com/platforms/apple-iigs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl87.jpg",
    },
    UPS.APPLE_PIPPIN: {
        "category": "Console",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": 5,
        "id": 476,
        "name": "Apple Pippin",
        "slug": "apple-pippin",
        "url": "https://www.igdb.com/platforms/apple-pippin",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnn.jpg",
    },
    UPS.APPLEII: {
        "category": "Computer",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": -1,
        "id": 75,
        "name": "Apple II",
        "slug": "appleii",
        "url": "https://www.igdb.com/platforms/appleii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8r.jpg",
    },
    UPS.ARCADE: {
        "category": "Arcade",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 52,
        "name": "Arcade",
        "slug": "arcade",
        "url": "https://www.igdb.com/platforms/arcade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmz.jpg",
    },
    UPS.ARCADIA_2001: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 2,
        "id": 473,
        "name": "Arcadia 2001",
        "slug": "arcadia-2001",
        "url": "https://www.igdb.com/platforms/arcadia-2001",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnk.jpg",
    },
    UPS.ARDUBOY: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 8,
        "id": 438,
        "name": "Arduboy",
        "slug": "arduboy",
        "url": "https://www.igdb.com/platforms/arduboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk6.jpg",
    },
    UPS.ASTROCADE: {
        "category": "Console",
        "family_name": "Bally",
        "family_slug": "bally",
        "generation": 2,
        "id": 91,
        "name": "Bally Astrocade",
        "slug": "astrocade",
        "url": "https://www.igdb.com/platforms/astrocade",
        "url_logo": "",
    },
    UPS.ATARI_JAGUAR_CD: {
        "category": "Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 5,
        "id": 410,
        "name": "Atari Jaguar CD",
        "slug": "atari-jaguar-cd",
        "url": "https://www.igdb.com/platforms/atari-jaguar-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj4.jpg",
    },
    UPS.ATARI_ST: {
        "category": "Computer",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": -1,
        "id": 63,
        "name": "Atari ST/STE",
        "slug": "atari-st",
        "url": "https://www.igdb.com/platforms/atari-st",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla7.jpg",
    },
    UPS.ATARI2600: {
        "category": "Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 2,
        "id": 59,
        "name": "Atari 2600",
        "slug": "atari2600",
        "url": "https://www.igdb.com/platforms/atari2600",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln4.jpg",
    },
    UPS.ATARI5200: {
        "category": "Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 2,
        "id": 66,
        "name": "Atari 5200",
        "slug": "atari5200",
        "url": "https://www.igdb.com/platforms/atari5200",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8g.jpg",
    },
    UPS.ATARI7800: {
        "category": "Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 3,
        "id": 60,
        "name": "Atari 7800",
        "slug": "atari7800",
        "url": "https://www.igdb.com/platforms/atari7800",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8f.jpg",
    },
    UPS.ATARI8BIT: {
        "category": "Computer",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": -1,
        "id": 65,
        "name": "Atari 8-bit",
        "slug": "atari8bit",
        "url": "https://www.igdb.com/platforms/atari8bit",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plad.jpg",
    },
    UPS.AY_3_8500: {
        "category": "Computer",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": -1,
        "id": 140,
        "name": "AY-3-8500",
        "slug": "ay-3-8500",
        "url": "https://www.igdb.com/platforms/ay-3-8500",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/x42zeitpbuo2ltn7ybb2.jpg",
    },
    UPS.AY_3_8603: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 145,
        "name": "AY-3-8603",
        "slug": "ay-3-8603",
        "url": "https://www.igdb.com/platforms/ay-3-8603",
        "url_logo": "",
    },
    UPS.AY_3_8605: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 146,
        "name": "AY-3-8605",
        "slug": "ay-3-8605",
        "url": "https://www.igdb.com/platforms/ay-3-8605",
        "url_logo": "",
    },
    UPS.AY_3_8606: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 147,
        "name": "AY-3-8606",
        "slug": "ay-3-8606",
        "url": "https://www.igdb.com/platforms/ay-3-8606",
        "url_logo": "",
    },
    UPS.AY_3_8607: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 148,
        "name": "AY-3-8607",
        "slug": "ay-3-8607",
        "url": "https://www.igdb.com/platforms/ay-3-8607",
        "url_logo": "",
    },
    UPS.AY_3_8610: {
        "category": "Computer",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 141,
        "name": "AY-3-8610",
        "slug": "ay-3-8610",
        "url": "https://www.igdb.com/platforms/ay-3-8610",
        "url_logo": "",
    },
    UPS.AY_3_8710: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 144,
        "name": "AY-3-8710",
        "slug": "ay-3-8710",
        "url": "https://www.igdb.com/platforms/ay-3-8710",
        "url_logo": "",
    },
    UPS.AY_3_8760: {
        "category": "Console",
        "family_name": "General Instruments",
        "family_slug": "general-instruments",
        "generation": 1,
        "id": 143,
        "name": "AY-3-8760",
        "slug": "ay-3-8760",
        "url": "https://www.igdb.com/platforms/ay-3-8760",
        "url_logo": "",
    },
    UPS.BBCMICRO: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 69,
        "name": "BBC Microcomputer System",
        "slug": "bbcmicro",
        "url": "https://www.igdb.com/platforms/bbcmicro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl86.jpg",
    },
    UPS.BLACKBERRY: {
        "category": "Operating System",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 73,
        "name": "BlackBerry OS",
        "slug": "blackberry",
        "url": "https://www.igdb.com/platforms/blackberry",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/bezbkk17hk0uobdkhjcv.jpg",
    },
    UPS.BLU_RAY_PLAYER: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 7,
        "id": 239,
        "name": "Blu-ray Player",
        "slug": "blu-ray-player",
        "url": "https://www.igdb.com/platforms/blu-ray-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbv.jpg",
    },
    UPS.BROWSER: {
        "category": "Platform",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 82,
        "name": "Browser (Flash/HTML5)",
        "slug": "browser",
        "url": "https://www.igdb.com/platforms/browser",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmx.jpg",
    },
    UPS.C_PLUS_4: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 94,
        "name": "Commodore Plus/4",
        "slug": "c-plus-4",
        "url": "https://www.igdb.com/platforms/c-plus-4",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8m.jpg",
    },
    UPS.C16: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 93,
        "name": "Commodore 16",
        "slug": "c16",
        "url": "https://www.igdb.com/platforms/c16",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf4.jpg",
    },
    UPS.C64: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 15,
        "name": "Commodore C64/128/MAX",
        "slug": "c64",
        "url": "https://www.igdb.com/platforms/c64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
    },
    UPS.CALL_A_COMPUTER: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 107,
        "name": "Call-A-Computer time-shared mainframe computer system",
        "slug": "call-a-computer",
        "url": "https://www.igdb.com/platforms/call-a-computer",
        "url_logo": "",
    },
    UPS.CASIO_LOOPY: {
        "category": "Console",
        "family_name": "Casio",
        "family_slug": "casio",
        "generation": 5,
        "id": 380,
        "name": "Casio Loopy",
        "slug": "casio-loopy",
        "url": "https://www.igdb.com/platforms/casio-loopy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkm.jpg",
    },
    UPS.CDCCYBER70: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 109,
        "name": "CDC Cyber 70",
        "slug": "cdccyber70",
        "url": "https://www.igdb.com/platforms/cdccyber70",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plae.jpg",
    },
    UPS.COLECOVISION: {
        "category": "Console",
        "family_name": "Coleco",
        "family_slug": "coleco",
        "generation": 2,
        "id": 68,
        "name": "ColecoVision",
        "slug": "colecovision",
        "url": "https://www.igdb.com/platforms/colecovision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8n.jpg",
    },
    UPS.COMMODORE_CDTV: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 158,
        "name": "Commodore CDTV",
        "slug": "commodore-cdtv",
        "url": "https://www.igdb.com/platforms/commodore-cdtv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl84.jpg",
    },
    UPS.CPET: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 90,
        "name": "Commodore PET",
        "slug": "cpet",
        "url": "https://www.igdb.com/platforms/cpet",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf3.jpg",
    },
    UPS.DAYDREAM: {
        "category": "Console",
        "family_name": "Google",
        "family_slug": "google",
        "generation": 8,
        "id": 164,
        "name": "Daydream",
        "slug": "daydream",
        "url": "https://www.igdb.com/platforms/daydream",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lwbdsvaveyxmuwnsga7g.jpg",
    },
    UPS.DC: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 6,
        "id": 23,
        "name": "Dreamcast",
        "slug": "dc",
        "url": "https://www.igdb.com/platforms/dc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7i.jpg",
    },
    UPS.DIGIBLAST: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 7,
        "id": 486,
        "name": "Digiblast",
        "slug": "digiblast",
        "url": "https://www.igdb.com/platforms/digiblast",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo2.jpg",
    },
    UPS.DONNER30: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 85,
        "name": "Donner Model 30",
        "slug": "donner30",
        "url": "https://www.igdb.com/platforms/donner30",
        "url_logo": "",
    },
    UPS.DOS: {
        "category": "Operating System",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": -1,
        "id": 13,
        "name": "DOS",
        "slug": "dos",
        "url": "https://www.igdb.com/platforms/dos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/sqgw6vespav1buezgjjn.jpg",
    },
    UPS.DRAGON_32_SLASH_64: {
        "category": "Computer",
        "family_name": "Dragon Data",
        "family_slug": "dragon-data",
        "generation": -1,
        "id": 153,
        "name": "Dragon 32/64",
        "slug": "dragon-32-slash-64",
        "url": "https://www.igdb.com/platforms/dragon-32-slash-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8e.jpg",
    },
    UPS.DVD_PLAYER: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 6,
        "id": 238,
        "name": "DVD Player",
        "slug": "dvd-player",
        "url": "https://www.igdb.com/platforms/dvd-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbu.jpg",
    },
    UPS.E_READER_SLASH_CARD_E_READER: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 6,
        "id": 510,
        "name": "e-Reader / Card-e Reader",
        "slug": "e-reader-slash-card-e-reader",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploy.jpg",
    },
    UPS.EDSAC: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 102,
        "name": "EDSAC",
        "slug": "edsac--1",
        "url": "https://www.igdb.com/platforms/edsac--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plat.jpg",
    },
    UPS.ELEKTOR: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 505,
        "name": "Elektor TV Games Computer",
        "slug": "elektor-tv-games-computer",
        "url": "https://www.igdb.com/platforms/elektor-tv-games-computer",
        "url_logo": "",
    },
    UPS.EPOCH_CASSETTE_VISION: {
        "category": "Console",
        "family_name": "Epoch",
        "family_slug": "epoch",
        "generation": 2,
        "id": 375,
        "name": "Epoch Cassette Vision",
        "slug": "epoch-cassette-vision",
        "url": "https://www.igdb.com/platforms/epoch-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plko.jpg",
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "category": "Console",
        "family_name": "Epoch",
        "family_slug": "epoch",
        "generation": 3,
        "id": 376,
        "name": "Epoch Super Cassette Vision",
        "slug": "epoch-super-cassette-vision",
        "url": "https://www.igdb.com/platforms/epoch-super-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkn.jpg",
    },
    UPS.EVERCADE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 8,
        "id": 309,
        "name": "Evercade",
        "slug": "evercade",
        "url": "https://www.igdb.com/platforms/evercade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plky.jpg",
    },
    UPS.EXIDY_SORCERER: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 236,
        "name": "Exidy Sorcerer",
        "slug": "exidy-sorcerer",
        "url": "https://www.igdb.com/platforms/exidy-sorcerer",
        "url_logo": "",
    },
    UPS.FAIRCHILD_CHANNEL_F: {
        "category": "Console",
        "family_name": "Fairchild",
        "family_slug": "fairchild",
        "generation": 2,
        "id": 127,
        "name": "Fairchild Channel F",
        "slug": "fairchild-channel-f",
        "url": "https://www.igdb.com/platforms/fairchild-channel-f",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8s.jpg",
    },
    UPS.FAMICOM: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 3,
        "id": 99,
        "name": "Family Computer",
        "slug": "famicom",
        "url": "https://www.igdb.com/platforms/famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnf.jpg",
    },
    UPS.FDS: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 3,
        "id": 51,
        "name": "Family Computer Disk System",
        "slug": "fds",
        "url": "https://www.igdb.com/platforms/fds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8b.jpg",
    },
    UPS.FM_7: {
        "category": "Computer",
        "family_name": "Fujitsu",
        "family_slug": "fujitsu",
        "generation": -1,
        "id": 152,
        "name": "FM-7",
        "slug": "fm-7",
        "url": "https://www.igdb.com/platforms/fm-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pley.jpg",
    },
    UPS.FM_TOWNS: {
        "category": "Computer",
        "family_name": "Fujitsu",
        "family_slug": "fujitsu",
        "generation": -1,
        "id": 118,
        "name": "FM Towns",
        "slug": "fm-towns",
        "url": "https://www.igdb.com/platforms/fm-towns",
        "url_logo": "",
    },
    UPS.G_AND_W: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 2,
        "id": 307,
        "name": "Game & Watch",
        "slug": "g-and-w",
        "url": "https://www.igdb.com/platforms/g-and-w",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pler.jpg",
    },
    UPS.GAMATE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 4,
        "id": 378,
        "name": "Gamate",
        "slug": "gamate",
        "url": "https://www.igdb.com/platforms/gamate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plhf.jpg",
    },
    UPS.GAME_DOT_COM: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 5,
        "id": 379,
        "name": "Game.com",
        "slug": "game-dot-com",
        "url": "https://www.igdb.com/platforms/game-dot-com",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgk.jpg",
    },
    UPS.GAMEGEAR: {
        "category": "Portable Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 35,
        "name": "Sega Game Gear",
        "slug": "gamegear",
        "url": "https://www.igdb.com/platforms/gamegear",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7z.jpg",
    },
    UPS.GB: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 4,
        "id": 33,
        "name": "Game Boy",
        "slug": "gb",
        "url": "https://www.igdb.com/platforms/gb",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7m.jpg",
    },
    UPS.GBA: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 6,
        "id": 24,
        "name": "Game Boy Advance",
        "slug": "gba",
        "url": "https://www.igdb.com/platforms/gba",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl74.jpg",
    },
    UPS.GBC: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 5,
        "id": 22,
        "name": "Game Boy Color",
        "slug": "gbc",
        "url": "https://www.igdb.com/platforms/gbc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7l.jpg",
    },
    UPS.GEAR_VR: {
        "category": "Console",
        "family_name": "Samsung",
        "family_slug": "samsung",
        "generation": 8,
        "id": 388,
        "name": "Gear VR",
        "slug": "gear-vr",
        "url": "https://www.igdb.com/platforms/gear-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkj.jpg",
    },
    UPS.GENESIS: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 29,
        "name": "Sega Mega Drive/Genesis",
        "slug": "genesis-slash-megadrive",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive",
        "url_logo": "",
    },
    UPS.GIZMONDO: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 7,
        "id": 474,
        "name": "Gizmondo",
        "slug": "gizmondo",
        "url": "https://www.igdb.com/platforms/gizmondo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnl.jpg",
    },
    UPS.GT40: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 98,
        "name": "DEC GT40",
        "slug": "gt40",
        "url": "https://www.igdb.com/platforms/gt40",
        "url_logo": "",
    },
    UPS.HANDHELD_ELECTRONIC_LCD: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 1,
        "id": 411,
        "name": "Handheld Electronic LCD",
        "slug": "handheld-electronic-lcd",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd",
        "url_logo": "",
    },
    UPS.HP2100: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 104,
        "name": "HP 2100",
        "slug": "hp2100",
        "url": "https://www.igdb.com/platforms/hp2100",
        "url_logo": "",
    },
    UPS.HP3000: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 105,
        "name": "HP 3000",
        "slug": "hp3000",
        "url": "https://www.igdb.com/platforms/hp3000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla9.jpg",
    },
    UPS.HYPER_NEO_GEO_64: {
        "category": "Arcade",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 5,
        "id": 135,
        "name": "Hyper Neo Geo 64",
        "slug": "hyper-neo-geo-64",
        "url": "https://www.igdb.com/platforms/hyper-neo-geo-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ubf1qgytr069wm0ikh0z.jpg",
    },
    UPS.HYPERSCAN: {
        "category": "Console",
        "family_name": "Mattel",
        "family_slug": "mattel",
        "generation": 7,
        "id": 407,
        "name": "HyperScan",
        "slug": "hyperscan",
        "url": "https://www.igdb.com/platforms/hyperscan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj2.jpg",
    },
    UPS.IMLAC_PDS1: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 111,
        "name": "Imlac PDS-1",
        "slug": "imlac-pds1",
        "url": "https://www.igdb.com/platforms/imlac-pds1",
        "url_logo": "",
    },
    UPS.INTELLIVISION: {
        "category": "Console",
        "family_name": "Mattel",
        "family_slug": "mattel",
        "generation": 2,
        "id": 67,
        "name": "Intellivision",
        "slug": "intellivision",
        "url": "https://www.igdb.com/platforms/intellivision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8o.jpg",
    },
    UPS.INTELLIVISION_AMICO: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 9,
        "id": 382,
        "name": "Intellivision Amico",
        "slug": "intellivision-amico",
        "url": "https://www.igdb.com/platforms/intellivision-amico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkp.jpg",
    },
    UPS.IOS: {
        "category": "Operating System",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": -1,
        "id": 39,
        "name": "iOS",
        "slug": "ios",
        "url": "https://www.igdb.com/platforms/ios",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6w.jpg",
    },
    UPS.JAGUAR: {
        "category": "Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 5,
        "id": 62,
        "name": "Atari Jaguar",
        "slug": "jaguar",
        "url": "https://www.igdb.com/platforms/jaguar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7y.jpg",
    },
    UPS.LASERACTIVE: {
        "category": "Console",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": 4,
        "id": 487,
        "name": "LaserActive",
        "slug": "laseractive",
        "url": "https://www.igdb.com/platforms/laseractive",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo4.jpg",
    },
    UPS.LEAPSTER: {
        "category": "Portable Console",
        "family_name": "Leapster",
        "family_slug": "leapster",
        "generation": 6,
        "id": 412,
        "name": "Leapster",
        "slug": "leapster",
        "url": "https://www.igdb.com/platforms/leapster",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj5.jpg",
    },
    UPS.LEAPSTER_EXPLORER_SLASH_LEADPAD_EXPLORER: {
        "category": "Portable Console",
        "family_name": "Leapster",
        "family_slug": "leapster",
        "generation": 7,
        "id": 413,
        "name": "Leapster Explorer/LeadPad Explorer",
        "slug": "leapster-explorer-slash-leadpad-explorer",
        "url": "https://www.igdb.com/platforms/leapster-explorer-slash-leadpad-explorer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plna.jpg",
    },
    UPS.LEAPTV: {
        "category": "Console",
        "family_name": "Leapster",
        "family_slug": "leapster",
        "generation": 8,
        "id": 414,
        "name": "LeapTV",
        "slug": "leaptv",
        "url": "https://www.igdb.com/platforms/leaptv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj6.jpg",
    },
    UPS.LEGACY_COMPUTER: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 409,
        "name": "Legacy Computer",
        "slug": "legacy-computer",
        "url": "https://www.igdb.com/platforms/legacy-computer",
        "url_logo": "",
    },
    UPS.LINUX: {
        "category": "Operating System",
        "family_name": "Linux",
        "family_slug": "linux",
        "generation": -1,
        "id": 3,
        "name": "Linux",
        "slug": "linux",
        "url": "https://www.igdb.com/platforms/linux",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plak.jpg",
    },
    UPS.LYNX: {
        "category": "Portable Console",
        "family_name": "Atari",
        "family_slug": "atari",
        "generation": 4,
        "id": 61,
        "name": "Atari Lynx",
        "slug": "lynx",
        "url": "https://www.igdb.com/platforms/lynx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl82.jpg",
    },
    UPS.MAC: {
        "category": "Operating System",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": -1,
        "id": 14,
        "name": "Mac",
        "slug": "mac",
        "url": "https://www.igdb.com/platforms/mac",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo3.jpg",
    },
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 4,
        "id": 408,
        "name": "Mega Duck/Cougar Boy",
        "slug": "mega-duck-slash-cougar-boy",
        "url": "https://www.igdb.com/platforms/mega-duck-slash-cougar-boy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj3.jpg",
    },
    UPS.META_QUEST_2: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 9,
        "id": 386,
        "name": "Meta Quest 2",
        "slug": "meta-quest-2",
        "url": "https://www.igdb.com/platforms/meta-quest-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll0.jpg",
    },
    UPS.META_QUEST_3: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 9,
        "id": 471,
        "name": "Meta Quest 3",
        "slug": "meta-quest-3",
        "url": "https://www.igdb.com/platforms/meta-quest-3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnb.jpg",
    },
    UPS.MICROCOMPUTER: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 112,
        "name": "Microcomputer",
        "slug": "microcomputer--1",
        "url": "https://www.igdb.com/platforms/microcomputer--1",
        "url_logo": "",
    },
    UPS.MICROVISION: {
        "category": "Portable Console",
        "family_name": "Milton Bradley",
        "family_slug": "milton-bradley",
        "generation": 2,
        "id": 89,
        "name": "Microvision",
        "slug": "microvision--1",
        "url": "https://www.igdb.com/platforms/microvision--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8q.jpg",
    },
    UPS.MOBILE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 7,
        "id": 55,
        "name": "Legacy Mobile Device",
        "slug": "mobile",
        "url": "https://www.igdb.com/platforms/mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnd.jpg",
    },
    UPS.MSX: {
        "category": "Computer",
        "family_name": "ASCII",
        "family_slug": "ascii",
        "generation": -1,
        "id": 27,
        "name": "MSX",
        "slug": "msx",
        "url": "https://www.igdb.com/platforms/msx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8j.jpg",
    },
    UPS.MSX2: {
        "category": "Computer",
        "family_name": "ASCII",
        "family_slug": "ascii",
        "generation": -1,
        "id": 53,
        "name": "MSX2",
        "slug": "msx2",
        "url": "https://www.igdb.com/platforms/msx2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8k.jpg",
    },
    UPS.N64: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 5,
        "id": 4,
        "name": "Nintendo 64",
        "slug": "n64",
        "url": "https://www.igdb.com/platforms/n64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl78.jpg",
    },
    UPS.NDS: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 7,
        "id": 20,
        "name": "Nintendo DS",
        "slug": "nds",
        "url": "https://www.igdb.com/platforms/nds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6t.jpg",
    },
    UPS.NEC_PC_6000_SERIES: {
        "category": "Computer",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": -1,
        "id": 157,
        "name": "NEC PC-6000 Series",
        "slug": "nec-pc-6000-series",
        "url": "https://www.igdb.com/platforms/nec-pc-6000-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaa.jpg",
    },
    UPS.NEO_GEO_CD: {
        "category": "Console",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 4,
        "id": 136,
        "name": "Neo Geo CD",
        "slug": "neo-geo-cd",
        "url": "https://www.igdb.com/platforms/neo-geo-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7t.jpg",
    },
    UPS.NEO_GEO_POCKET: {
        "category": "Portable Console",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 5,
        "id": 119,
        "name": "Neo Geo Pocket",
        "slug": "neo-geo-pocket",
        "url": "https://www.igdb.com/platforms/neo-geo-pocket",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plau.jpg",
    },
    UPS.NEO_GEO_POCKET_COLOR: {
        "category": "Portable Console",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 5,
        "id": 120,
        "name": "Neo Geo Pocket Color",
        "slug": "neo-geo-pocket-color",
        "url": "https://www.igdb.com/platforms/neo-geo-pocket-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7h.jpg",
    },
    UPS.NEOGEOAES: {
        "category": "Console",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 4,
        "id": 80,
        "name": "Neo Geo AES",
        "slug": "neogeoaes",
        "url": "https://www.igdb.com/platforms/neogeoaes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hamfdrgnhenxb2d9g8mh.jpg",
    },
    UPS.NEOGEOMVS: {
        "category": "Arcade",
        "family_name": "SNK",
        "family_slug": "snk",
        "generation": 4,
        "id": 79,
        "name": "Neo Geo MVS",
        "slug": "neogeomvs",
        "url": "https://www.igdb.com/platforms/neogeomvs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/cbhfilmhdgwdql8nzsy0.jpg",
    },
    UPS.NES: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 3,
        "id": 18,
        "name": "Nintendo Entertainment System",
        "slug": "nes",
        "url": "https://www.igdb.com/platforms/nes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmo.jpg",
    },
    UPS.NEW_NINTENDON3DS: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 8,
        "id": 137,
        "name": "New Nintendo 3DS",
        "slug": "new-nintendo-3ds",
        "url": "https://www.igdb.com/platforms/new-nintendo-3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6j.jpg",
    },
    UPS.NGAGE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 6,
        "id": 42,
        "name": "N-Gage",
        "slug": "ngage",
        "url": "https://www.igdb.com/platforms/ngage",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl76.jpg",
    },
    UPS.NGC: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 6,
        "id": 21,
        "name": "Nintendo GameCube",
        "slug": "ngc",
        "url": "https://www.igdb.com/platforms/ngc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7a.jpg",
    },
    UPS.NIMROD: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 101,
        "name": "Ferranti Nimrod Computer",
        "slug": "nimrod",
        "url": "https://www.igdb.com/platforms/nimrod",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaq.jpg",
    },
    UPS.NINTENDO_DSI: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 7,
        "id": 159,
        "name": "Nintendo DSi",
        "slug": "nintendo-dsi",
        "url": "https://www.igdb.com/platforms/nintendo-dsi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6u.jpg",
    },
    UPS.NUON: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 6,
        "id": 122,
        "name": "Nuon",
        "slug": "nuon",
        "url": "https://www.igdb.com/platforms/nuon",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7g.jpg",
    },
    UPS.OCULUS_GO: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 8,
        "id": 387,
        "name": "Oculus Go",
        "slug": "oculus-go",
        "url": "https://www.igdb.com/platforms/oculus-go",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkk.jpg",
    },
    UPS.OCULUS_QUEST: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 8,
        "id": 384,
        "name": "Oculus Quest",
        "slug": "oculus-quest",
        "url": "https://www.igdb.com/platforms/oculus-quest",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plh7.jpg",
    },
    UPS.OCULUS_RIFT: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 7,
        "id": 385,
        "name": "Oculus Rift",
        "slug": "oculus-rift",
        "url": "https://www.igdb.com/platforms/oculus-rift",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln8.jpg",
    },
    UPS.OCULUS_VR: {
        "category": "Console",
        "family_name": "Meta",
        "family_slug": "meta",
        "generation": 7,
        "id": 162,
        "name": "Oculus VR",
        "slug": "oculus-vr",
        "url": "https://www.igdb.com/platforms/oculus-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pivaofe9ll2b8cqfvvbu.jpg",
    },
    UPS.ODYSSEY: {
        "category": "Console",
        "family_name": "Magnavox",
        "family_slug": "magnavox",
        "generation": 1,
        "id": 88,
        "name": "Magnavox Odyssey",
        "slug": "odyssey--1",
        "url": "https://www.igdb.com/platforms/odyssey--1",
        "url_logo": "",
    },
    UPS.ODYSSEY_2: {
        "category": "Computer",
        "family_name": "Magnavox",
        "family_slug": "magnavox",
        "generation": -1,
        "id": 133,
        "name": "Odyssey 2 / Videopac G7000",
        "slug": "odyssey-2-slash-videopac-g7000",
        "url": "https://www.igdb.com/platforms/odyssey-2-slash-videopac-g7000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fqwnmmpanb5se6ebccm3.jpg",
    },
    UPS.ONLIVE_GAME_SYSTEM: {
        "category": "Platform",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 113,
        "name": "OnLive Game System",
        "slug": "onlive-game-system",
        "url": "https://www.igdb.com/platforms/onlive-game-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plan.jpg",
    },
    UPS.OOPARTS: {
        "category": "Platform",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 372,
        "name": "OOParts",
        "slug": "ooparts",
        "url": "https://www.igdb.com/platforms/ooparts",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgi.jpg",
    },
    UPS.OUYA: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 8,
        "id": 72,
        "name": "Ouya",
        "slug": "ouya",
        "url": "https://www.igdb.com/platforms/ouya",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6k.jpg",
    },
    UPS.PALM_OS: {
        "category": "Operating System",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 417,
        "name": "Palm OS",
        "slug": "palm-os",
        "url": "https://www.igdb.com/platforms/palm-os",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj9.jpg",
    },
    UPS.PANASONIC_JUNGLE: {
        "category": "Portable Console",
        "family_name": "Panasonic",
        "family_slug": "panasonic",
        "generation": 8,
        "id": 477,
        "name": "Panasonic Jungle",
        "slug": "panasonic-jungle",
        "url": "https://www.igdb.com/platforms/panasonic-jungle",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnp.jpg",
    },
    UPS.PANASONIC_M2: {
        "category": "Console",
        "family_name": "Panasonic",
        "family_slug": "panasonic",
        "generation": 6,
        "id": 478,
        "name": "Panasonic M2",
        "slug": "panasonic-m2",
        "url": "https://www.igdb.com/platforms/panasonic-m2",
        "url_logo": "",
    },
    UPS.PC_50X_FAMILY: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 1,
        "id": 142,
        "name": "PC-50X Family",
        "slug": "pc-50x-family",
        "url": "https://www.igdb.com/platforms/pc-50x-family",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/dpwrkxrjkuxwqroqwjsw.jpg",
    },
    UPS.PC_8800_SERIES: {
        "category": "Computer",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": -1,
        "id": 125,
        "name": "PC-8800 Series",
        "slug": "pc-8800-series",
        "url": "https://www.igdb.com/platforms/pc-8800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf2.jpg",
    },
    UPS.PC_9800_SERIES: {
        "category": "Computer",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": -1,
        "id": 149,
        "name": "PC-9800 Series",
        "slug": "pc-9800-series",
        "url": "https://www.igdb.com/platforms/pc-9800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla6.jpg",
    },
    UPS.PC_FX: {
        "category": "Console",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": 5,
        "id": 274,
        "name": "PC-FX",
        "slug": "pc-fx",
        "url": "https://www.igdb.com/platforms/pc-fx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf8.jpg",
    },
    UPS.PDP_7: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 103,
        "name": "PDP-7",
        "slug": "pdp-7--1",
        "url": "https://www.igdb.com/platforms/pdp-7--1",
        "url_logo": "",
    },
    UPS.PDP_8: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 97,
        "name": "PDP-8",
        "slug": "pdp-8--1",
        "url": "https://www.igdb.com/platforms/pdp-8--1",
        "url_logo": "",
    },
    UPS.PDP1: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 95,
        "name": "PDP-1",
        "slug": "pdp1",
        "url": "https://www.igdb.com/platforms/pdp1",
        "url_logo": "",
    },
    UPS.PDP10: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 96,
        "name": "PDP-10",
        "slug": "pdp10",
        "url": "https://www.igdb.com/platforms/pdp10",
        "url_logo": "",
    },
    UPS.PDP11: {
        "category": "Computer",
        "family_name": "DEC",
        "family_slug": "dec",
        "generation": -1,
        "id": 108,
        "name": "PDP-11",
        "slug": "pdp11",
        "url": "https://www.igdb.com/platforms/pdp11",
        "url_logo": "",
    },
    UPS.PHILIPS_CD_I: {
        "category": "Console",
        "family_name": "Philips",
        "family_slug": "philips",
        "generation": 4,
        "id": 117,
        "name": "Philips CD-i",
        "slug": "philips-cd-i",
        "url": "https://www.igdb.com/platforms/philips-cd-i",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl80.jpg",
    },
    UPS.PLATO: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 110,
        "name": "PLATO",
        "slug": "plato--1",
        "url": "https://www.igdb.com/platforms/plato--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaf.jpg",
    },
    UPS.PLAYDATE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 9,
        "id": 381,
        "name": "Playdate",
        "slug": "playdate",
        "url": "https://www.igdb.com/platforms/playdate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgx.jpg",
    },
    UPS.PLAYDIA: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 5,
        "id": 308,
        "name": "Playdia",
        "slug": "playdia",
        "url": "https://www.igdb.com/platforms/playdia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ples.jpg",
    },
    UPS.PLUG_AND_PLAY: {
        "category": "Platform",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 377,
        "name": "Plug & Play",
        "slug": "plug-and-play",
        "url": "https://www.igdb.com/platforms/plug-and-play",
        "url_logo": "",
    },
    UPS.POCKETSTATION: {
        "category": "Portable Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 5,
        "id": 441,
        "name": "PocketStation",
        "slug": "pocketstation",
        "url": "https://www.igdb.com/platforms/pocketstation",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkc.jpg",
    },
    UPS.POKEMON_MINI: {
        "category": "Portable Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 6,
        "id": 166,
        "name": "Pokémon mini",
        "slug": "pokemon-mini",
        "url": "https://www.igdb.com/platforms/pokemon-mini",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7f.jpg",
    },
    UPS.POLYMEGA: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 9,
        "id": 509,
        "name": "Polymega",
        "slug": "polymega",
        "url": "https://www.igdb.com/platforms/polymega",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plox.jpg",
    },
    UPS.PSX: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 5,
        "id": 7,
        "name": "PlayStation",
        "slug": "ps",
        "url": "https://www.igdb.com/platforms/ps",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmb.jpg",
    },
    UPS.PS2: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 6,
        "id": 8,
        "name": "PlayStation 2",
        "slug": "ps2",
        "url": "https://www.igdb.com/platforms/ps2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl72.jpg",
    },
    UPS.PS3: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 7,
        "id": 9,
        "name": "PlayStation 3",
        "slug": "ps3",
        "url": "https://www.igdb.com/platforms/ps3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/tuyy1nrqodtmbqajp4jg.jpg",
    },
    UPS.PS4: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 8,
        "id": 48,
        "name": "PlayStation 4",
        "slug": "ps4--1",
        "url": "https://www.igdb.com/platforms/ps4--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6f.jpg",
    },
    UPS.PS5: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 9,
        "id": 167,
        "name": "PlayStation 5",
        "slug": "ps5",
        "url": "https://www.igdb.com/platforms/ps5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plos.jpg",
    },
    UPS.PSP: {
        "category": "Portable Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 7,
        "id": 38,
        "name": "PlayStation Portable",
        "slug": "psp",
        "url": "https://www.igdb.com/platforms/psp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5y.jpg",
    },
    UPS.PSVITA: {
        "category": "Portable Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 8,
        "id": 46,
        "name": "PlayStation Vita",
        "slug": "psvita",
        "url": "https://www.igdb.com/platforms/psvita",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6g.jpg",
    },
    UPS.PSVR: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 8,
        "id": 165,
        "name": "PlayStation VR",
        "slug": "psvr",
        "url": "https://www.igdb.com/platforms/psvr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnc.jpg",
    },
    UPS.PSVR2: {
        "category": "Console",
        "family_name": "Sony",
        "family_slug": "sony",
        "generation": 9,
        "id": 390,
        "name": "PlayStation VR2",
        "slug": "psvr2",
        "url": "https://www.igdb.com/platforms/psvr2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo5.jpg",
    },
    UPS.R_ZONE: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 5,
        "id": 475,
        "name": "R-Zone",
        "slug": "r-zone",
        "url": "https://www.igdb.com/platforms/r-zone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnm.jpg",
    },
    UPS.SATELLAVIEW: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 4,
        "id": 306,
        "name": "Satellaview",
        "slug": "satellaview",
        "url": "https://www.igdb.com/platforms/satellaview",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgj.jpg",
    },
    UPS.SATURN: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 5,
        "id": 32,
        "name": "Sega Saturn",
        "slug": "saturn",
        "url": "https://www.igdb.com/platforms/saturn",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hrmqljpwunky1all3v78.jpg",
    },
    UPS.SCUMMVM: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        # Note: The ID 50501 is a keyword ID (not a platform ID) in IGDB's system
        "id": 50501,
        "name": "ScummVM",
        "slug": "scummvm",
        "url": "https://www.igdb.com/categories/scummvm-compatible",
        "url_logo": "",
    },
    UPS.SDSSIGMA7: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 106,
        "name": "SDS Sigma 7",
        "slug": "sdssigma7",
        "url": "https://www.igdb.com/platforms/sdssigma7",
        "url_logo": "",
    },
    UPS.SEGACD: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 78,
        "name": "Sega CD",
        "slug": "sega-cd",
        "url": "https://www.igdb.com/platforms/sega-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7w.jpg",
    },
    UPS.SEGACD32: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 482,
        "name": "Sega CD 32X",
        "slug": "sega-cd-32x",
        "url": "https://www.igdb.com/platforms/sega-cd-32x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnu.jpg",
    },
    UPS.SEGA_PICO: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 339,
        "name": "Sega Pico",
        "slug": "sega-pico",
        "url": "https://www.igdb.com/platforms/sega-pico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgo.jpg",
    },
    UPS.SEGA32: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 4,
        "id": 30,
        "name": "Sega 32X",
        "slug": "sega32",
        "url": "https://www.igdb.com/platforms/sega32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7r.jpg",
    },
    UPS.SERIES_X_S: {
        "category": "Console",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": 9,
        "id": 169,
        "name": "Xbox Series X/S",
        "slug": "series-x-s",
        "url": "https://www.igdb.com/platforms/series-x-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plfl.jpg",
    },
    UPS.SFAM: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 4,
        "id": 58,
        "name": "Super Famicom",
        "slug": "sfam",
        "url": "https://www.igdb.com/platforms/sfam",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/a9x7xjy4p9sqynrvomcf.jpg",
    },
    UPS.SG1000: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 3,
        "id": 84,
        "name": "SG-1000",
        "slug": "sg1000",
        "url": "https://www.igdb.com/platforms/sg1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmn.jpg",
    },
    UPS.SHARP_MZ_2200: {
        "category": "Computer",
        "family_name": "Sharp",
        "family_slug": "sharp",
        "generation": -1,
        "id": 374,
        "name": "Sharp MZ-2200",
        "slug": "sharp-mz-2200",
        "url": "https://www.igdb.com/platforms/sharp-mz-2200",
        "url_logo": "",
    },
    UPS.SHARP_X68000: {
        "category": "Computer",
        "family_name": "Sharp",
        "family_slug": "sharp",
        "generation": -1,
        "id": 121,
        "name": "Sharp X68000",
        "slug": "sharp-x68000",
        "url": "https://www.igdb.com/platforms/sharp-x68000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8i.jpg",
    },
    UPS.SINCLAIR_QL: {
        "category": "Computer",
        "family_name": "Sinclair",
        "family_slug": "sinclair",
        "generation": -1,
        "id": 406,
        "name": "Sinclair QL",
        "slug": "sinclair-ql",
        "url": "https://www.igdb.com/platforms/sinclair-ql",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plih.jpg",
    },
    UPS.ZX81: {
        "category": "Computer",
        "family_name": "Sinclair",
        "family_slug": "sinclair",
        "generation": -1,
        "id": 373,
        "name": "Sinclair ZX81",
        "slug": "sinclair-zx81",
        "url": "https://www.igdb.com/platforms/sinclair-zx81",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgr.jpg",
    },
    UPS.SMS: {
        "category": "Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 3,
        "id": 64,
        "name": "Sega Master System/Mark III",
        "slug": "sms",
        "url": "https://www.igdb.com/platforms/sms",
        "url_logo": "",
    },
    UPS.SNES: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 4,
        "id": 19,
        "name": "Super Nintendo Entertainment System",
        "slug": "snes",
        "url": "https://www.igdb.com/platforms/snes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ifw2tvdkynyxayquiyk4.jpg",
    },
    UPS.SOL_20: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 237,
        "name": "Sol-20",
        "slug": "sol-20",
        "url": "https://www.igdb.com/platforms/sol-20",
        "url_logo": "",
    },
    UPS.STADIA: {
        "category": "Platform",
        "family_name": "Linux",
        "family_slug": "linux",
        "generation": -1,
        "id": 170,
        "name": "Google Stadia",
        "slug": "stadia",
        "url": "https://www.igdb.com/platforms/stadia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl94.jpg",
    },
    UPS.STEAM_VR: {
        "category": "Platform",
        "family_name": "Valve",
        "family_slug": "valve",
        "generation": 8,
        "id": 163,
        "name": "SteamVR",
        "slug": "steam-vr",
        "url": "https://www.igdb.com/platforms/steam-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ipbdzzx7z3rwuzm9big4.jpg",
    },
    UPS.SUPER_ACAN: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 4,
        "id": 480,
        "name": "Super A'Can",
        "slug": "super-acan",
        "url": "https://www.igdb.com/platforms/super-acan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plns.jpg",
    },
    UPS.SUPER_NES_CD_ROM_SYSTEM: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 4,
        "id": 131,
        "name": "Super NES CD-ROM System",
        "slug": "super-nes-cd-rom-system",
        "url": "https://www.igdb.com/platforms/super-nes-cd-rom-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plep.jpg",
    },
    UPS.SUPERGRAFX: {
        "category": "Console",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": 4,
        "id": 128,
        "name": "PC Engine SuperGrafx",
        "slug": "supergrafx",
        "url": "https://www.igdb.com/platforms/supergrafx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla4.jpg",
    },
    UPS.SWANCRYSTAL: {
        "category": "Portable Console",
        "family_name": "Bandai",
        "family_slug": "bandai",
        "generation": 5,
        "id": 124,
        "name": "SwanCrystal",
        "slug": "swancrystal",
        "url": "https://www.igdb.com/platforms/swancrystal",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8v.jpg",
    },
    UPS.SWITCH: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 8,
        "id": 130,
        "name": "Nintendo Switch",
        "slug": "switch",
        "url": "https://www.igdb.com/platforms/switch",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgu.jpg",
    },
    UPS.SWITCH_2: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 9,
        "id": 508,
        "name": "Nintendo Switch 2",
        "slug": "switch-2",
        "url": "https://www.igdb.com/platforms/switch-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plow.jpg",
    },
    UPS.TATUNG_EINSTEIN: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 155,
        "name": "Tatung Einstein",
        "slug": "tatung-einstein",
        "url": "https://www.igdb.com/platforms/tatung-einstein",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla8.jpg",
    },
    UPS.TEREBIKKO_SLASH_SEE_N_SAY_VIDEO_PHONE: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 479,
        "name": "Terebikko / See 'n Say Video Phone",
        "slug": "terebikko-slash-see-n-say-video-phone",
        "url": "https://www.igdb.com/platforms/terebikko-slash-see-n-say-video-phone",
        "url_logo": "",
    },
    UPS.THOMSON_MO5: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 156,
        "name": "Thomson MO5",
        "slug": "thomson-mo5",
        "url": "https://www.igdb.com/platforms/thomson-mo5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plex.jpg",
    },
    UPS.TI_99: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 129,
        "name": "Texas Instruments TI-99",
        "slug": "ti-99",
        "url": "https://www.igdb.com/platforms/ti-99",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf0.jpg",
    },
    UPS.TOMY_TUTOR_SLASH_PYUTA_SLASH_GRANDSTAND_TUTOR: {
        "category": "Computer",
        "family_name": "",
        "family_slug": "",
        "generation": -1,
        "id": 481,
        "name": "Tomy Tutor / Pyuta / Grandstand Tutor",
        "slug": "tomy-tutor-slash-pyuta-slash-grandstand-tutor",
        "url": "https://www.igdb.com/platforms/tomy-tutor-slash-pyuta-slash-grandstand-tutor",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnt.jpg",
    },
    UPS.TRS_80: {
        "category": "Computer",
        "family_name": "Tandy",
        "family_slug": "tandy",
        "generation": -1,
        "id": 126,
        "name": "TRS-80",
        "slug": "trs-80",
        "url": "https://www.igdb.com/platforms/trs-80",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plac.jpg",
    },
    UPS.TRS_80_COLOR_COMPUTER: {
        "category": "Computer",
        "family_name": "Tandy",
        "family_slug": "tandy",
        "generation": -1,
        "id": 151,
        "name": "TRS-80 Color Computer",
        "slug": "trs-80-color-computer",
        "url": "https://www.igdb.com/platforms/trs-80-color-computer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf1.jpg",
    },
    UPS.TURBOGRAFX_CD: {
        "category": "Computer",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": -1,
        "id": 150,
        "name": "Turbografx-16/PC Engine CD",
        "slug": "turbografx-16-slash-pc-engine-cd",
        "url": "https://www.igdb.com/platforms/turbografx-16-slash-pc-engine-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl83.jpg",
    },
    UPS.TG16: {
        "category": "Console",
        "family_name": "NEC",
        "family_slug": "nec",
        "generation": 4,
        "id": 86,
        "name": "TurboGrafx-16/PC Engine",
        "slug": "turbografx16--1",
        "url": "https://www.igdb.com/platforms/turbografx16--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl88.jpg",
    },
    UPS.UZEBOX: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 9,
        "id": 504,
        "name": "Uzebox",
        "slug": "uzebox",
        "url": "https://www.igdb.com/platforms/uzebox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plor.jpg",
    },
    UPS.VC: {
        "category": "Platform",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": -1,
        "id": 47,
        "name": "Virtual Console",
        "slug": "vc",
        "url": "https://www.igdb.com/platforms/vc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plao.jpg",
    },
    UPS.VC_4000: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 2,
        "id": 138,
        "name": "VC 4000",
        "slug": "vc-4000",
        "url": "https://www.igdb.com/platforms/vc-4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/phikgyfmv1fevj2jhzr5.jpg",
    },
    UPS.VECTREX: {
        "category": "Console",
        "family_name": "Milton Bradley",
        "family_slug": "milton-bradley",
        "generation": 2,
        "id": 70,
        "name": "Vectrex",
        "slug": "vectrex",
        "url": "https://www.igdb.com/platforms/vectrex",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8h.jpg",
    },
    UPS.VIC_20: {
        "category": "Computer",
        "family_name": "Commodore",
        "family_slug": "commodore",
        "generation": -1,
        "id": 71,
        "name": "Commodore VIC-20",
        "slug": "vic-20",
        "url": "https://www.igdb.com/platforms/vic-20",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8p.jpg",
    },
    UPS.VIRTUALBOY: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 5,
        "id": 87,
        "name": "Virtual Boy",
        "slug": "virtualboy",
        "url": "https://www.igdb.com/platforms/virtualboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7s.jpg",
    },
    UPS.VISIONOS: {
        "category": "Operating System",
        "family_name": "Apple",
        "family_slug": "apple",
        "generation": -1,
        "id": 472,
        "name": "visionOS",
        "slug": "visionos",
        "url": "https://www.igdb.com/platforms/visionos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnj.jpg",
    },
    UPS.VISUAL_MEMORY_UNIT_SLASH_VISUAL_MEMORY_SYSTEM: {
        "category": "Portable Console",
        "family_name": "Sega",
        "family_slug": "sega",
        "generation": 6,
        "id": 440,
        "name": "Visual Memory Unit / Visual Memory System",
        "slug": "visual-memory-unit-slash-visual-memory-system",
        "url": "https://www.igdb.com/platforms/visual-memory-unit-slash-visual-memory-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk8.jpg",
    },
    UPS.VSMILE: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 6,
        "id": 439,
        "name": "V.Smile",
        "slug": "vsmile",
        "url": "https://www.igdb.com/platforms/vsmile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk7.jpg",
    },
    UPS.SUPERVISION: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 4,
        "id": 415,
        "name": "Watara/QuickShot Supervision",
        "slug": "watara-slash-quickshot-supervision",
        "url": "https://www.igdb.com/platforms/watara-slash-quickshot-supervision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj7.jpg",
    },
    UPS.WII: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 7,
        "id": 5,
        "name": "Wii",
        "slug": "wii",
        "url": "https://www.igdb.com/platforms/wii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl92.jpg",
    },
    UPS.WIIU: {
        "category": "Console",
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "generation": 8,
        "id": 41,
        "name": "Wii U",
        "slug": "wiiu",
        "url": "https://www.igdb.com/platforms/wiiu",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6n.jpg",
    },
    UPS.WIN: {
        "category": "Operating System",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": -1,
        "id": 6,
        "name": "Windows",
        "slug": "win",
        "url": "https://www.igdb.com/platforms/win",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plim.jpg",
    },
    UPS.WINDOWS_MIXED_REALITY: {
        "category": "Platform",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": 8,
        "id": 161,
        "name": "Windows Mixed Reality",
        "slug": "windows-mixed-reality",
        "url": "https://www.igdb.com/platforms/windows-mixed-reality",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm4.jpg",
    },
    UPS.WINDOWS_MOBILE: {
        "category": "Operating System",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": -1,
        "id": 405,
        "name": "Windows Mobile",
        "slug": "windows-mobile",
        "url": "https://www.igdb.com/platforms/windows-mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkl.jpg",
    },
    UPS.WINPHONE: {
        "category": "Operating System",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": -1,
        "id": 74,
        "name": "Windows Phone",
        "slug": "winphone",
        "url": "https://www.igdb.com/platforms/winphone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla3.jpg",
    },
    UPS.WONDERSWAN: {
        "category": "Portable Console",
        "family_name": "Bandai",
        "family_slug": "bandai",
        "generation": 5,
        "id": 57,
        "name": "WonderSwan",
        "slug": "wonderswan",
        "url": "https://www.igdb.com/platforms/wonderswan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7b.jpg",
    },
    UPS.WONDERSWAN_COLOR: {
        "category": "Portable Console",
        "family_name": "Bandai",
        "family_slug": "bandai",
        "generation": 5,
        "id": 123,
        "name": "WonderSwan Color",
        "slug": "wonderswan-color",
        "url": "https://www.igdb.com/platforms/wonderswan-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl79.jpg",
    },
    UPS.X1: {
        "category": "Computer",
        "family_name": "Sharp",
        "family_slug": "sharp",
        "generation": -1,
        "id": 77,
        "name": "Sharp X1",
        "slug": "x1",
        "url": "https://www.igdb.com/platforms/x1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl89.jpg",
    },
    UPS.XBOX: {
        "category": "Console",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": 6,
        "id": 11,
        "name": "Xbox",
        "slug": "xbox",
        "url": "https://www.igdb.com/platforms/xbox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7e.jpg",
    },
    UPS.XBOX360: {
        "category": "Console",
        "family_name": "Microsoft",
        "family_slug": "microsoft",
        "generation": 7,
        "id": 12,
        "name": "Xbox 360",
        "slug": "xbox360",
        "url": "https://www.igdb.com/platforms/xbox360",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plha.jpg",
    },
    UPS.XBOXONE: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 8,
        "id": 49,
        "name": "Xbox One",
        "slug": "xboxone",
        "url": "https://www.igdb.com/platforms/xboxone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl95.jpg",
    },
    UPS.ZEEBO: {
        "category": "Console",
        "family_name": "",
        "family_slug": "",
        "generation": 7,
        "id": 240,
        "name": "Zeebo",
        "slug": "zeebo",
        "url": "https://www.igdb.com/platforms/zeebo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbx.jpg",
    },
    UPS.ZOD: {
        "category": "Portable Console",
        "family_name": "",
        "family_slug": "",
        "generation": 5,
        "id": 44,
        "name": "Tapwave Zodiac",
        "slug": "zod",
        "url": "https://www.igdb.com/platforms/zod",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lfsdnlko80ftakbugceu.jpg",
    },
    UPS.ZXS: {
        "category": "Computer",
        "family_name": "Sinclair",
        "family_slug": "sinclair",
        "generation": -1,
        "id": 26,
        "name": "ZX Spectrum",
        "slug": "zxs",
        "url": "https://www.igdb.com/platforms/zxs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plab.jpg",
    },
}


class SlugToIGDBVersion(TypedDict):
    id: int
    slug: str
    platform_slug: UPS
    name: str
    url: str
    url_logo: str


IGDB_PLATFORM_VERSIONS: dict[str, SlugToIGDBVersion] = {
    "10": {
        "id": 526,
        "name": "10",
        "platform_slug": UPS.ANDROID,
        "slug": "10",
        "url": "https://www.igdb.com/platforms/android/version/10",
        "url_logo": "",
    },
    "11": {
        "id": 527,
        "name": "11",
        "platform_slug": UPS.ANDROID,
        "slug": "11",
        "url": "https://www.igdb.com/platforms/android/version/11",
        "url_logo": "",
    },
    "12": {
        "id": 528,
        "name": "12",
        "platform_slug": UPS.ANDROID,
        "slug": "12",
        "url": "https://www.igdb.com/platforms/android/version/12",
        "url_logo": "",
    },
    "520-st": {
        "id": 30,
        "name": "520 ST",
        "platform_slug": UPS.ATARI_ST,
        "slug": "520-st",
        "url": "https://www.igdb.com/platforms/atari-st/version/520-st",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla7.jpg",
    },
    "acetronic-mpu-1000": {
        "id": 213,
        "name": "Acetronic MPU-1000",
        "platform_slug": UPS.APVS,
        "slug": "acetronic-mpu-1000",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system/version/acetronic-mpu-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yfdqsudagw0av25dawjr.jpg",
    },
    "advanced-pico-beena": {
        "id": 726,
        "name": "Advanced Pico Beena",
        "platform_slug": UPS.ADVANCED_PICO_BEENA,
        "slug": "advanced-pico-beena",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena/version/advanced-pico-beena",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plou.jpg",
    },
    "aleck-64": {
        "id": 681,
        "name": "Aleck 64",
        "platform_slug": UPS.ARCADE,
        "slug": "aleck-64",
        "url": "https://www.igdb.com/platforms/arcade/version/aleck-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plni.jpg",
    },
    "amiga-a-1000": {
        "id": 110,
        "name": "Amiga A 1000",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-1000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkf.jpg",
    },
    "amiga-a-1200": {
        "id": 522,
        "name": "Amiga A 1200",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-1200",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-1200",
        "url_logo": "",
    },
    "amiga-a-2000": {
        "id": 111,
        "name": "Amiga A 2000",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-2000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-2000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plng.jpg",
    },
    "amiga-a-3000": {
        "id": 112,
        "name": "Amiga A 3000",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-3000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-3000",
        "url_logo": "",
    },
    "amiga-a-3000t": {
        "id": 113,
        "name": "Amiga A 3000T",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-3000t",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-3000t",
        "url_logo": "",
    },
    "amiga-a-500": {
        "id": 19,
        "name": "Amiga A 500",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-500",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-500",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plav.jpg",
    },
    "amiga-a-600": {
        "id": 109,
        "name": "Amiga A 600",
        "platform_slug": UPS.AMIGA,
        "slug": "amiga-a-600",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-600",
        "url_logo": "",
    },
    "amstrad-cpc-6128": {
        "id": 525,
        "name": "Amstrad CPC 6128",
        "platform_slug": UPS.ACPC,
        "slug": "amstrad-cpc-6128",
        "url": "https://www.igdb.com/platforms/acpc/version/amstrad-cpc-6128",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnh.jpg",
    },
    "android-1-dot-0": {
        "id": 541,
        "name": "Android 1.0",
        "platform_slug": UPS.ANDROID,
        "slug": "android-1-dot-0",
        "url": "https://www.igdb.com/platforms/android/version/android-1-dot-0",
        "url_logo": "",
    },
    "android-1-dot-1": {
        "id": 542,
        "name": "Android 1.1",
        "platform_slug": UPS.ANDROID,
        "slug": "android-1-dot-1",
        "url": "https://www.igdb.com/platforms/android/version/android-1-dot-1",
        "url_logo": "",
    },
    "android-13": {
        "id": 672,
        "name": "Android 13",
        "platform_slug": UPS.ANDROID,
        "slug": "android-13",
        "url": "https://www.igdb.com/platforms/android/version/android-13",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln3.jpg",
    },
    "android-cupcake": {
        "id": 543,
        "name": "Android Cupcake",
        "platform_slug": UPS.ANDROID,
        "slug": "android-cupcake",
        "url": "https://www.igdb.com/platforms/android/version/android-cupcake",
        "url_logo": "",
    },
    "android-donut": {
        "id": 544,
        "name": "Android Donut",
        "platform_slug": UPS.ANDROID,
        "slug": "android-donut",
        "url": "https://www.igdb.com/platforms/android/version/android-donut",
        "url_logo": "",
    },
    "android-eclair": {
        "id": 545,
        "name": "Android Eclair",
        "platform_slug": UPS.ANDROID,
        "slug": "android-eclair",
        "url": "https://www.igdb.com/platforms/android/version/android-eclair",
        "url_logo": "",
    },
    "android-froyo": {
        "id": 546,
        "name": "Android Froyo",
        "platform_slug": UPS.ANDROID,
        "slug": "android-froyo",
        "url": "https://www.igdb.com/platforms/android/version/android-froyo",
        "url_logo": "",
    },
    "atari-2600-plus": {
        "id": 673,
        "name": "Atari 2600+",
        "platform_slug": UPS.ATARI2600,
        "slug": "atari-2600-plus",
        "url": "https://www.igdb.com/platforms/atari2600/version/atari-2600-plus",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln4.jpg",
    },
    "atari-400": {
        "id": 27,
        "name": "Atari 400",
        "platform_slug": UPS.ATARI8BIT,
        "slug": "atari-400",
        "url": "https://www.igdb.com/platforms/atari8bit/version/atari-400",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plad.jpg",
    },
    "atari-800": {
        "id": 104,
        "name": "Atari 800",
        "platform_slug": UPS.ATARI8BIT,
        "slug": "atari-800",
        "url": "https://www.igdb.com/platforms/atari8bit/version/atari-800",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl68.jpg",
    },
    "atari-lynx-mkii": {
        "id": 189,
        "name": "Atari Lynx MkII",
        "platform_slug": UPS.LYNX,
        "slug": "atari-lynx-mkii",
        "url": "https://www.igdb.com/platforms/lynx/version/atari-lynx-mkii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl82.jpg",
    },
    "atomiswave": {
        "id": 652,
        "name": "Atomiswave",
        "platform_slug": UPS.ARCADE,
        "slug": "atomiswave",
        "url": "https://www.igdb.com/platforms/arcade/version/atomiswave",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plma.jpg",
    },
    "audiosonic-pp-1292-advanced-programmable-video-system": {
        "id": 197,
        "name": "Audiosonic PP-1292 Advanced Programmable Video System",
        "platform_slug": UPS.APVS,
        "slug": "audiosonic-pp-1292-advanced-programmable-video-system",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system/version/audiosonic-pp-1292-advanced-programmable-video-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/f9a4tll5lnyxhlijvxjy.jpg",
    },
    "beenalite": {
        "id": 727,
        "name": "BeenaLite",
        "platform_slug": UPS.ADVANCED_PICO_BEENA,
        "slug": "beenalite",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena/version/beenalite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plov.jpg",
    },
    "big-sur": {
        "id": 599,
        "name": "Big Sur",
        "platform_slug": UPS.MAC,
        "slug": "big-sur",
        "url": "https://www.igdb.com/platforms/mac/version/big-sur",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plla.jpg",
    },
    "blu-ray-disc": {
        "id": 356,
        "name": "Blu-ray Disc",
        "platform_slug": UPS.BLU_RAY_PLAYER,
        "slug": "blu-ray-disc",
        "url": "https://www.igdb.com/platforms/blu-ray-player/version/blu-ray-disc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbv.jpg",
    },
    "card-e-reader": {
        "id": 735,
        "name": "Card-e Reader",
        "platform_slug": UPS.E_READER_SLASH_CARD_E_READER,
        "slug": "card-e-reader",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader/version/card-e-reader",
        "url_logo": "",
    },
    "cheetah": {
        "id": 45,
        "name": "Cheetah",
        "platform_slug": UPS.MAC,
        "slug": "cheetah",
        "url": "https://www.igdb.com/platforms/mac/version/cheetah",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/eatvxlflfq0lk8p8sp2c.jpg",
    },
    "commodore-64c": {
        "id": 595,
        "name": "Commodore 64C",
        "platform_slug": UPS.C64,
        "slug": "commodore-64c",
        "url": "https://www.igdb.com/platforms/c64/version/commodore-64c",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
    },
    "cpc-464": {
        "id": 20,
        "name": "CPC 464",
        "platform_slug": UPS.ACPC,
        "slug": "cpc-464",
        "url": "https://www.igdb.com/platforms/acpc/version/cpc-464",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/nlizydzqnuzvzfdapqoj.jpg",
    },
    "digiblast": {
        "id": 712,
        "name": "Digiblast",
        "platform_slug": UPS.DIGIBLAST,
        "slug": "digiblast",
        "url": "https://www.igdb.com/platforms/digiblast/version/digiblast",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo2.jpg",
    },
    "dol-101": {
        "id": 121,
        "name": "DOL-101",
        "platform_slug": UPS.NGC,
        "slug": "dol-101",
        "url": "https://www.igdb.com/platforms/ngc/version/dol-101",
        "url_logo": "",
    },
    "dvd": {
        "id": 355,
        "name": "DVD",
        "platform_slug": UPS.DVD_PLAYER,
        "slug": "dvd",
        "url": "https://www.igdb.com/platforms/dvd-player/version/dvd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbu.jpg",
    },
    "e-reader-slash-card-e-reader-plus": {
        "id": 732,
        "name": "e-Reader / Card-e Reader+",
        "platform_slug": UPS.E_READER_SLASH_CARD_E_READER,
        "slug": "e-reader-slash-card-e-reader-plus",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader/version/e-reader-slash-card-e-reader-plus",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploy.jpg",
    },
    "el-capitan": {
        "id": 151,
        "name": "El Capitan",
        "platform_slug": UPS.MAC,
        "slug": "el-capitan",
        "url": "https://www.igdb.com/platforms/mac/version/el-capitan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll8.jpg",
    },
    "epoch-cassette-vision": {
        "id": 493,
        "name": "Epoch Cassette Vision",
        "platform_slug": UPS.EPOCH_CASSETTE_VISION,
        "slug": "epoch-cassette-vision",
        "url": "https://www.igdb.com/platforms/epoch-cassette-vision/version/epoch-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plko.jpg",
    },
    "euzebox": {
        "id": 721,
        "name": "EUzebox",
        "platform_slug": UPS.UZEBOX,
        "slug": "euzebox",
        "url": "https://www.igdb.com/platforms/uzebox/version/euzebox",
        "url_logo": "",
    },
    "evercade-exp": {
        "id": 594,
        "name": "Evercade EXP",
        "platform_slug": UPS.EVERCADE,
        "slug": "evercade-exp",
        "url": "https://www.igdb.com/platforms/evercade/version/evercade-exp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plky.jpg",
    },
    "evercade-vs": {
        "id": 500,
        "name": "Evercade VS",
        "platform_slug": UPS.EVERCADE,
        "slug": "evercade-vs",
        "url": "https://www.igdb.com/platforms/evercade/version/evercade-vs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgm.jpg",
    },
    "ez-games-video-game-system": {
        "id": 623,
        "name": "EZ Games Video Game System",
        "platform_slug": UPS.GENESIS,
        "slug": "ez-games-video-game-system",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/ez-games-video-game-system",
        "url_logo": "",
    },
    "famicom-titler": {
        "id": 646,
        "name": "Famicom Titler",
        "platform_slug": UPS.FAMICOM,
        "slug": "famicom-titler",
        "url": "https://www.igdb.com/platforms/famicom/version/famicom-titler",
        "url_logo": "",
    },
    "famicombox-slash-famicom-station": {
        "id": 648,
        "name": "FamicomBox/Famicom Station",
        "platform_slug": UPS.FAMICOM,
        "slug": "famicombox-slash-famicom-station",
        "url": "https://www.igdb.com/platforms/famicom/version/famicombox-slash-famicom-station",
        "url_logo": "",
    },
    "family-computer": {
        "id": 123,
        "name": "Family Computer",
        "platform_slug": UPS.FAMICOM,
        "slug": "family-computer",
        "url": "https://www.igdb.com/platforms/famicom/version/family-computer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7p.jpg",
    },
    "feature-phone": {
        "id": 514,
        "name": "Feature phone",
        "platform_slug": UPS.MOBILE,
        "slug": "feature-phone",
        "url": "https://www.igdb.com/platforms/mobile/version/feature-phone",
        "url_logo": "",
    },
    "firefox": {
        "id": 660,
        "name": "Firefox",
        "platform_slug": UPS.BROWSER,
        "slug": "firefox",
        "url": "https://www.igdb.com/platforms/browser/version/firefox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmu.jpg",
    },
    "fm-towns-car-marty": {
        "id": 709,
        "name": "FM Towns Car Marty",
        "platform_slug": UPS.FM_TOWNS,
        "slug": "fm-towns-car-marty",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-car-marty",
        "url_logo": "",
    },
    "fm-towns-marty": {
        "id": 707,
        "name": "FM Towns Marty",
        "platform_slug": UPS.FM_TOWNS,
        "slug": "fm-towns-marty",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-marty",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnz.jpg",
    },
    "fm-towns-marty-2": {
        "id": 708,
        "name": "FM Towns Marty 2",
        "platform_slug": UPS.FM_TOWNS,
        "slug": "fm-towns-marty-2",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-marty-2",
        "url_logo": "",
    },
    "froyo-2-2": {
        "id": 7,
        "name": "Froyo 2.2",
        "platform_slug": UPS.ANDROID,
        "slug": "froyo-2-2",
        "url": "https://www.igdb.com/platforms/android/version/froyo-2-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/gvskesmuwhvmtzv2zhny.jpg",
    },
    "game-boy-advance-sp": {
        "id": 193,
        "name": "Game Boy Advance SP",
        "platform_slug": UPS.GBA,
        "slug": "game-boy-advance-sp",
        "url": "https://www.igdb.com/platforms/gba/version/game-boy-advance-sp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7x.jpg",
    },
    "game-boy-light": {
        "id": 182,
        "name": "Game Boy Light",
        "platform_slug": UPS.GB,
        "slug": "game-boy-light",
        "url": "https://www.igdb.com/platforms/gb/version/game-boy-light",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7m.jpg",
    },
    "game-boy-micro": {
        "id": 194,
        "name": "Game Boy Micro",
        "platform_slug": UPS.GBA,
        "slug": "game-boy-micro",
        "url": "https://www.igdb.com/platforms/gba/version/game-boy-micro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl74.jpg",
    },
    "game-boy-pocket": {
        "id": 181,
        "name": "Game Boy Pocket",
        "platform_slug": UPS.GB,
        "slug": "game-boy-pocket",
        "url": "https://www.igdb.com/platforms/gb/version/game-boy-pocket",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7o.jpg",
    },
    "game-television": {
        "id": 644,
        "name": "Game Television",
        "platform_slug": UPS.NES,
        "slug": "game-television",
        "url": "https://www.igdb.com/platforms/nes/version/game-television",
        "url_logo": "",
    },
    "gingerbread-2-3-3": {
        "id": 8,
        "name": "Gingerbread 2.3.3",
        "platform_slug": UPS.ANDROID,
        "slug": "gingerbread-2-3-3",
        "url": "https://www.igdb.com/platforms/android/version/gingerbread-2-3-3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/iftbsii6snn6geq5hi9n.jpg",
    },
    "google-chrome": {
        "id": 659,
        "name": "Google Chrome",
        "platform_slug": UPS.BROWSER,
        "slug": "google-chrome",
        "url": "https://www.igdb.com/platforms/browser/version/google-chrome",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmt.jpg",
    },
    "google-stadia-founders-edition": {
        "id": 285,
        "name": "Google Stadia: Founder's Edition",
        "platform_slug": UPS.STADIA,
        "slug": "google-stadia-founders-edition",
        "url": "https://www.igdb.com/platforms/stadia/version/google-stadia-founders-edition",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl94.jpg",
    },
    "handheld-pc": {
        "id": 539,
        "name": "Handheld PC",
        "platform_slug": UPS.MOBILE,
        "slug": "handheld-pc",
        "url": "https://www.igdb.com/platforms/mobile/version/handheld-pc",
        "url_logo": "",
    },
    "honeycomb-3-2": {
        "id": 9,
        "name": "Honeycomb 3.2",
        "platform_slug": UPS.ANDROID,
        "slug": "honeycomb-3-2",
        "url": "https://www.igdb.com/platforms/android/version/honeycomb-3-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/qkdxwfyrcwhqrnj1hljd.jpg",
    },
    "ice-cream-sandwich": {
        "id": 10,
        "name": "Ice Cream Sandwich",
        "platform_slug": UPS.ANDROID,
        "slug": "ice-cream-sandwich",
        "url": "https://www.igdb.com/platforms/android/version/ice-cream-sandwich",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fxe5fcitcfmnam128xc1.jpg",
    },
    "initial-version": {
        "id": 200,
        "name": "Initial version",
        "platform_slug": UPS.PC_50X_FAMILY,
        "slug": "initial-version",
        "url": "https://www.igdb.com/platforms/pc-50x-family/version/initial-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vckflbrulcehb6qiap6n.jpg",
    },
    "internet-explorer": {
        "id": 655,
        "name": "Internet Explorer",
        "platform_slug": UPS.BROWSER,
        "slug": "internet-explorer",
        "url": "https://www.igdb.com/platforms/browser/version/internet-explorer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmp.jpg",
    },
    "vc-4000": {
        "id": 196,
        "name": "Interton VC 4000",
        "platform_slug": UPS.VC_4000,
        "slug": "interton-vc-4000",
        "url": "https://www.igdb.com/platforms/vc-4000/version/interton-vc-4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/phikgyfmv1fevj2jhzr5.jpg",
    },
    "ique-player": {
        "id": 122,
        "name": "iQue Player",
        "platform_slug": UPS.N64,
        "slug": "ique-player",
        "url": "https://www.igdb.com/platforms/n64/version/ique-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl78.jpg",
    },
    "itt-odyssee": {
        "id": 169,
        "name": "ITT Odyssee",
        "platform_slug": UPS.ODYSSEY,
        "slug": "itt-odyssee",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/itt-odyssee",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8y.jpg",
    },
    "mac": {
        "id": 142,
        "name": "Jaguar",
        "platform_slug": UPS.JAGUAR,
        "slug": "jaguar",
        "url": "https://www.igdb.com/platforms/mac/version/jaguar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fua8zdpguizpoyzfvkou.jpg",
    },
    "jelly-bean-4-1-x-4-3-x": {
        "id": 11,
        "name": "Jelly Bean 4.1.x-4.3.x",
        "platform_slug": UPS.ANDROID,
        "slug": "jelly-bean-4-1-x-4-3-x",
        "url": "https://www.igdb.com/platforms/android/version/jelly-bean-4-1-x-4-3-x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/w4okoupqnolhrymeqznd.jpg",
    },
    "kitkat": {
        "id": 12,
        "name": "KitKat",
        "platform_slug": UPS.ANDROID,
        "slug": "kitkat",
        "url": "https://www.igdb.com/platforms/android/version/kitkat",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/kb9wpjpv0t1dthhuypou.jpg",
    },
    "lcd-based-handhelds": {
        "id": 551,
        "name": "LCD-based handhelds",
        "platform_slug": UPS.HANDHELD_ELECTRONIC_LCD,
        "slug": "lcd-based-handhelds",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/lcd-based-handhelds",
        "url_logo": "",
    },
    "led-based-handheld": {
        "id": 692,
        "name": "LED-based handheld",
        "platform_slug": UPS.HANDHELD_ELECTRONIC_LCD,
        "slug": "led-based-handheld",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/led-based-handheld",
        "url_logo": "",
    },
    "leopard": {
        "id": 145,
        "name": "Leopard",
        "platform_slug": UPS.MAC,
        "slug": "leopard",
        "url": "https://www.igdb.com/platforms/mac/version/leopard",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/db0qv9ovisi8e0isgkby.jpg",
    },
    "lion": {
        "id": 147,
        "name": "Lion",
        "platform_slug": UPS.MAC,
        "slug": "lion",
        "url": "https://www.igdb.com/platforms/mac/version/lion",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yaguodfpr4ucdiakputb.jpg",
    },
    "lollipop": {
        "id": 236,
        "name": "Lollipop",
        "platform_slug": UPS.ANDROID,
        "slug": "lollipop",
        "url": "https://www.igdb.com/platforms/android/version/lollipop",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plah.jpg",
    },
    "mark-iii-soft-desk-10": {
        "id": 665,
        "name": "Mark III Soft Desk 10",
        "platform_slug": UPS.ARCADE,
        "slug": "mark-iii-soft-desk-10",
        "url": "https://www.igdb.com/platforms/arcade/version/mark-iii-soft-desk-10",
        "url_logo": "",
    },
    "mark-iii-soft-desk-5": {
        "id": 666,
        "name": "Mark III Soft Desk 5",
        "platform_slug": UPS.ARCADE,
        "slug": "mark-iii-soft-desk-5",
        "url": "https://www.igdb.com/platforms/arcade/version/mark-iii-soft-desk-5",
        "url_logo": "",
    },
    "marshmallow": {
        "id": 237,
        "name": "Marshmallow",
        "platform_slug": UPS.ANDROID,
        "slug": "marshmallow",
        "url": "https://www.igdb.com/platforms/android/version/marshmallow",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plai.jpg",
    },
    "master-system-girl": {
        "id": 632,
        "name": "Master System Girl",
        "platform_slug": UPS.SMS,
        "slug": "master-system-girl",
        "url": "https://www.igdb.com/platforms/sms/version/master-system-girl",
        "url_logo": "",
    },
    "master-system-super-compact": {
        "id": 630,
        "name": "Master System Super Compact",
        "platform_slug": UPS.SMS,
        "slug": "master-system-super-compact",
        "url": "https://www.igdb.com/platforms/sms/version/master-system-super-compact",
        "url_logo": "",
    },
    "mavericks": {
        "id": 149,
        "name": "Mavericks",
        "platform_slug": UPS.MAC,
        "slug": "mavericks",
        "url": "https://www.igdb.com/platforms/mac/version/mavericks",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lsyardp2tldsqglhscqh.jpg",
    },
    "mega-pc": {
        "id": 625,
        "name": "Mega PC",
        "platform_slug": UPS.GENESIS,
        "slug": "mega-pc",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/mega-pc",
        "url_logo": "",
    },
    "mega-play": {
        "id": 636,
        "name": "Mega Play",
        "platform_slug": UPS.ARCADE,
        "slug": "mega-play",
        "url": "https://www.igdb.com/platforms/arcade/version/mega-play",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm8.jpg",
    },
    "mega-tech-system": {
        "id": 635,
        "name": "Mega-Tech System",
        "platform_slug": UPS.ARCADE,
        "slug": "mega-tech-system",
        "url": "https://www.igdb.com/platforms/arcade/version/mega-tech-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmk.jpg",
    },
    "meta-quest-2": {
        "id": 593,
        "name": "Meta Quest 2",
        "platform_slug": UPS.META_QUEST_2,
        "slug": "meta-quest-2",
        "url": "https://www.igdb.com/platforms/meta-quest-2/version/meta-quest-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll0.jpg",
    },
    "microsoft-edge": {
        "id": 661,
        "name": "Microsoft Edge",
        "platform_slug": UPS.BROWSER,
        "slug": "microsoft-edge",
        "url": "https://www.igdb.com/platforms/browser/version/microsoft-edge",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmv.jpg",
    },
    "monterey": {
        "id": 600,
        "name": "Monterey",
        "platform_slug": UPS.MAC,
        "slug": "monterey",
        "url": "https://www.igdb.com/platforms/mac/version/monterey",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll9.jpg",
    },
    "mountain-lion": {
        "id": 148,
        "name": "Mountain Lion",
        "platform_slug": UPS.MAC,
        "slug": "mountain-lion",
        "url": "https://www.igdb.com/platforms/mac/version/mountain-lion",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vpprk3kkeloztxesyoiv.jpg",
    },
    "ms-dos": {
        "id": 540,
        "name": "MS-DOS",
        "platform_slug": UPS.DOS,
        "slug": "ms-dos",
        "url": "https://www.igdb.com/platforms/dos/version/ms-dos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plix.jpg",
    },
    "my-computer-tv": {
        "id": 645,
        "name": "My Computer TV",
        "platform_slug": UPS.FAMICOM,
        "slug": "my-computer-tv",
        "url": "https://www.igdb.com/platforms/famicom/version/my-computer-tv",
        "url_logo": "",
    },
    "n-gage-qd": {
        "id": 118,
        "name": "N-Gage QD",
        "platform_slug": UPS.NGAGE,
        "slug": "n-gage-qd",
        "url": "https://www.igdb.com/platforms/ngage/version/n-gage-qd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl76.jpg",
    },
    "naomi": {
        "id": 637,
        "name": "NAOMI",
        "platform_slug": UPS.ARCADE,
        "slug": "naomi",
        "url": "https://www.igdb.com/platforms/arcade/version/naomi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmf.jpg",
    },
    "naomi-2": {
        "id": 651,
        "name": "NAOMI 2",
        "platform_slug": UPS.ARCADE,
        "slug": "naomi-2",
        "url": "https://www.igdb.com/platforms/arcade/version/naomi-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm9.jpg",
    },
    "net-yaroze": {
        "id": 654,
        "name": "Net Yaroze",
        "platform_slug": UPS.PSX,
        "slug": "net-yaroze",
        "url": "https://www.igdb.com/platforms/ps/version/net-yaroze",
        "url_logo": "",
    },
    "netscape-navigator": {
        "id": 656,
        "name": "Netscape Navigator",
        "platform_slug": UPS.BROWSER,
        "slug": "netscape-navigator",
        "url": "https://www.igdb.com/platforms/browser/version/netscape-navigator",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmq.jpg",
    },
    "new-famicom": {
        "id": 642,
        "name": "New Famicom",
        "platform_slug": UPS.FAMICOM,
        "slug": "new-famicom",
        "url": "https://www.igdb.com/platforms/famicom/version/new-famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnf.jpg",
    },
    "new-nintendo-3ds-xl": {
        "id": 677,
        "name": "New Nintendo 3DS XL",
        "platform_slug": UPS.NEW_NINTENDON3DS,
        "slug": "new-nintendo-3ds-xl",
        "url": "https://www.igdb.com/platforms/new-nintendo-3ds/version/new-nintendo-3ds-xl",
        "url_logo": "",
    },
    "new-style-nes": {
        "id": 643,
        "name": "New-Style NES",
        "platform_slug": UPS.NES,
        "slug": "new-style-nes",
        "url": "https://www.igdb.com/platforms/nes/version/new-style-nes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmo.jpg",
    },
    "new-style-super-nes-model-sns-101": {
        "id": 97,
        "name": "New-Style Super NES (Model SNS-101)",
        "platform_slug": UPS.SNES,
        "slug": "new-style-super-nes-model-sns-101",
        "url": "https://www.igdb.com/platforms/snes/version/new-style-super-nes-model-sns-101",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/mr2y5qpyhvj1phm5tivg.jpg",
    },
    "nintendo-2ds": {
        "id": 676,
        "name": "Nintendo 2DS",
        "platform_slug": UPS.N3DS,
        "slug": "nintendo-2ds",
        "url": "https://www.igdb.com/platforms/3ds/version/nintendo-2ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln6.jpg",
    },
    "nintendo-3ds-xl-slash-ll": {
        "id": 675,
        "name": "Nintendo 3DS XL/LL",
        "platform_slug": UPS.N3DS,
        "slug": "nintendo-3ds-xl-slash-ll",
        "url": "https://www.igdb.com/platforms/3ds/version/nintendo-3ds-xl-slash-ll",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln5.jpg",
    },
    "nintendo-ds-lite": {
        "id": 190,
        "name": "Nintendo DS Lite",
        "platform_slug": UPS.NDS,
        "slug": "nintendo-ds-lite",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-ds-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pdn0g4fyks0y1v2ckzws.jpg",
    },
    "nintendo-dsi": {
        "id": 191,
        "name": "Nintendo DSi",
        "platform_slug": UPS.NDS,
        "slug": "nintendo-dsi",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-dsi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6s.jpg",
    },
    "nintendo-dsi-xl": {
        "id": 192,
        "name": "Nintendo DSi XL",
        "platform_slug": UPS.NDS,
        "slug": "nintendo-dsi-xl",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-dsi-xl",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6t.jpg",
    },
    "nintendo-super-system": {
        "id": 638,
        "name": "Nintendo Super System",
        "platform_slug": UPS.ARCADE,
        "slug": "nintendo-super-system",
        "url": "https://www.igdb.com/platforms/arcade/version/nintendo-super-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmd.jpg",
    },
    "nintendo-vs-system": {
        "id": 640,
        "name": "Nintendo VS. System",
        "platform_slug": UPS.ARCADE,
        "slug": "nintendo-vs-system",
        "url": "https://www.igdb.com/platforms/arcade/version/nintendo-vs-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmi.jpg",
    },
    "nokia-n-gage-classic": {
        "id": 49,
        "name": "Nokia N-Gage Classic",
        "platform_slug": UPS.NGAGE,
        "slug": "nokia-n-gage-classic",
        "url": "https://www.igdb.com/platforms/ngage/version/nokia-n-gage-classic",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl75.jpg",
    },
    "nougat": {
        "id": 238,
        "name": "Nougat",
        "platform_slug": UPS.ANDROID,
        "slug": "nougat",
        "url": "https://www.igdb.com/platforms/android/version/nougat",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaj.jpg",
    },
    "oculus-quest-2": {
        "id": 507,
        "name": "Oculus Quest 2",
        "platform_slug": UPS.META_QUEST_2,
        "slug": "oculus-quest-2",
        "url": "https://www.igdb.com/platforms/meta-quest-2/version/oculus-quest-2",
        "url_logo": "",
    },
    "oculus-rift-s": {
        "id": 680,
        "name": "Oculus Rift S",
        "platform_slug": UPS.OCULUS_RIFT,
        "slug": "oculus-rift-s",
        "url": "https://www.igdb.com/platforms/oculus-rift/version/oculus-rift-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln9.jpg",
    },
    "odisea-mexico-export": {
        "id": 170,
        "name": "Odisea (Mexico Export)",
        "platform_slug": UPS.ODYSSEY,
        "slug": "odisea-mexico-export",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odisea-mexico-export",
        "url_logo": "",
    },
    "odissea-italian-export": {
        "id": 171,
        "name": "Odissea (Italian Export)",
        "platform_slug": UPS.ODYSSEY,
        "slug": "odissea-italian-export",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odissea-italian-export",
        "url_logo": "",
    },
    "odyssey-export": {
        "id": 167,
        "name": "Odyssey (Export)",
        "platform_slug": UPS.ODYSSEY,
        "slug": "odyssey-export",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-export",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf5.jpg",
    },
    "odyssey-german-export": {
        "id": 168,
        "name": "Odyssey (German Export)",
        "platform_slug": UPS.ODYSSEY,
        "slug": "odyssey-german-export",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-german-export",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf6.jpg",
    },
    "odyssey-us": {
        "id": 101,
        "name": "Odyssey (US)",
        "platform_slug": UPS.ODYSSEY,
        "slug": "odyssey-us",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-us",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8u.jpg",
    },
    "oled-model": {
        "id": 503,
        "name": "OLED Model",
        "platform_slug": UPS.SWITCH,
        "slug": "oled-model",
        "url": "https://www.igdb.com/platforms/switch/version/oled-model",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgu.jpg",
    },
    "opera": {
        "id": 657,
        "name": "Opera",
        "platform_slug": UPS.BROWSER,
        "slug": "opera",
        "url": "https://www.igdb.com/platforms/browser/version/opera",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmr.jpg",
    },
    "opera-gx": {
        "id": 663,
        "name": "Opera GX",
        "platform_slug": UPS.BROWSER,
        "slug": "opera-gx",
        "url": "https://www.igdb.com/platforms/browser/version/opera-gx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmx.jpg",
    },
    "oreo": {
        "id": 239,
        "name": "Oreo",
        "platform_slug": UPS.ANDROID,
        "slug": "oreo",
        "url": "https://www.igdb.com/platforms/android/version/oreo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plag.jpg",
    },
    "original-version": {
        "id": 67,
        "name": "Original version",
        "platform_slug": UPS.SFAM,
        "slug": "original-version",
        "url": "https://www.igdb.com/platforms/sfam/version/original-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7j.jpg",
    },
    "panasonic-q": {
        "id": 125,
        "name": "Panasonic Q",
        "platform_slug": UPS.NGC,
        "slug": "panasonic-q",
        "url": "https://www.igdb.com/platforms/ngc/version/panasonic-q",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jtbbevwj5l6q01pkkned.jpg",
    },
    "panther": {
        "id": 143,
        "name": "Panther",
        "platform_slug": UPS.MAC,
        "slug": "panther",
        "url": "https://www.igdb.com/platforms/mac/version/panther",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lgboqvrjxbhm9crh0gmk.jpg",
    },
    "pie": {
        "id": 320,
        "name": "Pie",
        "platform_slug": UPS.ANDROID,
        "slug": "pie",
        "url": "https://www.igdb.com/platforms/android/version/pie",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plax.jpg",
    },
    "playchoice-10": {
        "id": 641,
        "name": "PlayChoice-10",
        "platform_slug": UPS.ARCADE,
        "slug": "playchoice-10",
        "url": "https://www.igdb.com/platforms/arcade/version/playchoice-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmg.jpg",
    },
    "playstation": {
        "id": 57,
        "name": "PlayStation",
        "platform_slug": UPS.PSX,
        "slug": "playstation",
        "url": "https://www.igdb.com/platforms/ps/version/playstation",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7q.jpg",
    },
    "playstation-3-original": {
        "id": 4,
        "name": "Playstation 3 Original",
        "platform_slug": UPS.PS3,
        "slug": "playstation-3-original",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-original",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6l.jpg",
    },
    "playstation-3-slim": {
        "id": 5,
        "name": "Playstation 3 Slim",
        "platform_slug": UPS.PS3,
        "slug": "playstation-3-slim",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-slim",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6m.jpg",
    },
    "playstation-3-super-slim": {
        "id": 6,
        "name": "Playstation 3 Super Slim",
        "platform_slug": UPS.PS3,
        "slug": "playstation-3-super-slim",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-super-slim",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/tuyy1nrqodtmbqajp4jg.jpg",
    },
    "playstation-4-pro": {
        "id": 179,
        "name": "PlayStation 4 Pro",
        "platform_slug": UPS.PS4,
        "slug": "playstation-4-pro",
        "url": "https://www.igdb.com/platforms/ps4--1/version/playstation-4-pro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6f.jpg",
    },
    "playstation-4-slim": {
        "id": 178,
        "name": "PlayStation 4 Slim",
        "platform_slug": UPS.PS4,
        "slug": "playstation-4-slim",
        "url": "https://www.igdb.com/platforms/ps4--1/version/playstation-4-slim",
        "url_logo": "",
    },
    "playstation-5-pro": {
        "id": 724,
        "name": "PlayStation 5 Pro",
        "platform_slug": UPS.PS5,
        "slug": "playstation-5-pro",
        "url": "https://www.igdb.com/platforms/ps5/version/playstation-5-pro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plos.jpg",
    },
    "playstation-portable-brite": {
        "id": 277,
        "name": "PlayStation Portable Brite",
        "platform_slug": UPS.PSP,
        "slug": "playstation-portable-brite",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-brite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5w.jpg",
    },
    "playstation-portable-go": {
        "id": 278,
        "name": "PlayStation Portable Go",
        "platform_slug": UPS.PSP,
        "slug": "playstation-portable-go",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-go",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6p.jpg",
    },
    "playstation-portable-slim-and-lite": {
        "id": 276,
        "name": "PlayStation Portable Slim & Lite",
        "platform_slug": UPS.PSP,
        "slug": "playstation-portable-slim-and-lite",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-slim-and-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5v.jpg",
    },
    "playstation-portable-street": {
        "id": 279,
        "name": "PlayStation Portable Street",
        "platform_slug": UPS.PSP,
        "slug": "playstation-portable-street",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-street",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5y.jpg",
    },
    "playstation-tv": {
        "id": 275,
        "name": "PlayStation TV",
        "platform_slug": UPS.PSVITA,
        "slug": "playstation-tv",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-tv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6h.jpg",
    },
    "playstation-vita": {
        "id": 60,
        "name": "PlayStation Vita",
        "platform_slug": UPS.PSVITA,
        "slug": "playstation-vita",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-vita",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6g.jpg",
    },
    "playstation-vita-pch-2000": {
        "id": 274,
        "name": "PlayStation Vita (PCH-2000)",
        "platform_slug": UPS.PSVITA,
        "slug": "playstation-vita-pch-2000",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-vita-pch-2000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5z.jpg",
    },
    "pocket-pc-2002": {
        "id": 535,
        "name": "Pocket PC 2002",
        "platform_slug": UPS.WINDOWS_MOBILE,
        "slug": "pocket-pc-2002",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/pocket-pc-2002",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliu.jpg",
    },
    "ps-one": {
        "id": 653,
        "name": "PS One",
        "platform_slug": UPS.PSX,
        "slug": "ps-one",
        "url": "https://www.igdb.com/platforms/ps/version/ps-one",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmb.jpg",
    },
    "psp-1000": {
        "id": 59,
        "name": "PSP-1000",
        "platform_slug": UPS.PSP,
        "slug": "psp-1000",
        "url": "https://www.igdb.com/platforms/psp/version/psp-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6q.jpg",
    },
    "puma": {
        "id": 141,
        "name": "Puma",
        "platform_slug": UPS.MAC,
        "slug": "puma",
        "url": "https://www.igdb.com/platforms/mac/version/puma",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/luxugq3uspac6qqbvqwk.jpg",
    },
    "saba-videoplay": {
        "id": 212,
        "name": "Saba Videoplay",
        "platform_slug": UPS.FAIRCHILD_CHANNEL_F,
        "slug": "saba-videoplay",
        "url": "https://www.igdb.com/platforms/fairchild-channel-f/version/saba-videoplay",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8t.jpg",
    },
    "safari": {
        "id": 658,
        "name": "Safari",
        "platform_slug": UPS.BROWSER,
        "slug": "safari",
        "url": "https://www.igdb.com/platforms/browser/version/safari",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plms.jpg",
    },
    "sears-hockey-pong": {
        "id": 510,
        "name": "Sears Hockey-Pong",
        "platform_slug": UPS.AY_3_8500,
        "slug": "sears-hockey-pong",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/sears-hockey-pong",
        "url_logo": "",
    },
    "sega-alls": {
        "id": 696,
        "name": "Sega ALLS",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-alls",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-alls",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnq.jpg",
    },
    "sega-game-box-9": {
        "id": 631,
        "name": "Sega Game Box 9",
        "platform_slug": UPS.SMS,
        "slug": "sega-game-box-9",
        "url": "https://www.igdb.com/platforms/sms/version/sega-game-box-9",
        "url_logo": "",
    },
    "sega-hikaru": {
        "id": 650,
        "name": "Sega Hikaru",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-hikaru",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-hikaru",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmj.jpg",
    },
    "sega-mark-iii": {
        "id": 629,
        "name": "Sega Mark III",
        "platform_slug": UPS.SMS,
        "slug": "sega-mark-iii",
        "url": "https://www.igdb.com/platforms/sms/version/sega-mark-iii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm6.jpg",
    },
    "sega-master-system": {
        "id": 63,
        "name": "Sega Master System",
        "platform_slug": UPS.SMS,
        "slug": "sega-master-system",
        "url": "https://www.igdb.com/platforms/sms/version/sega-master-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8a.jpg",
    },
    "sega-master-system-ii": {
        "id": 633,
        "name": "Sega Master System II",
        "platform_slug": UPS.SMS,
        "slug": "sega-master-system-ii",
        "url": "https://www.igdb.com/platforms/sms/version/sega-master-system-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plme.jpg",
    },
    "sega-mega-drive-2-slash-genesis": {
        "id": 628,
        "name": "Sega Mega Drive 2/Genesis",
        "platform_slug": UPS.GENESIS,
        "slug": "sega-mega-drive-2-slash-genesis",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-drive-2-slash-genesis",
        "url_logo": "",
    },
    "sega-mega-drive-slash-genesis": {
        "id": 64,
        "name": "Sega Mega Drive/Genesis",
        "platform_slug": UPS.GENESIS,
        "slug": "sega-mega-drive-slash-genesis",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-drive-slash-genesis",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl85.jpg",
    },
    "sega-mega-jet": {
        "id": 624,
        "name": "Sega Mega Jet",
        "platform_slug": UPS.GENESIS,
        "slug": "sega-mega-jet",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-jet",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plne.jpg",
    },
    "sega-neptune": {
        "id": 703,
        "name": "Sega Neptune",
        "platform_slug": UPS.SEGA32,
        "slug": "sega-neptune",
        "url": "https://www.igdb.com/platforms/sega32/version/sega-neptune",
        "url_logo": "",
    },
    "sega-nomad": {
        "id": 626,
        "name": "Sega Nomad",
        "platform_slug": UPS.GENESIS,
        "slug": "sega-nomad",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-nomad",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmc.jpg",
    },
    "sega-ringedge": {
        "id": 667,
        "name": "Sega RingEdge",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-ringedge",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-ringedge",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmz.jpg",
    },
    "sega-system-1": {
        "id": 649,
        "name": "Sega System 1",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-system-1",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-system-1",
        "url_logo": "",
    },
    "sega-system-e": {
        "id": 634,
        "name": "Sega System E",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-system-e",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-system-e",
        "url_logo": "",
    },
    "sega-titan-video": {
        "id": 669,
        "name": "Sega Titan Video",
        "platform_slug": UPS.ARCADE,
        "slug": "sega-titan-video",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-titan-video",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln1.jpg",
    },
    "sg-1000": {
        "id": 91,
        "name": "SG-1000",
        "platform_slug": UPS.SG1000,
        "slug": "sg-1000",
        "url": "https://www.igdb.com/platforms/sg1000/version/sg-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmn.jpg",
    },
    "sg-1000-ii": {
        "id": 92,
        "name": "SG-1000 II",
        "platform_slug": UPS.SG1000,
        "slug": "sg-1000-ii",
        "url": "https://www.igdb.com/platforms/sg1000/version/sg-1000-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/m7lor1sj7g9gnvliwxx8.jpg",
    },
    "sinclair-ql": {
        "id": 524,
        "name": "Sinclair QL",
        "platform_slug": UPS.SINCLAIR_QL,
        "slug": "sinclair-ql",
        "url": "https://www.igdb.com/platforms/sinclair-ql/version/sinclair-ql",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plih.jpg",
    },
    "slimline": {
        "id": 114,
        "name": "Slimline",
        "platform_slug": UPS.PS2,
        "slug": "slimline",
        "url": "https://www.igdb.com/platforms/ps2/version/slimline",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl72.jpg",
    },
    "snow-leopard": {
        "id": 146,
        "name": "Snow Leopard",
        "platform_slug": UPS.MAC,
        "slug": "snow-leopard",
        "url": "https://www.igdb.com/platforms/mac/version/snow-leopard",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jiy43xitvtxfi16wcdyd.jpg",
    },
    "soft-desk-10": {
        "id": 668,
        "name": "Soft Desk 10",
        "platform_slug": UPS.ARCADE,
        "slug": "soft-desk-10",
        "url": "https://www.igdb.com/platforms/arcade/version/soft-desk-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln0.jpg",
    },
    "sonoma": {
        "id": 713,
        "name": "Sonoma",
        "platform_slug": UPS.MAC,
        "slug": "sonoma",
        "url": "https://www.igdb.com/platforms/mac/version/sonoma",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo3.jpg",
    },
    "duplicate-stadia": {
        "id": 319,
        "name": "Stadia",
        "platform_slug": UPS.STADIA,
        "slug": "stadia",
        "url": "https://www.igdb.com/platforms/duplicate-stadia/version/stadia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaw.jpg",
    },
    "starlight-wii-gaming-station": {
        "id": 730,
        "name": "Starlight Wii Gaming Station",
        "platform_slug": UPS.WII,
        "slug": "starlight-wii-gaming-station",
        "url": "https://www.igdb.com/platforms/wii/version/starlight-wii-gaming-station",
        "url_logo": "",
    },
    "super-famicom-box": {
        "id": 639,
        "name": "Super Famicom Box",
        "platform_slug": UPS.SFAM,
        "slug": "super-famicom-box",
        "url": "https://www.igdb.com/platforms/sfam/version/super-famicom-box",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmm.jpg",
    },
    "super-famicom-jr": {
        "id": 98,
        "name": "Super Famicom Jr.",
        "platform_slug": UPS.SFAM,
        "slug": "super-famicom-jr",
        "url": "https://www.igdb.com/platforms/sfam/version/super-famicom-jr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/a9x7xjy4p9sqynrvomcf.jpg",
    },
    "super-famicom-jr-model-shvc-101": {
        "id": 177,
        "name": "Super Famicom Jr. (Model SHVC-101)",
        "platform_slug": UPS.SNES,
        "slug": "super-famicom-jr-model-shvc-101",
        "url": "https://www.igdb.com/platforms/snes/version/super-famicom-jr-model-shvc-101",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ifw2tvdkynyxayquiyk4.jpg",
    },
    "super-famicom-shvc-001": {
        "id": 139,
        "name": "Super Famicom (SHVC-001)",
        "platform_slug": UPS.SNES,
        "slug": "super-famicom-shvc-001",
        "url": "https://www.igdb.com/platforms/snes/version/super-famicom-shvc-001",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jj75e2f0lzrbvtyw56er.jpg",
    },
    "super-nes-cd-rom-system": {
        "id": 174,
        "name": "Super NES CD-ROM System",
        "platform_slug": UPS.SUPER_NES_CD_ROM_SYSTEM,
        "slug": "super-nes-cd-rom-system",
        "url": "https://www.igdb.com/platforms/super-nes-cd-rom-system/version/super-nes-cd-rom-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plep.jpg",
    },
    "super-nintendo-original-european-version": {
        "id": 95,
        "name": "Super Nintendo (original European version)",
        "platform_slug": UPS.SNES,
        "slug": "super-nintendo-original-european-version",
        "url": "https://www.igdb.com/platforms/snes/version/super-nintendo-original-european-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7k.jpg",
    },
    "super-nintendo-original-north-american-version": {
        "id": 68,
        "name": "Super Nintendo (original North American version)",
        "platform_slug": UPS.SNES,
        "slug": "super-nintendo-original-north-american-version",
        "url": "https://www.igdb.com/platforms/snes/version/super-nintendo-original-north-american-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ob1omu1he33vpulatqzv.jpg",
    },
    "swancrystal": {
        "id": 734,
        "name": "SwanCrystal",
        "platform_slug": UPS.WONDERSWAN_COLOR,
        "slug": "swancrystal",
        "url": "https://www.igdb.com/platforms/wonderswan-color/version/swancrystal",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plp0.jpg",
    },
    "switch-lite": {
        "id": 282,
        "name": "Switch Lite",
        "platform_slug": UPS.SWITCH,
        "slug": "switch-lite",
        "url": "https://www.igdb.com/platforms/switch/version/switch-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pleu.jpg",
    },
    "tele-ball": {
        "id": 201,
        "name": "tele-ball",
        "platform_slug": UPS.AY_3_8500,
        "slug": "tele-ball",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yjdciw0jagvnmvzhhubs.jpg",
    },
    "tele-ball-ii": {
        "id": 202,
        "name": "tele-ball II",
        "platform_slug": UPS.AY_3_8500,
        "slug": "tele-ball-ii",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/x42zeitpbuo2ltn7ybb2.jpg",
    },
    "tele-ball-iii": {
        "id": 203,
        "name": "tele-ball III",
        "platform_slug": UPS.AY_3_8500,
        "slug": "tele-ball-iii",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-iii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fzkmxoxkrfwo1by8t9ja.jpg",
    },
    "tele-ball-vii": {
        "id": 204,
        "name": "tele-ball VII",
        "platform_slug": UPS.AY_3_8500,
        "slug": "tele-ball-vii",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-vii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vs8nzlrcte7l9ep2cqy5.jpg",
    },
    "tele-cassetten-game": {
        "id": 205,
        "name": "Tele-Cassetten-Game",
        "platform_slug": UPS.PC_50X_FAMILY,
        "slug": "tele-cassetten-game",
        "url": "https://www.igdb.com/platforms/pc-50x-family/version/tele-cassetten-game",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/dpwrkxrjkuxwqroqwjsw.jpg",
    },
    "telstar": {
        "id": 198,
        "name": "Telstar",
        "platform_slug": UPS.AY_3_8500,
        "slug": "telstar",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/telstar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vgsvdiyyzjeayaooi1fy.jpg",
    },
    "teradrive": {
        "id": 627,
        "name": "Teradrive",
        "platform_slug": UPS.GENESIS,
        "slug": "teradrive",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/teradrive",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm5.jpg",
    },
    "terebikko-cordless": {
        "id": 698,
        "name": "Terebikko Cordless",
        "platform_slug": UPS.TEREBIKKO_SLASH_SEE_N_SAY_VIDEO_PHONE,
        "slug": "terebikko-cordless",
        "url": "https://www.igdb.com/platforms/terebikko-slash-see-n-say-video-phone/version/terebikko-cordless",
        "url_logo": "",
    },
    "texas-instruments-ti-99-slash-4": {
        "id": 172,
        "name": "Texas Instruments TI-99/4",
        "platform_slug": UPS.TI_99,
        "slug": "texas-instruments-ti-99-slash-4",
        "url": "https://www.igdb.com/platforms/ti-99/version/texas-instruments-ti-99-slash-4",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plez.jpg",
    },
    "texas-instruments-ti-99-slash-4a": {
        "id": 427,
        "name": "Texas Instruments TI-99/4A",
        "platform_slug": UPS.TI_99,
        "slug": "texas-instruments-ti-99-slash-4a",
        "url": "https://www.igdb.com/platforms/ti-99/version/texas-instruments-ti-99-slash-4a",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf0.jpg",
    },
    "tiger": {
        "id": 144,
        "name": "Tiger",
        "platform_slug": UPS.MAC,
        "slug": "tiger",
        "url": "https://www.igdb.com/platforms/mac/version/tiger",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jp06zemqemczisfaxsgl.jpg",
    },
    "tlv-k981g-game-vcd-player": {
        "id": 622,
        "name": "TLV-K981G Game VCD Player",
        "platform_slug": UPS.GENESIS,
        "slug": "tlv-k981g-game-vcd-player",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/tlv-k981g-game-vcd-player",
        "url_logo": "",
    },
    "triforce": {
        "id": 664,
        "name": "Triforce",
        "platform_slug": UPS.ARCADE,
        "slug": "triforce",
        "url": "https://www.igdb.com/platforms/arcade/version/triforce",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmy.jpg",
    },
    "turbo-express-slash-pc-engine-gt": {
        "id": 733,
        "name": "Turbo Express/PC Engine GT",
        "platform_slug": UPS.TG16,
        "slug": "turbo-express-slash-pc-engine-gt",
        "url": "https://www.igdb.com/platforms/turbografx16--1/version/turbo-express-slash-pc-engine-gt",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploz.jpg",
    },
    "twin-famicom": {
        "id": 647,
        "name": "Twin Famicom",
        "platform_slug": UPS.FAMICOM,
        "slug": "twin-famicom",
        "url": "https://www.igdb.com/platforms/famicom/version/twin-famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plml.jpg",
    },
    "vectrex": {
        "id": 70,
        "name": "Vectrex",
        "platform_slug": UPS.VECTREX,
        "slug": "vectrex",
        "url": "https://www.igdb.com/platforms/vectrex/version/vectrex",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8h.jpg",
    },
    "ventura": {
        "id": 598,
        "name": "Ventura",
        "platform_slug": UPS.MAC,
        "slug": "ventura",
        "url": "https://www.igdb.com/platforms/mac/version/ventura",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll5.jpg",
    },
    "vfd-based-handhelds": {
        "id": 691,
        "name": "VFD-based handhelds",
        "platform_slug": UPS.HANDHELD_ELECTRONIC_LCD,
        "slug": "vfd-based-handhelds",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/vfd-based-handhelds",
        "url_logo": "",
    },
    "vivaldi": {
        "id": 662,
        "name": "Vivaldi",
        "platform_slug": UPS.BROWSER,
        "slug": "vivaldi",
        "url": "https://www.igdb.com/platforms/browser/version/vivaldi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmw.jpg",
    },
    "vt01": {
        "id": 686,
        "name": "VT01",
        "platform_slug": UPS.PLUG_AND_PLAY,
        "slug": "vt01",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt01",
        "url_logo": "",
    },
    "vt02": {
        "id": 684,
        "name": "VT02",
        "platform_slug": UPS.PLUG_AND_PLAY,
        "slug": "vt02",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt02",
        "url_logo": "",
    },
    "vt03": {
        "id": 685,
        "name": "VT03",
        "platform_slug": UPS.PLUG_AND_PLAY,
        "slug": "vt03",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt03",
        "url_logo": "",
    },
    "vt09": {
        "id": 687,
        "name": "VT09",
        "platform_slug": UPS.PLUG_AND_PLAY,
        "slug": "vt09",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt09",
        "url_logo": "",
    },
    "vt32": {
        "id": 688,
        "name": "VT32",
        "platform_slug": UPS.PLUG_AND_PLAY,
        "slug": "vt32",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt32",
        "url_logo": "",
    },
    "web-browser": {
        "id": 86,
        "name": "Browser (Flash/HTML5)",
        "platform_slug": UPS.BROWSER,
        "slug": "web-browser",
        "url": "https://www.igdb.com/platforms/browser/version/web-browser",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plal.jpg",
    },
    "wii-family-edition": {
        "id": 731,
        "name": "Wii Family Edition",
        "platform_slug": UPS.WII,
        "slug": "wii-family-edition",
        "url": "https://www.igdb.com/platforms/wii/version/wii-family-edition",
        "url_logo": "",
    },
    "wii-mini": {
        "id": 283,
        "name": "Wii mini",
        "platform_slug": UPS.WII,
        "slug": "wii-mini",
        "url": "https://www.igdb.com/platforms/wii/version/wii-mini",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl92.jpg",
    },
    "windows-1-dot-0": {
        "id": 529,
        "name": "Windows 1.0",
        "platform_slug": UPS.WIN,
        "slug": "windows-1-dot-0",
        "url": "https://www.igdb.com/platforms/win/version/windows-1-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plin.jpg",
    },
    "windows-10": {
        "id": 124,
        "name": "Windows 10",
        "platform_slug": UPS.WIN,
        "slug": "windows-10",
        "url": "https://www.igdb.com/platforms/win/version/windows-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/irwvwpl023f8y19tidgq.jpg",
    },
    "windows-10-mobile": {
        "id": 227,
        "name": "Windows 10 Mobile",
        "platform_slug": UPS.WINPHONE,
        "slug": "windows-10-mobile",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-10-mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla3.jpg",
    },
    "windows-11": {
        "id": 513,
        "name": "Windows 11",
        "platform_slug": UPS.WIN,
        "slug": "windows-11",
        "url": "https://www.igdb.com/platforms/win/version/windows-11",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plim.jpg",
    },
    "windows-2-dot-0": {
        "id": 530,
        "name": "Windows 2.0",
        "platform_slug": UPS.WIN,
        "slug": "windows-2-dot-0",
        "url": "https://www.igdb.com/platforms/win/version/windows-2-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plio.jpg",
    },
    "windows-3-dot-0": {
        "id": 531,
        "name": "Windows 3.0",
        "platform_slug": UPS.WIN,
        "slug": "windows-3-dot-0",
        "url": "https://www.igdb.com/platforms/win/version/windows-3-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plip.jpg",
    },
    "windows-7": {
        "id": 1,
        "name": "Windows 7",
        "platform_slug": UPS.WIN,
        "slug": "windows-7",
        "url": "https://www.igdb.com/platforms/win/version/windows-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pvjzmgepkxhwvgrgmazj.jpg",
    },
    "windows-8": {
        "id": 15,
        "name": "Windows 8",
        "platform_slug": UPS.WIN,
        "slug": "windows-8",
        "url": "https://www.igdb.com/platforms/win/version/windows-8",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/itdndmarjfphtsppnlfh.jpg",
    },
    "windows-95": {
        "id": 532,
        "name": "Windows 95",
        "platform_slug": UPS.WIN,
        "slug": "windows-95",
        "url": "https://www.igdb.com/platforms/win/version/windows-95",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliq.jpg",
    },
    "windows-98": {
        "id": 533,
        "name": "Windows 98",
        "platform_slug": UPS.WIN,
        "slug": "windows-98",
        "url": "https://www.igdb.com/platforms/win/version/windows-98",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plir.jpg",
    },
    "windows-me": {
        "id": 534,
        "name": "Windows Me",
        "platform_slug": UPS.WIN,
        "slug": "windows-me",
        "url": "https://www.igdb.com/platforms/win/version/windows-me",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plis.jpg",
    },
    "windows-mobile-2003": {
        "id": 536,
        "name": "Windows Mobile 2003",
        "platform_slug": UPS.WINDOWS_MOBILE,
        "slug": "windows-mobile-2003",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-2003",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliv.jpg",
    },
    "windows-mobile-5-dot-0": {
        "id": 537,
        "name": "Windows Mobile 5.0",
        "platform_slug": UPS.WINDOWS_MOBILE,
        "slug": "windows-mobile-5-dot-0",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-5-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliw.jpg",
    },
    "windows-mobile-6-dot-0": {
        "id": 538,
        "name": "Windows Mobile 6.0",
        "platform_slug": UPS.WINDOWS_MOBILE,
        "slug": "windows-mobile-6-dot-0",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-6-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkl.jpg",
    },
    "windows-phone-7": {
        "id": 224,
        "name": "Windows Phone 7",
        "platform_slug": UPS.WINPHONE,
        "slug": "windows-phone-7",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/taegabndvbq86z4dumy2.jpg",
    },
    "windows-phone-8": {
        "id": 225,
        "name": "Windows Phone 8",
        "platform_slug": UPS.WINPHONE,
        "slug": "windows-phone-8",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-8",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ui8kqoijqxolfowolj56.jpg",
    },
    "windows-phone-8-dot-1": {
        "id": 226,
        "name": "Windows Phone 8.1",
        "platform_slug": UPS.WINPHONE,
        "slug": "windows-phone-8-dot-1",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-8-dot-1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/gvk8xyyptd40kg3yb8j5.jpg",
    },
    "windows-vista": {
        "id": 14,
        "name": "Windows Vista",
        "platform_slug": UPS.WIN,
        "slug": "windows-vista",
        "url": "https://www.igdb.com/platforms/win/version/windows-vista",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/z6hjqy9uvneqbd3yh4sm.jpg",
    },
    "windows-xp": {
        "id": 13,
        "name": "Windows XP",
        "platform_slug": UPS.WIN,
        "slug": "windows-xp",
        "url": "https://www.igdb.com/platforms/win/version/windows-xp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/nnr9qxtqzrmh1v0s9x2p.jpg",
    },
    "wonderswan-color": {
        "id": 84,
        "name": "WonderSwan Color",
        "platform_slug": UPS.WONDERSWAN,
        "slug": "wonderswan-color",
        "url": "https://www.igdb.com/platforms/wonderswan/version/wonderswan-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7d.jpg",
    },
    "xbox-360-arcade": {
        "id": 3,
        "name": "Xbox 360 Arcade",
        "platform_slug": UPS.XBOX360,
        "slug": "xbox-360-arcade",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-arcade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6y.jpg",
    },
    "xbox-360-elite": {
        "id": 2,
        "name": "Xbox 360 Elite",
        "platform_slug": UPS.XBOX360,
        "slug": "xbox-360-elite",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-elite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6z.jpg",
    },
    "xbox-360-original": {
        "id": 83,
        "name": "Xbox 360 Original",
        "platform_slug": UPS.XBOX360,
        "slug": "xbox-360-original",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-original",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6x.jpg",
    },
    "xbox-360-s": {
        "id": 495,
        "name": "Xbox 360 S",
        "platform_slug": UPS.XBOX360,
        "slug": "xbox-360-s",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plha.jpg",
    },
    "xbox-one-s": {
        "id": 180,
        "name": "Xbox One S",
        "platform_slug": UPS.XBOXONE,
        "slug": "xbox-one-s",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl90.jpg",
    },
    "xbox-one-s-all-digital": {
        "id": 188,
        "name": "Xbox One S All-Digital",
        "platform_slug": UPS.XBOXONE,
        "slug": "xbox-one-s-all-digital",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-s-all-digital",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl95.jpg",
    },
    "xbox-one-x--1": {
        "id": 185,
        "name": "Xbox One X",
        "platform_slug": UPS.XBOXONE,
        "slug": "xbox-one-x--1",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-x--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fckqj8d3as6tug4fg3x4.jpg",
    },
    "xbox-series-s": {
        "id": 489,
        "name": "Xbox Series S",
        "platform_slug": UPS.SERIES_X_S,
        "slug": "xbox-series-s",
        "url": "https://www.igdb.com/platforms/series-x-s/version/xbox-series-s",
        "url_logo": "",
    },
    "xbox-series-x": {
        "id": 284,
        "name": "Xbox Series X",
        "platform_slug": UPS.SERIES_X_S,
        "slug": "xbox-series-x",
        "url": "https://www.igdb.com/platforms/series-x-s/version/xbox-series-x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plfl.jpg",
    },
    "yosemite": {
        "id": 150,
        "name": "Yosemite",
        "platform_slug": UPS.MAC,
        "slug": "yosemite",
        "url": "https://www.igdb.com/platforms/mac/version/yosemite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/df1raex6oqgcp56leff4.jpg",
    },
    "zodiac-1": {
        "id": 69,
        "name": "Zodiac 1",
        "platform_slug": UPS.ZOD,
        "slug": "zodiac-1",
        "url": "https://www.igdb.com/platforms/zod/version/zodiac-1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lfsdnlko80ftakbugceu.jpg",
    },
    "zx-spectrum": {
        "id": 79,
        "name": "ZX Spectrum",
        "platform_slug": UPS.ZXS,
        "slug": "zx-spectrum",
        "url": "https://www.igdb.com/platforms/zxs/version/zx-spectrum",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plab.jpg",
    },
}
