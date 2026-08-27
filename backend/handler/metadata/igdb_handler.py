import re
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from fastapi import status

from adapters.services.igdb import (
    IGDB_PLATFORM_LIST,
    IGDB_PLATFORM_VERSIONS,
    IGDBService,
)
from adapters.services.igdb_types import (
    Game,
    GameType,
    mark_expanded,
    mark_list_expanded,
)
from config import IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, IS_PYTEST_RUN
from config.config_manager import config_manager as cm
from handler.filesystem.base_handler import region_name_to_provider_shortcode
from handler.redis_handler import async_cache
from logger.logger import log
from models.rom import Rom
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

PS1_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.PSX]["id"]
PS2_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.PS2]["id"]
PSP_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.PSP]["id"]
SWITCH_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.SWITCH]["id"]
ARCADE_IGDB_IDS: Final = [
    IGDB_PLATFORM_LIST[UPS.ARCADE]["id"],
    IGDB_PLATFORM_LIST[UPS.NEOGEOAES]["id"],
    IGDB_PLATFORM_LIST[UPS.NEOGEOMVS]["id"],
]

# IGDB catalogues a console and its regional twin as two separate platforms.
# A game released in only one region is filed under just one of the pair,
# so a search locked to a single platform silently misses region-exclusive titles.
# Map each platform to its twin so searches can include both.
# See https://github.com/rommapp/romm/issues/3462.
SNES_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.SNES]["id"]
SUPER_FAMICOM_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.SFAM]["id"]
NES_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.NES]["id"]
FAMICOM_IGDB_ID: Final = IGDB_PLATFORM_LIST[UPS.FAMICOM]["id"]

IGDB_REGIONAL_TWIN_PLATFORMS: Final[dict[int, int]] = {
    SNES_IGDB_ID: SUPER_FAMICOM_IGDB_ID,
    SUPER_FAMICOM_IGDB_ID: SNES_IGDB_ID,
    NES_IGDB_ID: FAMICOM_IGDB_ID,
    FAMICOM_IGDB_ID: NES_IGDB_ID,
}

# Regex to detect IGDB ID tags in filenames like (igdb-12345)
IGDB_TAG_REGEX = re.compile(r"\(igdb-(\d+)\)", re.IGNORECASE)

# Jaro-Winkler score of an exact (post-normalization) title match. Only a first
# pass hitting this may be trusted without widening the search.
EXACT_MATCH_SCORE: Final = 1.0


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


class IGDBMetadataMultiplayerMode(TypedDict):
    campaigncoop: bool
    dropin: bool
    lancoop: bool
    offlinecoop: bool
    offlinecoopmax: int
    offlinemax: int
    onlinecoop: int
    onlinecoopmax: int
    onlinemax: int
    splitscreen: bool
    splitscreenonline: bool
    platform: IGDBMetadataPlatform


class IGDBMetadata(TypedDict):
    total_rating: str | None
    aggregated_rating: str | None
    first_release_date: int | None
    youtube_video_id: str | None
    genres: list[str]
    franchises: list[str]
    alternative_names: list[str]
    collections: list[str]
    companies: list[str]
    publishers: list[str]
    developers: list[str]
    game_modes: list[str]
    age_ratings: list[IGDBAgeRating]
    platforms: list[IGDBMetadataPlatform]
    multiplayer_modes: list[IGDBMetadataMultiplayerMode]
    player_count: str
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


def extract_metadata_from_igdb_rom(
    self: MetadataHandler, rom: Game, platform_igdb_id: int | None
) -> IGDBMetadata:
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
    multiplayer_modes = rom.get("multiplayer_modes", [])
    ports = rom.get("ports", [])
    remakes = rom.get("remakes", [])
    remasters = rom.get("remasters", [])
    similar_games = rom.get("similar_games", [])
    videos = rom.get("videos", [])

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
    assert mark_list_expanded(multiplayer_modes)
    assert mark_list_expanded(ports)
    assert mark_list_expanded(remakes)
    assert mark_list_expanded(remasters)
    assert mark_list_expanded(similar_games)
    assert mark_list_expanded(videos)

    multiplayer_modes_metadata = []

    for mm in multiplayer_modes:
        platform_data = mm.get("platform")

        igdb_id = -1
        name = ""
        if isinstance(platform_data, dict):
            igdb_id = platform_data.get("id", -1)
            name = platform_data.get("name", "")

        multiplayer_modes_metadata.append(
            IGDBMetadataMultiplayerMode(
                campaigncoop=mm.get("campaigncoop", False),
                dropin=mm.get("dropin", False),
                lancoop=mm.get("lancoop", False),
                offlinecoop=mm.get("offlinecoop", False),
                offlinecoopmax=mm.get("offlinecoopmax", 0),
                offlinemax=mm.get("offlinemax", 0),
                onlinecoop=mm.get("onlinecoop", False),
                onlinecoopmax=mm.get("onlinecoopmax", 0),
                onlinemax=mm.get("onlinemax", 0),
                splitscreen=mm.get("splitscreen", False),
                splitscreenonline=mm.get("splitscreenonline", False),
                platform=IGDBMetadataPlatform(
                    igdb_id=igdb_id,
                    name=name,
                ),
            )
        )

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
            "publishers": [
                c["company"]["name"]
                for c in involved_companies
                if c.get("company") and c.get("publisher")
            ],
            "developers": [
                c["company"]["name"]
                for c in involved_companies
                if c.get("company") and c.get("developer")
            ],
            "platforms": [
                IGDBMetadataPlatform(igdb_id=p["id"], name=p.get("name", ""))
                for p in platforms
            ],
            "multiplayer_modes": multiplayer_modes_metadata,
            "player_count": derive_player_count(
                multiplayer_modes_metadata, platform_igdb_id
            ),
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


def derive_player_count(
    multiplayer_modes: list[IGDBMetadataMultiplayerMode],
    platform_igdb_id: int | None = None,
) -> str:
    if not multiplayer_modes:
        return "1"

    relevant_modes = [
        mm
        for mm in multiplayer_modes
        if not platform_igdb_id
        or (mm.get("platform") and mm["platform"].get("igdb_id") == platform_igdb_id)
    ]

    if not relevant_modes:
        return "1"

    max_players = 1

    for mm in relevant_modes:
        if any(
            mm.get(key, False)
            for key in (
                "campaigncoop",
                "lancoop",
                "offlinecoop",
                "onlinecoop",
                "dropin",
            )
        ):
            max_players = max(max_players, 2)

        max_players = max(
            max_players,
            mm.get("offlinecoopmax", 0),
            mm.get("onlinecoopmax", 0),
        )

        max_players = max(
            max_players,
            mm.get("offlinemax", 0),
            mm.get("onlinemax", 0),
        )

    return f"1-{max_players}" if max_players > 1 else "1"


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


def get_igdb_preferred_locale(rom: Rom | None = None) -> str | None:
    """Get IGDB locale from the ROM's prioritized regions when available.

    Maps region priority codes to IGDB's game_localizations region identifiers.
    Prioritizes the ROM's tagged regions by scan.priority.region, then falls
    back to scan.priority.region.

    Returns:
        IGDB region identifier (e.g., "ja-JP", "EU") or None for default
    """
    config = cm.get_config()
    priority = config.SCAN_REGION_PRIORITY
    normalized_priority = [region.lower() for region in priority]

    if rom is not None and isinstance(rom.regions, list):
        rom_codes: list[str] = []
        for region_name in rom.regions:
            code = region_name_to_provider_shortcode(region_name)
            if code and code in REGION_TO_IGDB_LOCALE:
                rom_codes.append(code)

        rom_codes.sort(
            key=lambda code: (
                normalized_priority.index(code)
                if code in normalized_priority
                else len(normalized_priority)
            )
        )
        if rom_codes:
            return REGION_TO_IGDB_LOCALE[rom_codes[0]]

    for region in priority:
        if region.lower() in REGION_TO_IGDB_LOCALE:
            return REGION_TO_IGDB_LOCALE[region.lower()]

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
    handler: "IGDBHandler",
    rom: Game,
    preferred_locale: str | None,
    platform_igdb_id: int | None,
) -> "IGDBRom":
    """Build an IGDBRom from IGDB game data with localization support.

    Args:
        handler: IGDBHandler instance for URL normalization
        rom: Game data from IGDB API
        preferred_locale: Locale code (e.g., "ja-JP") or None
        platform_igdb_id: IGDB platform identifier

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
        igdb_metadata=extract_metadata_from_igdb_rom(handler, rom, platform_igdb_id),
    )


def _platform_igdb_ids_with_twin(platform_igdb_id: int) -> list[int]:
    """Return the IGDB platform id plus its regional twin, if any.

    IGDB splits region-twin consoles (SNES/Super Famicom, NES/Famicom) into
    separate platforms, so region-exclusive titles are catalogued under only one
    of the pair. Including both lets a Japan-only Super Famicom game match from
    an ``snes`` library and vice-versa. See issue #3462.
    """
    twin = IGDB_REGIONAL_TWIN_PLATFORMS.get(platform_igdb_id)
    return [platform_igdb_id, twin] if twin is not None else [platform_igdb_id]


def _build_platforms_where(platform_igdb_id: int, field: str = "platforms") -> str:
    """Build an IGDB ``where`` fragment matching the platform or its regional twin.

    A platform without a twin keeps the original single-clause shape
    (``platforms=[19]``); a twin produces a parenthesized OR group
    (``(platforms=[19] | platforms=[58])``) so it composes correctly with any
    trailing ``&`` filters.
    """
    ids = _platform_igdb_ids_with_twin(platform_igdb_id)
    clause = " | ".join(f"{field}=[{pid}]" for pid in ids)
    return f"({clause})" if len(ids) > 1 else clause


def _index_games_by_searchable_name(games: list[Game]) -> dict[str, Game]:
    """Map every searchable title of each game to the game it belongs to.

    A game is searchable not only by its primary English ``name`` but also by
    any ``alternative_names`` and ``game_localizations`` titles IGDB knows.
    No-Intro / ReDump filenames frequently use a localized title (e.g.
    ``007 - Die Welt Ist Nicht Genug`` for ``James Bond 007: The World Is Not
    Enough``); IGDB surfaces such a game through its ``alternative_name``
    wildcard search, so the candidate index must include those titles or
    ``find_best_match`` would score the localized filename only against the
    English name and drop the match (issue #3435).

    Primary names take precedence and use a lowest-igdb-id tiebreak (matching
    prior behavior); alternative/localization titles fill in only names not
    already claimed by a primary name.
    """
    index: dict[str, Game] = {}

    # First pass: primary names. On collision the lowest IGDB id wins.
    for game in games:
        name = game.get("name", "")
        if name and (name not in index or game["id"] < index[name]["id"]):
            index[name] = game

    # Second pass: alternative and localization titles, without displacing a
    # primary name already claimed above.
    for game in games:
        alternative_names = game.get("alternative_names", [])
        assert mark_list_expanded(alternative_names)
        for alt in alternative_names:
            alt_name = alt.get("name", "")
            if alt_name and alt_name not in index:
                index[alt_name] = game

        game_localizations = game.get("game_localizations", [])
        assert mark_list_expanded(game_localizations)
        for loc in game_localizations:
            loc_name = loc.get("name", "")
            if loc_name and loc_name not in index:
                index[loc_name] = game

    return index


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

    def _is_prefix_superset_match(self, search_term: str, candidate_name: str) -> bool:
        """Whether one title's words are a proper prefix of the other's.

        Jaro-Winkler scores a base title and a longer variant that starts with
        it (e.g. "Portable Ops" vs "Portable Ops Plus") well above the match
        threshold, so a fuzzy pass can settle for the base when the variant is
        simply absent from that pass's candidates. Detecting this prefix/superset
        ambiguity lets the caller widen the search before committing. (#3805)
        """
        search_tokens = self.normalize_search_term(search_term).split()
        candidate_tokens = self.normalize_search_term(candidate_name).split()
        if not search_tokens or not candidate_tokens:
            return False

        shorter, longer = sorted((search_tokens, candidate_tokens), key=len)
        return len(shorter) < len(longer) and longer[: len(shorter)] == shorter

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
                GameType.STANDALONE_EXPANSION,
            )
            game_type_filter = f"& game_type=({','.join(map(str, categories))})"
        else:
            game_type_filter = ""

        log.debug("Searching in games endpoint with game_type %s", game_type_filter)
        base_where = _build_platforms_where(platform_igdb_id)

        # Special case for ScummVM games
        # https://github.com/rommapp/romm/issues/2424
        scummvm_platform = self.get_platform(UPS.SCUMMVM)
        if scummvm_platform["igdb_id"] == platform_igdb_id:
            base_where = f"keywords=[{platform_igdb_id}]"

        roms = await self.igdb_service.list_games(
            search_term=search_term,
            fields=GAMES_FIELDS,
            where=f"{base_where} {game_type_filter}",
            limit=self.pagination_limit,
        )

        games_by_name = _index_games_by_searchable_name(roms)

        best_match, best_score = self.find_best_match(
            search_term,
            list(games_by_name.keys()),
        )

        # Trust an exact first-pass hit outright. A non-exact hit that is only a
        # prefix/superset of the search term (e.g. matching "Portable Ops" for a
        # "Portable Ops Plus" search) may be a near-miss for a more specific
        # variant this pass never saw, so widen the search and re-rank across
        # every candidate before committing. (#3805)
        if best_match is not None and (
            best_score >= EXACT_MATCH_SCORE
            or not self._is_prefix_superset_match(search_term, best_match)
        ):
            log.debug(
                f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
            )
            return games_by_name[best_match]

        extra_roms: list[Game] = []

        # The game_type filter can hide a more specific variant that IGDB
        # classifies as an excluded type (e.g. an expansion). Re-query without
        # it so such variants become candidates.
        if game_type_filter:
            log.debug("Searching in games endpoint without game_type")
            extra_roms.extend(
                await self.igdb_service.list_games(
                    search_term=search_term,
                    fields=GAMES_FIELDS,
                    where=base_where,
                    limit=self.pagination_limit,
                )
            )

        log.debug("Searching expanded in search endpoint")
        roms_expanded = await self.igdb_service.search(
            fields=SEARCH_FIELDS,
            where=f'{_build_platforms_where(platform_igdb_id, field="game.platforms")} & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*)',
            limit=self.pagination_limit,
        )

        # Collect all unique game IDs from the expanded search results,
        # skipping entries without a valid game id.
        unique_game_ids = list(
            dict.fromkeys(
                game_id
                for r in roms_expanded
                if (g := r.get("game")) and (game_id := g.get("id")) is not None
            )
        )

        if unique_game_ids:
            log.debug(
                "Searching expanded in games endpoint for %d candidate game(s): %s",
                len(unique_game_ids),
                unique_game_ids,
            )
            id_filter = " | ".join(f"id={gid}" for gid in unique_game_ids)
            extra_roms.extend(
                await self.igdb_service.list_games(
                    fields=GAMES_FIELDS,
                    where=f"({id_filter})",
                    limit=self.pagination_limit,
                )
            )

        if extra_roms:
            # Re-rank across the union of every pass so an exact variant surfaced
            # only after widening can outrank the first-pass near-miss on the
            # base title. The base stays in the pool, so it remains the fallback
            # when no better match exists.
            games_by_name = _index_games_by_searchable_name(roms + extra_roms)
            best_match, best_score = self.find_best_match(
                search_term,
                list(games_by_name.keys()),
            )

        if best_match:
            log.debug(
                f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
            )
            return games_by_name[best_match]

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

    async def get_rom(self, rom: Rom, fs_name: str, platform_igdb_id: int) -> IGDBRom:
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return IGDBRom(igdb_id=None)

        if not platform_igdb_id:
            return IGDBRom(igdb_id=None)

        # Check for IGDB ID tag in filename first
        igdb_id_from_tag = self.extract_igdb_id_from_filename(fs_name)
        if igdb_id_from_tag:
            log.debug(f"Found IGDB ID tag in filename: {igdb_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(rom, igdb_id_from_tag)
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
        match = SONY_SERIAL_REGEX.search(fs_name)
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

        # Support for ScummVM filename format
        scummvm_platform = self.get_platform(UPS.SCUMMVM)
        if platform_igdb_id == scummvm_platform.get("igdb_id"):
            search_term = await self._scummvm_format(search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)

        log.debug("Searching for %s on IGDB with game_type", search_term)
        res = await self._search_rom(search_term, platform_igdb_id, with_game_type=True)
        if not res:
            log.debug("Searching for %s on IGDB without game_type", search_term)
            res = await self._search_rom(search_term, platform_igdb_id)

        # IGDB search is fuzzy so no need to split the search term by special characters
        if not res:
            return fallback_rom

        return build_igdb_rom(
            self, res, get_igdb_preferred_locale(rom=rom), platform_igdb_id
        )

    async def get_rom_by_id(self, rom: Rom, igdb_id: int) -> IGDBRom:
        if not self.is_enabled():
            return IGDBRom(igdb_id=None)

        roms = await self.igdb_service.list_games(
            fields=GAMES_FIELDS,
            where=f"id={igdb_id}",
            limit=self.pagination_limit,
        )
        if not roms:
            return IGDBRom(igdb_id=None)

        return build_igdb_rom(self, roms[0], get_igdb_preferred_locale(rom=rom), None)

    async def get_matched_rom_by_id(self, rom: Rom, igdb_id: int) -> IGDBRom | None:
        if not self.is_enabled():
            return None

        result = await self.get_rom_by_id(rom, igdb_id)
        return result if result["igdb_id"] else None

    async def get_matched_roms_by_name(
        self, rom: Rom, search_term: str, platform_igdb_id: int | None
    ) -> list[IGDBRom]:
        if not self.is_enabled():
            return []

        if not platform_igdb_id:
            return []

        matched_roms = await self.igdb_service.list_games(
            search_term=search_term,
            fields=GAMES_FIELDS,
            where=_build_platforms_where(platform_igdb_id),
            limit=self.pagination_limit,
        )

        alternative_matched_roms = await self.igdb_service.search(
            fields=SEARCH_FIELDS,
            where=f'{_build_platforms_where(platform_igdb_id, field="game.platforms")} & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*)',
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

        # Use a dictionary to keep track of unique IDs
        unique_ids: dict[int, Game] = {}

        # Use a list comprehension to filter duplicates based on the 'id' key
        matched_roms = [
            unique_ids.setdefault(rom["id"], rom)
            for rom in matched_roms
            if rom["id"] not in unique_ids
        ]

        preferred_locale = get_igdb_preferred_locale(rom=rom)
        return [
            build_igdb_rom(self, rom, preferred_locale, platform_igdb_id)
            for rom in matched_roms
        ]


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
    "involved_companies.developer",
    "involved_companies.publisher",
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
    "multiplayer_modes.campaigncoop",
    "multiplayer_modes.checksum",
    "multiplayer_modes.dropin",
    "multiplayer_modes.lancoop",
    "multiplayer_modes.offlinecoop",
    "multiplayer_modes.offlinecoopmax",
    "multiplayer_modes.offlinemax",
    "multiplayer_modes.onlinecoop",
    "multiplayer_modes.onlinecoopmax",
    "multiplayer_modes.onlinemax",
    "multiplayer_modes.splitscreen",
    "multiplayer_modes.splitscreenonline",
    "multiplayer_modes.platform.id",
    "multiplayer_modes.platform.name",
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
