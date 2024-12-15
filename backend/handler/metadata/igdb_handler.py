import functools
import re
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from adapters.services.igdb_types import GameCategory
from config import IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, IS_PYTEST_RUN
from fastapi import HTTPException, status
from handler.redis_handler import async_cache
from logger.logger import log
from unidecode import unidecode as uc
from utils.context import ctx_httpx_client

from .base_hander import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    MetadataHandler,
)

# Used to display the IGDB API status in the frontend
IGDB_API_ENABLED: Final = bool(IGDB_CLIENT_ID) and bool(IGDB_CLIENT_SECRET)

PS1_IGDB_ID: Final = 7
PS2_IGDB_ID: Final = 8
PSP_IGDB_ID: Final = 38
SWITCH_IGDB_ID: Final = 130
ARCADE_IGDB_IDS: Final = [52, 79, 80]


class IGDBPlatform(TypedDict):
    slug: str
    igdb_id: int | None
    name: NotRequired[str]
    category: NotRequired[str]
    generation: NotRequired[str]
    family_name: NotRequired[str]
    family_slug: NotRequired[str]
    url: NotRequired[str]
    url_logo: NotRequired[str]
    logo_path: NotRequired[str]


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


class IGDBRom(TypedDict):
    igdb_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    igdb_metadata: NotRequired[IGDBMetadata]


def extract_metadata_from_igdb_rom(rom: dict) -> IGDBMetadata:
    return IGDBMetadata(
        {
            "youtube_video_id": str(pydash.get(rom, "videos[0].video_id", None)),
            "total_rating": str(round(rom.get("total_rating", 0.0), 2)),
            "aggregated_rating": str(round(rom.get("aggregated_rating", 0.0), 2)),
            "first_release_date": rom.get("first_release_date", None),
            "genres": pydash.map_(rom.get("genres", []), "name"),
            "franchises": pydash.compact(
                [rom.get("franchise.name", None)]
                + pydash.map_(rom.get("franchises", []), "name")
            ),
            "alternative_names": pydash.map_(rom.get("alternative_names", []), "name"),
            "collections": pydash.map_(rom.get("collections", []), "name"),
            "game_modes": pydash.map_(rom.get("game_modes", []), "name"),
            "companies": pydash.map_(rom.get("involved_companies", []), "company.name"),
            "platforms": [
                IGDBMetadataPlatform(igdb_id=p.get("id", ""), name=p.get("name", ""))
                for p in rom.get("platforms", [])
            ],
            "age_ratings": [
                IGDB_AGE_RATINGS[r["rating"]]
                for r in rom.get("age_ratings", [])
                if r["rating"] in IGDB_AGE_RATINGS
            ],
            "expansions": [
                IGDBRelatedGame(
                    id=e["id"],
                    slug=e["slug"],
                    name=e["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(e, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="expansion",
                )
                for e in rom.get("expansions", [])
            ],
            "dlcs": [
                IGDBRelatedGame(
                    id=d["id"],
                    slug=d["slug"],
                    name=d["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(d, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="dlc",
                )
                for d in rom.get("dlcs", [])
            ],
            "remasters": [
                IGDBRelatedGame(
                    id=r["id"],
                    slug=r["slug"],
                    name=r["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(r, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="remaster",
                )
                for r in rom.get("remasters", [])
            ],
            "remakes": [
                IGDBRelatedGame(
                    id=r["id"],
                    slug=r["slug"],
                    name=r["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(r, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="remake",
                )
                for r in rom.get("remakes", [])
            ],
            "expanded_games": [
                IGDBRelatedGame(
                    id=g["id"],
                    slug=g["slug"],
                    name=g["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(g, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="expanded",
                )
                for g in rom.get("expanded_games", [])
            ],
            "ports": [
                IGDBRelatedGame(
                    id=p["id"],
                    slug=p["slug"],
                    name=p["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(p, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="port",
                )
                for p in rom.get("ports", [])
            ],
            "similar_games": [
                IGDBRelatedGame(
                    id=s["id"],
                    slug=s["slug"],
                    name=s["name"],
                    cover_url=MetadataHandler._normalize_cover_url(
                        pydash.get(s, "cover.url", "").replace("t_thumb", "t_1080p")
                    ),
                    type="similar",
                )
                for s in rom.get("similar_games", [])
            ],
        }
    )


class IGDBBaseHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.igdb.com/v4"
        self.platform_endpoint = f"{self.BASE_URL}/platforms"
        self.platform_version_endpoint = f"{self.BASE_URL}/platform_versions"
        self.platforms_fields = PLATFORMS_FIELDS
        self.games_endpoint = f"{self.BASE_URL}/games"
        self.games_fields = GAMES_FIELDS
        self.search_endpoint = f"{self.BASE_URL}/search"
        self.search_fields = SEARCH_FIELDS
        self.pagination_limit = 200
        self.twitch_auth = TwitchAuth()
        self.headers = {
            "Client-ID": IGDB_CLIENT_ID,
            "Accept": "application/json",
        }

    @staticmethod
    def check_twitch_token(func):
        @functools.wraps(func)
        async def wrapper(*args):
            token = await args[0].twitch_auth.get_oauth_token()
            args[0].headers["Authorization"] = f"Bearer {token}"
            return await func(*args)

        return wrapper

    async def _request(self, url: str, data: str, timeout: int = 120) -> list:
        httpx_client = ctx_httpx_client.get()
        try:
            masked_headers = self._mask_sensitive_values(self.headers)
            log.debug(
                "API request: URL=%s, Headers=%s, Content=%s, Timeout=%s",
                url,
                masked_headers,
                f"{data} limit {self.pagination_limit};",
                timeout,
            )
            res = await httpx_client.post(
                url,
                content=f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=timeout,
            )

            res.raise_for_status()
            return res.json()
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to IGDB", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as err:
            # Retry once if the auth token is invalid
            if err.response.status_code != 401:
                log.error(err)
                return []  # All requests to the IGDB API return a list

            # Attempt to force a token refresh if the token is invalid
            log.warning("Twitch token invalid: fetching a new one...")
            token = await self.twitch_auth._update_twitch_token()
            self.headers["Authorization"] = f"Bearer {token}"
        except httpx.TimeoutException:
            # Retry once the request if it times out
            pass

        try:
            log.debug(
                "Making a second attempt API request: URL=%s, Headers=%s, Content=%s, Timeout=%s",
                url,
                masked_headers,
                f"{data} limit {self.pagination_limit};",
                timeout,
            )
            res = await httpx_client.post(
                url,
                content=f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=timeout,
            )
            res.raise_for_status()
        except httpx.HTTPError as err:
            # Log the error and return an empty list if the request fails again
            log.error(err)
            return []

        return res.json()

    async def _search_rom(
        self, search_term: str, platform_igdb_id: int, with_category: bool = False
    ) -> dict | None:
        if not platform_igdb_id:
            return None

        search_term = uc(search_term)
        if with_category:
            categories = (
                GameCategory.EXPANDED_GAME,
                GameCategory.MAIN_GAME,
                GameCategory.PORT,
                GameCategory.REMAKE,
                GameCategory.REMASTER,
            )
            category_filter = f"& category=({','.join(map(str, categories))})"
        else:
            category_filter = ""

        def is_exact_match(rom: dict, search_term: str) -> bool:
            search_term_lower = search_term.lower()
            if rom["slug"].lower() == search_term_lower:
                return True

            search_term_normalized = self._normalize_exact_match(search_term)
            # Check both the ROM name and alternative names for an exact match.
            rom_names = [rom["name"]] + [
                alternative_name["name"]
                for alternative_name in rom.get("alternative_names", [])
            ]

            return any(
                (
                    rom_name.lower() == search_term_lower
                    or self._normalize_exact_match(rom_name) == search_term_normalized
                )
                for rom_name in rom_names
            )

        log.debug("Searching in games endpoint with category %s", category_filter)
        roms = await self._request(
            self.games_endpoint,
            data=f'search "{search_term}"; fields {",".join(self.games_fields)}; where platforms=[{platform_igdb_id}] {category_filter};',
        )
        for rom in roms:
            # Return early if an exact match is found.
            if is_exact_match(rom, search_term):
                return rom

        log.debug("Searching expanded in search endpoint")
        roms_expanded = await self._request(
            self.search_endpoint,
            data=f'fields {",".join(self.search_fields)}; where game.platforms=[{platform_igdb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*);',
        )
        if roms_expanded:
            log.debug(
                "Searching expanded in games endpoint for expanded game %s",
                roms_expanded[0]["game"],
            )
            extra_roms = await self._request(
                self.games_endpoint,
                f'fields {",".join(self.games_fields)}; where id={roms_expanded[0]["game"]["id"]};',
            )
            for rom in extra_roms:
                # Return early if an exact match is found.
                if is_exact_match(rom, search_term):
                    return rom

            roms.extend(extra_roms)

        return roms[0] if roms else None

    @check_twitch_token
    async def get_platform(self, slug: str) -> IGDBPlatform:
        if not IGDB_API_ENABLED:
            return IGDBPlatform(igdb_id=None, slug=slug)

        platforms = await self._request(
            self.platform_endpoint,
            data=f'fields {",".join(self.platforms_fields)}; where slug="{slug.lower()}";',
        )
        platform = pydash.get(platforms, "[0]", None)
        if platform:
            return IGDBPlatform(
                igdb_id=platform.get("id", None),
                slug=slug,
                name=platform.get("name", slug),
                category=IGDB_PLATFORM_CATEGORIES.get(
                    platform.get("category", 0), "Unknown"
                ),
                generation=platform.get("generation", None),
                family_name=pydash.get(platform, "platform_family.name", None),
                family_slug=pydash.get(platform, "platform_family.slug", None),
                url=platform.get("url", None),
                url_logo=self._normalize_cover_url(
                    pydash.get(platform, "platform_logo.url", "").replace(
                        "t_thumb", "t_1080p"
                    )
                ),
            )

        # Check if platform is a version if not found
        platform_versions = await self._request(
            self.platform_version_endpoint,
            data=f'fields {",".join(self.platforms_fields)}; where slug="{slug.lower()}";',
        )
        version = pydash.get(platform_versions, "[0]", None)
        if version:
            return IGDBPlatform(
                igdb_id=version["id"],
                slug=slug,
                name=version["name"],
            )

        return IGDBPlatform(igdb_id=None, slug=slug)

    @check_twitch_token
    async def get_rom(self, file_name: str, platform_igdb_id: int) -> IGDBRom:
        from handler.filesystem import fs_rom_handler

        if not IGDB_API_ENABLED:
            return IGDBRom(igdb_id=None)

        if not platform_igdb_id:
            return IGDBRom(igdb_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = IGDBRom(igdb_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(file_name)
        if platform_igdb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(file_name, re.IGNORECASE)
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
        match = SWITCH_TITLEDB_REGEX.search(file_name)
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
        match = SWITCH_PRODUCT_ID_REGEX.search(file_name)
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

        log.debug("Searching for %s on IGDB with category", search_term)
        rom = await self._search_rom(search_term, platform_igdb_id, with_category=True)
        if not rom:
            log.debug("Searching for %s on IGDB without category", search_term)
            rom = await self._search_rom(search_term, platform_igdb_id)

        # Split the search term since igdb struggles with colons
        if not rom and ":" in search_term:
            for term in search_term.split(":")[::-1]:
                log.debug(
                    "Searching for %s on IGDB without category after splitting semicolon",
                    term,
                )
                rom = await self._search_rom(term, platform_igdb_id)
                if rom:
                    break

        # Some MAME games have two titles split by a slash
        if not rom and "/" in search_term:
            for term in search_term.split("/"):
                log.debug(
                    "Searching for %s on IGDB without category after splitting slash",
                    term,
                )
                rom = await self._search_rom(term.strip(), platform_igdb_id)
                if rom:
                    break

        if not rom:
            return fallback_rom

        return IGDBRom(
            igdb_id=rom["id"],
            slug=rom["slug"],
            name=rom["name"],
            summary=rom.get("summary", ""),
            url_cover=self._normalize_cover_url(
                rom.get("cover", {}).get("url", "")
            ).replace("t_thumb", "t_1080p"),
            url_screenshots=[
                self._normalize_cover_url(s.get("url", "")).replace("t_thumb", "t_720p")
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(rom),
        )

    @check_twitch_token
    async def get_rom_by_id(self, igdb_id: int) -> IGDBRom:
        if not IGDB_API_ENABLED:
            return IGDBRom(igdb_id=None)

        roms = await self._request(
            self.games_endpoint,
            f'fields {",".join(self.games_fields)}; where id={igdb_id};',
        )
        rom = pydash.get(roms, "[0]", None)

        if not rom:
            return IGDBRom(igdb_id=None)

        return IGDBRom(
            igdb_id=rom["id"],
            slug=rom["slug"],
            name=rom["name"],
            summary=rom.get("summary", ""),
            url_cover=self._normalize_cover_url(
                rom.get("cover", {}).get("url", "")
            ).replace("t_thumb", "t_1080p"),
            url_screenshots=[
                self._normalize_cover_url(s.get("url", "")).replace("t_thumb", "t_720p")
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(rom),
        )

    @check_twitch_token
    async def get_matched_roms_by_id(self, igdb_id: int) -> list[IGDBRom]:
        if not IGDB_API_ENABLED:
            return []

        rom = await self.get_rom_by_id(igdb_id)
        return [rom] if rom["igdb_id"] else []

    @check_twitch_token
    async def get_matched_roms_by_name(
        self, search_term: str, platform_igdb_id: int
    ) -> list[IGDBRom]:
        if not IGDB_API_ENABLED:
            return []

        if not platform_igdb_id:
            return []

        search_term = uc(search_term)
        matched_roms = await self._request(
            self.games_endpoint,
            data=f'search "{search_term}"; fields {",".join(self.games_fields)}; where platforms=[{platform_igdb_id}];',
        )

        alternative_matched_roms = await self._request(
            self.search_endpoint,
            data=f'fields {",".join(self.search_fields)}; where game.platforms=[{platform_igdb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*);',
        )

        if alternative_matched_roms:
            alternative_roms_ids = []
            for rom in alternative_matched_roms:
                alternative_roms_ids.append(
                    rom.get("game").get("id", "")
                    if "game" in rom.keys()
                    else rom.get("id", "")
                )
            id_filter = " | ".join(
                list(
                    map(
                        lambda rom: (
                            f'id={rom.get("game").get("id", "")}'
                            if "game" in rom.keys()
                            else f'id={rom.get("id", "")}'
                        ),
                        alternative_matched_roms,
                    )
                )
            )
            alternative_matched_roms = await self._request(
                self.games_endpoint,
                f'fields {",".join(self.games_fields)}; where {id_filter};',
            )
            matched_roms.extend(alternative_matched_roms)

        # Use a dictionary to keep track of unique ids
        unique_ids: dict[str, dict[str, str]] = {}

        # Use a list comprehension to filter duplicates based on the 'id' key
        matched_roms = [
            unique_ids.setdefault(rom["id"], rom)
            for rom in matched_roms
            if rom["id"] not in unique_ids
        ]

        return [
            IGDBRom(
                {  # type: ignore[misc]
                    k: v
                    for k, v in {
                        "igdb_id": rom["id"],
                        "slug": rom["slug"],
                        "name": rom["name"],
                        "summary": rom.get("summary", ""),
                        "url_cover": self._normalize_cover_url(
                            pydash.get(rom, "cover.url", "").replace(
                                "t_thumb", "t_1080p"
                            )
                        ),
                        "url_screenshots": [
                            self._normalize_cover_url(s.get("url", "")).replace(
                                "t_thumb", "t_720p"
                            )
                            for s in rom.get("screenshots", [])
                        ],
                        "igdb_metadata": extract_metadata_from_igdb_rom(rom),
                    }.items()
                    if v
                }
            )
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

    async def _update_twitch_token(self) -> str:
        if not IGDB_API_ENABLED:
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

            if res.status_code == 400:
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

        if not IGDB_API_ENABLED:
            return ""

        # Fetch the token cache
        token = await async_cache.get("romm:twitch_token")
        if not token:
            log.warning("Twitch token invalid: fetching a new one...")
            return await self._update_twitch_token()

        return token


PLATFORMS_FIELDS = [
    "id",
    "name",
    "category",
    "generation",
    "url",
    "platform_family.name",
    "platform_family.slug",
    "platform_logo.url",
]

GAMES_FIELDS = [
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
    "age_ratings.rating",
    "videos.video_id",
]

SEARCH_FIELDS = ["game.id", "name"]

# Generated from the following code on https://www.igdb.com/platforms/:
# Array.from(document.querySelectorAll(".media-body a")).map(a => ({
#   slug: a.href.split("/")[4],
#   name: a.innerText
# }))

IGDB_PLATFORM_LIST = [
    {"slug": "visionos", "name": "visionOS"},
    {"slug": "meta-quest-3", "name": "Meta Quest 3"},
    {"slug": "atari2600", "name": "Atari 2600"},
    {"slug": "psvr2", "name": "PlayStation VR2"},
    {"slug": "switch", "name": "Nintendo Switch"},
    {"slug": "evercade", "name": "Evercade"},
    {"slug": "android", "name": "Android"},
    {"slug": "mac", "name": "Mac"},
    {"slug": "win", "name": "PC (Microsoft Windows)"},
    {"slug": "oculus-quest", "name": "Oculus Quest"},
    {"slug": "playdate", "name": "Playdate"},
    {"slug": "series-x", "name": "Xbox Series X"},
    {"slug": "meta-quest-2", "name": "Meta Quest 2"},
    {"slug": "ps5", "name": "PlayStation 5"},
    {"slug": "oculus-rift", "name": "Oculus Rift"},
    {"slug": "xboxone", "name": "Xbox One"},
    {"slug": "leaptv", "name": "LeapTV"},
    {"slug": "new-nintendo-3ds", "name": "New Nintendo 3DS"},
    {"slug": "gear-vr", "name": "Gear VR"},
    {"slug": "psvr", "name": "PlayStation VR"},
    {"slug": "3ds", "name": "Nintendo 3DS"},
    {"slug": "winphone", "name": "Windows Phone"},
    {"slug": "arduboy", "name": "Arduboy"},
    {"slug": "ps4--1", "name": "PlayStation 4"},
    {"slug": "oculus-go", "name": "Oculus Go"},
    {"slug": "psvita", "name": "PlayStation Vita"},
    {"slug": "wiiu", "name": "Wii U"},
    {"slug": "ouya", "name": "Ouya"},
    {"slug": "wii", "name": "Wii"},
    {"slug": "ps3", "name": "PlayStation 3"},
    {"slug": "psp", "name": "PlayStation Portable"},
    {"slug": "nintendo-dsi", "name": "Nintendo DSi"},
    {
        "slug": "leapster-explorer-slash-leadpad-explorer",
        "name": "Leapster Explorer/LeadPad Explorer",
    },
    {"slug": "xbox360", "name": "Xbox 360"},
    {"slug": "nds", "name": "Nintendo DS"},
    {"slug": "ps2", "name": "PlayStation 2"},
    {"slug": "arcade", "name": "Arcade"},
    {"slug": "zeebo", "name": "Zeebo"},
    {"slug": "windows-mobile", "name": "Windows Mobile"},
    {"slug": "ios", "name": "iOS"},
    {"slug": "mobile", "name": "Legacy Mobile Device"},
    {"slug": "blu-ray-player", "name": "Blu-ray Player"},
    {"slug": "hyperscan", "name": "HyperScan"},
    {"slug": "gizmondo", "name": "Gizmondo"},
    {"slug": "gba", "name": "Game Boy Advance"},
    {"slug": "ngage", "name": "N-Gage"},
    {"slug": "vsmile", "name": "V.Smile"},
    {"slug": "n64", "name": "Nintendo 64"},
    {"slug": "leapster", "name": "Leapster"},
    {"slug": "zod", "name": "Tapwave Zodiac"},
    {"slug": "wonderswan-color", "name": "WonderSwan Color"},
    {"slug": "xbox", "name": "Xbox"},
    {"slug": "ngc", "name": "Nintendo GameCube"},
    {"slug": "wonderswan", "name": "WonderSwan"},
    {"slug": "pokemon-mini", "name": "Pokémon mini"},
    {"slug": "nuon", "name": "Nuon"},
    {"slug": "ps", "name": "PlayStation"},
    {"slug": "nintendo-64dd", "name": "Nintendo 64DD"},
    {"slug": "neo-geo-pocket-color", "name": "Neo Geo Pocket Color"},
    {"slug": "dvd-player", "name": "DVD Player"},
    {"slug": "pocketstation", "name": "PocketStation"},
    {
        "slug": "visual-memory-unit-slash-visual-memory-system",
        "name": "Visual Memory Unit / Visual Memory System",
    },
    {"slug": "blackberry", "name": "BlackBerry OS"},
    {"slug": "dc", "name": "Dreamcast"},
    {"slug": "gbc", "name": "Game Boy Color"},
    {"slug": "gb", "name": "Game Boy"},
    {"slug": "neo-geo-pocket", "name": "Neo Geo Pocket"},
    {"slug": "snes", "name": "Super Nintendo Entertainment System"},
    {"slug": "genesis-slash-megadrive", "name": "Sega Mega Drive/Genesis"},
    {"slug": "sfam", "name": "Super Famicom"},
    {"slug": "game-dot-com", "name": "Game.com"},
    {"slug": "hyper-neo-geo-64", "name": "Hyper Neo Geo 64"},
    {"slug": "satellaview", "name": "Satellaview"},
    {"slug": "palm-os", "name": "Palm OS"},
    {"slug": "apple-pippin", "name": "Apple Pippin"},
    {"slug": "sega32", "name": "Sega 32X"},
    {"slug": "neo-geo-cd", "name": "Neo Geo CD"},
    {"slug": "virtualboy", "name": "Virtual Boy"},
    {"slug": "atari-jaguar-cd", "name": "Atari Jaguar CD"},
    {"slug": "saturn", "name": "Sega Saturn"},
    {"slug": "casio-loopy", "name": "Casio Loopy"},
    {"slug": "sega-pico", "name": "Sega Pico"},
    {"slug": "r-zone", "name": "R-Zone"},
    {"slug": "sms", "name": "Sega Master System/Mark III"},
    {"slug": "playdia", "name": "Playdia"},
    {"slug": "pc-fx", "name": "PC-FX"},
    {"slug": "3do", "name": "3DO Interactive Multiplayer"},
    {
        "slug": "terebikko-slash-see-n-say-video-phone",
        "name": "Terebikko / See 'n Say Video Phone",
    },
    {"slug": "jaguar", "name": "Atari Jaguar"},
    {"slug": "segacd", "name": "Sega CD"},
    {"slug": "nes", "name": "Nintendo Entertainment System"},
    {"slug": "amiga-cd32", "name": "Amiga CD32"},
    {"slug": "famicom", "name": "Family Computer"},
    {"slug": "mega-duck-slash-cougar-boy", "name": "Mega Duck/Cougar Boy"},
    {"slug": "amiga", "name": "Amiga"},
    {
        "slug": "watara-slash-quickshot-supervision",
        "name": "Watara/QuickShot Supervision",
    },
    {"slug": "philips-cd-i", "name": "Philips CD-i"},
    {"slug": "gamegear", "name": "Sega Game Gear"},
    {"slug": "neogeoaes", "name": "Neo Geo AES"},
    {"slug": "linux", "name": "Linux"},
    {"slug": "turbografx-16-slash-pc-engine-cd", "name": "Turbografx-16/PC Engine CD"},
    {"slug": "neogeomvs", "name": "Neo Geo MVS"},
    {"slug": "commodore-cdtv", "name": "Commodore CDTV"},
    {"slug": "lynx", "name": "Atari Lynx"},
    {"slug": "gamate", "name": "Gamate"},
    {"slug": "bbcmicro", "name": "BBC Microcomputer System"},
    {"slug": "turbografx16--1", "name": "TurboGrafx-16/PC Engine"},
    {"slug": "supergrafx", "name": "PC Engine SuperGrafx"},
    {"slug": "fm-towns", "name": "FM Towns"},
    {"slug": "pc-9800-series", "name": "PC-9800 Series"},
    {"slug": "apple-iigs", "name": "Apple IIGS"},
    {"slug": "x1", "name": "Sharp X1"},
    {"slug": "sharp-x68000", "name": "Sharp X68000"},
    {"slug": "acorn-archimedes", "name": "Acorn Archimedes"},
    {"slug": "c64", "name": "Commodore C64/128/MAX"},
    {"slug": "fds", "name": "Family Computer Disk System"},
    {"slug": "dragon-32-slash-64", "name": "Dragon 32/64"},
    {"slug": "acorn-electron", "name": "Acorn Electron"},
    {"slug": "acpc", "name": "Amstrad CPC"},
    {"slug": "atari-st", "name": "Atari ST/STE"},
    {"slug": "tatung-einstein", "name": "Tatung Einstein"},
    {"slug": "amstrad-pcw", "name": "Amstrad PCW"},
    {"slug": "epoch-super-cassette-vision", "name": "Epoch Super Cassette Vision"},
    {"slug": "atari7800", "name": "Atari 7800"},
    {"slug": "hp3000", "name": "HP 3000"},
    {"slug": "atari5200", "name": "Atari 5200"},
    {"slug": "c16", "name": "Commodore 16"},
    {"slug": "sinclair-ql", "name": "Sinclair QL"},
    {"slug": "thomson-mo5", "name": "Thomson MO5"},
    {"slug": "c-plus-4", "name": "Commodore Plus/4"},
    {"slug": "sg1000", "name": "SG-1000"},
    {"slug": "vectrex", "name": "Vectrex"},
    {"slug": "sharp-mz-2200", "name": "Sharp MZ-2200"},
    {"slug": "nec-pc-6000-series", "name": "NEC PC-6000 Series"},
    {"slug": "msx2", "name": "MSX2"},
    {"slug": "msx", "name": "MSX"},
    {"slug": "colecovision", "name": "ColecoVision"},
    {"slug": "intellivision", "name": "Intellivision"},
    {"slug": "vic-20", "name": "Commodore VIC-20"},
    {"slug": "zxs", "name": "ZX Spectrum"},
    {"slug": "arcadia-2001", "name": "Arcadia 2001"},
    {"slug": "fm-7", "name": "FM-7"},
    {"slug": "trs-80", "name": "TRS-80"},
    {"slug": "epoch-cassette-vision", "name": "Epoch Cassette Vision"},
    {"slug": "dos", "name": "DOS"},
    {"slug": "ti-99", "name": "Texas Instruments TI-99"},
    {"slug": "sinclair-zx81", "name": "Sinclair ZX81"},
    {"slug": "pc-8800-series", "name": "PC-8800 Series"},
    {"slug": "microvision--1", "name": "Microvision"},
    {"slug": "g-and-w", "name": "Game & Watch"},
    {"slug": "atari8bit", "name": "Atari 8-bit"},
    {"slug": "trs-80-color-computer", "name": "TRS-80 Color Computer"},
    {
        "slug": "1292-advanced-programmable-video-system",
        "name": "1292 Advanced Programmable Video System",
    },
    {"slug": "odyssey-2-slash-videopac-g7000", "name": "Odyssey 2 / Videopac G7000"},
    {"slug": "exidy-sorcerer", "name": "Exidy Sorcerer"},
    {"slug": "pc-50x-family", "name": "PC-50X Family"},
    {"slug": "vc-4000", "name": "VC 4000"},
    {"slug": "appleii", "name": "Apple II"},
    {"slug": "astrocade", "name": "Bally Astrocade"},
    {"slug": "ay-3-8500", "name": "AY-3-8500"},
    {"slug": "cpet", "name": "Commodore PET"},
    {"slug": "fairchild-channel-f", "name": "Fairchild Channel F"},
    {"slug": "ay-3-8610", "name": "AY-3-8610"},
    {"slug": "ay-3-8605", "name": "AY-3-8605"},
    {"slug": "ay-3-8603", "name": "AY-3-8603"},
    {"slug": "ay-3-8710", "name": "AY-3-8710"},
    {"slug": "ay-3-8760", "name": "AY-3-8760"},
    {"slug": "ay-3-8606", "name": "AY-3-8606"},
    {"slug": "ay-3-8607", "name": "AY-3-8607"},
    {"slug": "sol-20", "name": "Sol-20"},
    {"slug": "odyssey--1", "name": "Odyssey"},
    {"slug": "plato--1", "name": "PLATO"},
    {"slug": "cdccyber70", "name": "CDC Cyber 70"},
    {"slug": "sdssigma7", "name": "SDS Sigma 7"},
    {"slug": "pdp11", "name": "PDP-11"},
    {"slug": "hp2100", "name": "HP 2100"},
    {"slug": "pdp10", "name": "PDP-10"},
    {
        "slug": "call-a-computer",
        "name": "Call-A-Computer time-shared mainframe computer system",
    },
    {"slug": "pdp-8--1", "name": "PDP-8"},
    {"slug": "nintendo-playstation", "name": "Nintendo PlayStation"},
    {"slug": "pdp1", "name": "PDP-1"},
    {"slug": "donner30", "name": "Donner Model 30"},
    {"slug": "edsac--1", "name": "EDSAC"},
    {"slug": "nimrod", "name": "Ferranti Nimrod Computer"},
    {"slug": "swancrystal", "name": "SwanCrystal"},
    {"slug": "panasonic-jungle", "name": "Panasonic Jungle"},
    {"slug": "handheld-electronic-lcd", "name": "Handheld Electronic LCD"},
    {"slug": "intellivision-amico", "name": "Intellivision Amico"},
    {"slug": "legacy-computer", "name": "Legacy Computer"},
    {"slug": "panasonic-m2", "name": "Panasonic M2"},
    {"slug": "browser", "name": "Web browser"},
    {"slug": "ooparts", "name": "OOParts"},
    {"slug": "stadia", "name": "Google Stadia"},
    {"slug": "plug-and-play", "name": "Plug & Play"},
    {"slug": "amazon-fire-tv", "name": "Amazon Fire TV"},
    {"slug": "onlive-game-system", "name": "OnLive Game System"},
    {"slug": "vc", "name": "Virtual Console"},
    {"slug": "airconsole", "name": "AirConsole"},
]

IGDB_PLATFORM_CATEGORIES: dict[int, str] = {
    0: "Unknown",
    1: "Console",
    2: "Arcade",
    3: "Platform",
    4: "Operative System",
    5: "Portable Console",
    6: "Computer",
}

IGDB_AGE_RATINGS: dict[int, IGDBAgeRating] = {
    1: {
        "rating": "Three",
        "category": "PEGI",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_3.png",
    },
    2: {
        "rating": "Seven",
        "category": "PEGI",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_7.png",
    },
    3: {
        "rating": "Twelve",
        "category": "PEGI",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_12.png",
    },
    4: {
        "rating": "Sixteen",
        "category": "PEGI",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_16.png",
    },
    5: {
        "rating": "Eighteen",
        "category": "PEGI",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/pegi/pegi_18.png",
    },
    6: {
        "rating": "RP",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_rp.png",
    },
    7: {
        "rating": "EC",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_ec.png",
    },
    8: {
        "rating": "E",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_e.png",
    },
    9: {
        "rating": "E10",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_e10.png",
    },
    10: {
        "rating": "T",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_t.png",
    },
    11: {
        "rating": "M",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_m.png",
    },
    12: {
        "rating": "AO",
        "category": "ESRB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/esrb/esrb_ao.png",
    },
    13: {
        "rating": "CERO_A",
        "category": "CERO",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_a.png",
    },
    14: {
        "rating": "CERO_B",
        "category": "CERO",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_b.png",
    },
    15: {
        "rating": "CERO_C",
        "category": "CERO",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_c.png",
    },
    16: {
        "rating": "CERO_D",
        "category": "CERO",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_d.png",
    },
    17: {
        "rating": "CERO_Z",
        "category": "CERO",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/cero/cero_z.png",
    },
    18: {
        "rating": "USK_0",
        "category": "USK",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_0.png",
    },
    19: {
        "rating": "USK_6",
        "category": "USK",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_6.png",
    },
    20: {
        "rating": "USK_12",
        "category": "USK",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_12.png",
    },
    21: {
        "rating": "USK_16",
        "category": "USK",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_16.png",
    },
    22: {
        "rating": "USK_18",
        "category": "USK",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/usk/usk_18.png",
    },
    23: {
        "rating": "GRAC_ALL",
        "category": "GRAC",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_all.png",
    },
    24: {
        "rating": "GRAC_Twelve",
        "category": "GRAC",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_12.png",
    },
    25: {
        "rating": "GRAC_Fifteen",
        "category": "GRAC",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_15.png",
    },
    26: {
        "rating": "GRAC_Eighteen",
        "category": "GRAC",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_18.png",
    },
    27: {
        "rating": "GRAC_TESTING",
        "category": "GRAC",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/grac/grac_testing.png",
    },
    28: {
        "rating": "CLASS_IND_L",
        "category": "CLASS_IND",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_l.png",
    },
    29: {
        "rating": "CLASS_IND_Ten",
        "category": "CLASS_IND",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_10.png",
    },
    30: {
        "rating": "CLASS_IND_Twelve",
        "category": "CLASS_IND",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/class_ind/class_ind_12.png",
    },
    31: {
        "rating": "ACB_G",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_g.png",
    },
    32: {
        "rating": "ACB_PG",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_pg.png",
    },
    33: {
        "rating": "ACB_M",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_m.png",
    },
    34: {
        "rating": "ACB_MA15",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_ma15.png",
    },
    35: {
        "rating": "ACB_R18",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_r18.png",
    },
    36: {
        "rating": "ACB_RC",
        "category": "ACB",
        "rating_cover_url": "https://www.igdb.com/icons/rating_icons/acb/acb_rc.png",
    },
}
