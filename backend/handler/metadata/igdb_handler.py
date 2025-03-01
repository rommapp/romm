import functools
import json
import re
from typing import Final, NotRequired, TypedDict

import httpx
import pydash
from adapters.services.igdb_types import GameType
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
                IGDB_AGE_RATINGS[r["rating_category"]]
                for r in rom.get("age_ratings", [])
                if r["rating_category"] in IGDB_AGE_RATINGS
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


class IGDBHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.igdb.com/v4"
        self.platform_endpoint = f"{self.BASE_URL}/platforms"
        self.platforms_fields = PLATFORMS_FIELDS
        self.platform_version_endpoint = f"{self.BASE_URL}/platform_versions"
        self.platform_version_fields = PLATFORMS_VERSION_FIELDS
        self.games_endpoint = f"{self.BASE_URL}/games"
        self.games_fields = GAMES_FIELDS
        self.search_endpoint = f"{self.BASE_URL}/search"
        self.search_fields = SEARCH_FIELDS
        self.pagination_limit = 500
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
        masked_headers = {}

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
        except httpx.LocalProtocolError as e:
            if str(e) == "Illegal header value b'Bearer '":
                log.critical("IGDB Error: Invalid IGDB_CLIENT_ID or IGDB_CLIENT_SECRET")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Invalid IGDB credentials",
                ) from e
            else:
                log.critical("Connection error: can't connect to IGDB")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Can't connect to IGDB, check your internet connection",
                ) from e
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to IGDB")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to IGDB, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            # Retry once if the auth token is invalid
            if exc.response.status_code != 401:
                log.error(exc)
                return []  # All requests to the IGDB API return a list

            # Attempt to force a token refresh if the token is invalid
            log.warning("Twitch token invalid: fetching a new one...")
            token = await self.twitch_auth._update_twitch_token()
            self.headers["Authorization"] = f"Bearer {token}"
        except json.decoder.JSONDecodeError as exc:
            # Log the error and return an empty list if the response is not valid JSON
            log.error(exc)
            return []
        except httpx.TimeoutException:
            pass

        # Retry once the request if it times out
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
            return res.json()
        except (httpx.HTTPError, json.decoder.JSONDecodeError) as exc:
            # Log the error and return an empty list if the request fails again
            log.error(exc)
            return []

    async def _search_rom(
        self, search_term: str, platform_igdb_id: int, with_game_type: bool = False
    ) -> dict | None:
        if not platform_igdb_id:
            return None

        search_term = uc(search_term)
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

        log.debug("Searching in games endpoint with game_type %s", game_type_filter)
        roms = await self._request(
            self.games_endpoint,
            data=f'search "{search_term}"; fields {",".join(self.games_fields)}; where platforms=[{platform_igdb_id}] {game_type_filter};',
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
    async def get_platforms(self) -> list[IGDBPlatform]:
        if not IGDB_API_ENABLED:
            return []

        platforms = await self._request(
            self.platform_endpoint,
            data=f'fields {",".join(self.platforms_fields)};',
        )

        return [
            IGDBPlatform(
                igdb_id=platform["id"],
                slug=platform["slug"],
                name=platform["name"],
                category=IGDB_PLATFORM_CATEGORIES.get(
                    platform.get("platform_type", 0), "Unknown"
                ),
                generation=platform.get("generation", None),
                family_name=pydash.get(platform, "platform_family.name", None),
                family_slug=pydash.get(platform, "platform_family.slug", None),
                url_logo=self._normalize_cover_url(
                    pydash.get(platform, "platform_logo.url", "").replace(
                        "t_thumb", "t_1080p"
                    )
                ),
            )
            for platform in platforms
        ]

    async def get_platform(self, slug: str) -> IGDBPlatform:
        platform = SLUG_TO_IGDB_PLATFORM.get(slug, None)

        if platform:
            return IGDBPlatform(
                igdb_id=platform.get("id", None),
                slug=slug,
                name=platform.get("name", slug),
                category=platform.get("category", "Unknown"),
                generation=str(platform.get("generation")) or "",
                family_name=pydash.get(platform, "platform_family.name", None),
                family_slug=pydash.get(platform, "platform_family.slug", None),
                url_logo=self._normalize_cover_url(
                    pydash.get(platform, "platform_logo.url", "").replace(
                        "t_thumb", "t_1080p"
                    )
                ),
            )

        # Check if platform is a version if not found
        platform_versions = await self._request(
            self.platform_version_endpoint,
            data=f'fields {",".join(self.platform_version_fields)}; where slug="{slug.lower()}";',
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
    async def get_rom(self, fs_name: str, platform_igdb_id: int) -> IGDBRom:
        from handler.filesystem import fs_rom_handler

        if not IGDB_API_ENABLED:
            return IGDBRom(igdb_id=None)

        if not platform_igdb_id:
            return IGDBRom(igdb_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = IGDBRom(igdb_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(fs_name)
        if platform_igdb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = IGDBRom(igdb_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
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

        # Split the search term since igdb struggles with colons
        if not rom and ":" in search_term:
            for term in search_term.split(":")[::-1]:
                log.debug(
                    "Searching for %s on IGDB without game_Type after splitting semicolon",
                    term,
                )
                rom = await self._search_rom(term, platform_igdb_id)
                if rom:
                    break

        # Some MAME games have two titles split by a slash
        if not rom and "/" in search_term:
            for term in search_term.split("/"):
                log.debug(
                    "Searching for %s on IGDB without game_Type after splitting slash",
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
    async def get_matched_rom_by_id(self, igdb_id: int) -> IGDBRom | None:
        if not IGDB_API_ENABLED:
            return None

        rom = await self.get_rom_by_id(igdb_id)
        return rom if rom["igdb_id"] else None

    @check_twitch_token
    async def get_matched_roms_by_name(
        self, search_term: str, platform_igdb_id: int | None
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
                        "igdb_slug": rom["slug"],
                        "name": rom["name"],
                        "summary": rom.get("summary", ""),
                        "url_cover": self._normalize_cover_url(
                            pydash.get(rom, "cover.url", "").replace(
                                "t_thumb", "t_1080p"
                            )
                        ),
                        "url_screenshots": [
                            self._normalize_cover_url(s.get("url", "")).replace(  # type: ignore[attr-defined]
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


PLATFORMS_FIELDS = (
    "id",
    "slug",
    "name",
    "platform_type",
    "generation",
    "platform_family.name",
    "platform_family.slug",
    "platform_logo.url",
)

PLATFORMS_VERSION_FIELDS = (
    "id",
    "name",
    "platform_logo.url",
)

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
)

SEARCH_FIELDS = ("game.id", "name")


class SlugToIGDBPlatform(TypedDict):
    id: int
    igdb_slug: str
    name: str
    category: str
    generation: int | None
    family_name: str | None
    family_slug: str | None
    url_logo: str | None


SLUG_TO_IGDB_PLATFORM: dict[str, SlugToIGDBPlatform] = {
    "1292apvs": {
        "id": 139,
        "name": "1292 Advanced Programmable Video System",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "1292-advanced-programmable-video-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yfdqsudagw0av25dawjr.jpg",
    },
    "3do": {
        "id": 50,
        "name": "3DO Interactive Multiplayer",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "3do",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7u.jpg",
    },
    "3ds": {
        "id": 37,
        "name": "Nintendo 3DS",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln6.jpg",
    },
    "n64dd": {
        "id": 416,
        "name": "64DD",
        "category": "Console",
        "generation": 5,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "64dd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj8.jpg",
    },
    "acornarchimedes": {
        "id": 116,
        "name": "Acorn Archimedes",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "acorn-archimedes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plas.jpg",
    },
    "acornelectron": {
        "id": 134,
        "name": "Acorn Electron",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "acorn-electron",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8d.jpg",
    },
    "amstradcpc": {
        "id": 25,
        "name": "Amstrad CPC",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "acpc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnh.jpg",
    },
    "picobeena": {
        "id": 507,
        "name": "Advanced Pico Beena",
        "category": "Console",
        "generation": 6,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "advanced-pico-beena",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plou.jpg",
    },
    "airconsole": {
        "id": 389,
        "name": "AirConsole",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "airconsole",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkq.jpg",
    },
    "amazonfiretv": {
        "id": 132,
        "name": "Amazon Fire TV",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "amazon-fire-tv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl91.jpg",
    },
    "amiga": {
        "id": 16,
        "name": "Amiga",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "amiga",
        "url_logo": "",
    },
    "amigacd32": {
        "id": 114,
        "name": "Amiga CD32",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "amiga-cd32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7v.jpg",
    },
    "gx4000": {
        "id": 506,
        "name": "Amstrad GX4000",
        "category": "Console",
        "generation": 3,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "amstrad-gx4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plot.jpg",
    },
    "amstradpcw": {
        "id": 154,
        "name": "Amstrad PCW",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "amstrad-pcw",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf7.jpg",
    },
    "android": {
        "id": 34,
        "name": "Android",
        "category": "Operative System",
        "generation": None,
        "family_name": "Linux",
        "family_slug": "linux",
        "igdb_slug": "android",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln3.jpg",
    },
    "apple2gs": {
        "id": 115,
        "name": "Apple IIGS",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "apple-iigs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl87.jpg",
    },
    "pippin": {
        "id": 476,
        "name": "Apple Pippin",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "apple-pippin",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnn.jpg",
    },
    "apple2": {
        "id": 75,
        "name": "Apple II",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "appleii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8r.jpg",
    },
    "arcade": {
        "id": 52,
        "name": "Arcade",
        "category": "Arcade",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "arcade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmz.jpg",
    },
    "arcadia": {
        "id": 473,
        "name": "Arcadia 2001",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "arcadia-2001",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnk.jpg",
    },
    "arduboy": {
        "id": 438,
        "name": "Arduboy",
        "category": "Portable Console",
        "generation": 8,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "arduboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk6.jpg",
    },
    "astrocade": {
        "id": 91,
        "name": "Bally Astrocade",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "astrocade",
        "url_logo": "",
    },
    "jaguarcd": {
        "id": 410,
        "name": "Atari Jaguar CD",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari-jaguar-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj4.jpg",
    },
    "atarist": {
        "id": 63,
        "name": "Atari ST/STE",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari-st",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla7.jpg",
    },
    "atari2600": {
        "id": 59,
        "name": "Atari 2600",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari2600",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln4.jpg",
    },
    "atari5200": {
        "id": 66,
        "name": "Atari 5200",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari5200",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8g.jpg",
    },
    "atari7800": {
        "id": 60,
        "name": "Atari 7800",
        "category": "Console",
        "generation": 3,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari7800",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8f.jpg",
    },
    "atari8bit": {
        "id": 65,
        "name": "Atari 8-bit",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "atari8bit",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plad.jpg",
    },
    "ay38500": {
        "id": 140,
        "name": "AY-3-8500",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8500",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/x42zeitpbuo2ltn7ybb2.jpg",
    },
    "ay38603": {
        "id": 145,
        "name": "AY-3-8603",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8603",
        "url_logo": "",
    },
    "ay38605": {
        "id": 146,
        "name": "AY-3-8605",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8605",
        "url_logo": "",
    },
    "ay38606": {
        "id": 147,
        "name": "AY-3-8606",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8606",
        "url_logo": "",
    },
    "ay38607": {
        "id": 148,
        "name": "AY-3-8607",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8607",
        "url_logo": "",
    },
    "ay38610": {
        "id": 141,
        "name": "AY-3-8610",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8610",
        "url_logo": "",
    },
    "ay38710": {
        "id": 144,
        "name": "AY-3-8710",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8710",
        "url_logo": "",
    },
    "ay38760": {
        "id": 143,
        "name": "AY-3-8760",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ay-3-8760",
        "url_logo": "",
    },
    "bbcmicro": {
        "id": 69,
        "name": "BBC Microcomputer System",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "bbcmicro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl86.jpg",
    },
    "blackberry": {
        "id": 73,
        "name": "BlackBerry OS",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "blackberry",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/bezbkk17hk0uobdkhjcv.jpg",
    },
    "bluray": {
        "id": 239,
        "name": "Blu-ray Player",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "blu-ray-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbv.jpg",
    },
    "browser": {
        "id": 82,
        "name": "Web browser",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "browser",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmx.jpg",
    },
    "cplus4": {
        "id": 94,
        "name": "Commodore Plus/4",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "c-plus-4",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8m.jpg",
    },
    "c16": {
        "id": 93,
        "name": "Commodore 16",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "c16",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf4.jpg",
    },
    "c64": {
        "id": 15,
        "name": "Commodore 64",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "c64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
    },
    "c128": {
        "id": 15,
        "name": "Commodore 128",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "c64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
    },
    "loopy": {
        "id": 380,
        "name": "Casio Loopy",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "casio-loopy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkm.jpg",
    },
    "colecovision": {
        "id": 68,
        "name": "ColecoVision",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "colecovision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8n.jpg",
    },
    "cdtv": {
        "id": 158,
        "name": "Commodore CDTV",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "commodore-cdtv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl84.jpg",
    },
    "cpet": {
        "id": 90,
        "name": "Commodore PET",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "cpet",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf3.jpg",
    },
    "dreamcast": {
        "id": 23,
        "name": "Dreamcast",
        "category": "Console",
        "generation": 6,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "dc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7i.jpg",
    },
    "digiblast": {
        "id": 486,
        "name": "Digiblast",
        "category": "Portable Console",
        "generation": 7,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "digiblast",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo2.jpg",
    },
    "dos": {
        "id": 13,
        "name": "DOS",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "dos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/sqgw6vespav1buezgjjn.jpg",
    },
    "dragon32": {
        "id": 153,
        "name": "Dragon 32/64",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "dragon-32-slash-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8e.jpg",
    },
    "dvd": {
        "id": 238,
        "name": "DVD Player",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "dvd-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbu.jpg",
    },
    "elektor-tv-games-computer": {
        "id": 505,
        "name": "Elektor TV Games Computer",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "elektor-tv-games-computer",
        "url_logo": "",
    },
    "ecv": {
        "id": 375,
        "name": "Epoch Cassette Vision",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "epoch-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plko.jpg",
    },
    "evercade": {
        "id": 309,
        "name": "Evercade",
        "category": "Portable Console",
        "generation": 8,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "evercade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plky.jpg",
    },
    "exidysorcerer": {
        "id": 236,
        "name": "Exidy Sorcerer",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "exidy-sorcerer",
        "url_logo": "",
    },
    "channelf": {
        "id": 127,
        "name": "Fairchild Channel F",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "fairchild-channel-f",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8s.jpg",
    },
    "famicom": {
        "id": 99,
        "name": "Family Computer",
        "category": "Console",
        "generation": 3,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnf.jpg",
    },
    "fds": {
        "id": 51,
        "name": "Family Computer Disk System",
        "category": "Console",
        "generation": 3,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "fds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8b.jpg",
    },
    "fm7": {
        "id": 152,
        "name": "FM-7",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "fm-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pley.jpg",
    },
    "fmtowns": {
        "id": 118,
        "name": "FM Towns",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "fm-towns",
        "url_logo": "",
    },
    "gameandwatch": {
        "id": 307,
        "name": "Game & Watch",
        "category": "Portable Console",
        "generation": 2,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "g-and-w",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pler.jpg",
    },
    "gamate": {
        "id": 378,
        "name": "Gamate",
        "category": "Portable Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "gamate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plhf.jpg",
    },
    "gamecom": {
        "id": 379,
        "name": "Game.com",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "game-dot-com",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgk.jpg",
    },
    "gamegear": {
        "id": 35,
        "name": "Sega Game Gear",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "gamegear",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7z.jpg",
    },
    "gb": {
        "id": 33,
        "name": "Game Boy",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "gb",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7m.jpg",
    },
    "gba": {
        "id": 24,
        "name": "Game Boy Advance",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "gba",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl74.jpg",
    },
    "gbc": {
        "id": 22,
        "name": "Game Boy Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "gbc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7l.jpg",
    },
    "gearvr": {
        "id": 388,
        "name": "Gear VR",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "gear-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkj.jpg",
    },
    "megadrive": {
        "id": 29,
        "name": "Sega Mega Drive/Genesis",
        "category": "Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "genesis-slash-megadrive",
        "url_logo": "",
    },
    "gizmondo": {
        "id": 474,
        "name": "Gizmondo",
        "category": "Portable Console",
        "generation": 7,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "gizmondo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnl.jpg",
    },
    "lcdgames": {
        "id": 411,
        "name": "Handheld Electronic LCD",
        "category": "Portable Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "handheld-electronic-lcd",
        "url_logo": "",
    },
    "hp2100": {
        "id": 104,
        "name": "HP 2100",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "hp2100",
        "url_logo": "",
    },
    "hp3000": {
        "id": 105,
        "name": "HP 3000",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "hp3000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla9.jpg",
    },
    "hyper-neo-geo-64": {
        "id": 135,
        "name": "Hyper Neo Geo 64",
        "category": "Arcade",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "hyper-neo-geo-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ubf1qgytr069wm0ikh0z.jpg",
    },
    "hyperscan": {
        "id": 407,
        "name": "HyperScan",
        "category": "Console",
        "generation": 7,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "hyperscan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj2.jpg",
    },
    "imlac-pds1": {
        "id": 111,
        "name": "Imlac PDS-1",
        "category": "Unknown",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "imlac-pds1",
        "url_logo": "",
    },
    "intellivision": {
        "id": 67,
        "name": "Intellivision",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "intellivision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8o.jpg",
    },
    "intellivision-amico": {
        "id": 382,
        "name": "Intellivision Amico",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "intellivision-amico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkp.jpg",
    },
    "ios": {
        "id": 39,
        "name": "iOS",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ios",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6w.jpg",
    },
    "jaguar": {
        "id": 62,
        "name": "Atari Jaguar",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "jaguar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7y.jpg",
    },
    "laseractive": {
        "id": 487,
        "name": "LaserActive",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "laseractive",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo4.jpg",
    },
    "leapster": {
        "id": 412,
        "name": "Leapster",
        "category": "Portable Console",
        "generation": 6,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "leapster",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj5.jpg",
    },
    "leapsterexplorer": {
        "id": 413,
        "name": "Leapster Explorer/LeadPad Explorer",
        "category": "Portable Console",
        "generation": 7,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "leapster-explorer-slash-leadpad-explorer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plna.jpg",
    },
    "leaptv": {
        "id": 414,
        "name": "LeapTV",
        "category": "Console",
        "generation": 8,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "leaptv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj6.jpg",
    },
    "legacypc": {
        "id": 409,
        "name": "Legacy Computer",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "legacy-computer",
        "url_logo": "",
    },
    "linux": {
        "id": 3,
        "name": "Linux",
        "category": "Operative System",
        "generation": None,
        "family_name": "Linux",
        "family_slug": "linux",
        "igdb_slug": "linux",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plak.jpg",
    },
    "lynx": {
        "id": 61,
        "name": "Atari Lynx",
        "category": "Portable Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "lynx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl82.jpg",
    },
    "mac": {
        "id": 14,
        "name": "Mac",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "mac",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo3.jpg",
    },
    "megaduck": {
        "id": 408,
        "name": "Mega Duck/Cougar Boy",
        "category": "Portable Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "mega-duck-slash-cougar-boy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj3.jpg",
    },
    "quest2": {
        "id": 386,
        "name": "Meta Quest 2",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "meta-quest-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll0.jpg",
    },
    "quest3": {
        "id": 471,
        "name": "Meta Quest 3",
        "category": "Console",
        "generation": 9,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "meta-quest-3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnb.jpg",
    },
    "microvision": {
        "id": 89,
        "name": "Microvision",
        "category": "Portable Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "microvision--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8q.jpg",
    },
    "mobile": {
        "id": 55,
        "name": "Legacy Mobile Device",
        "category": "Portable Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnd.jpg",
    },
    "msx": {
        "id": 27,
        "name": "MSX",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "msx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8j.jpg",
    },
    "msx2": {
        "id": 53,
        "name": "MSX2",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "msx2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8k.jpg",
    },
    "n64": {
        "id": 4,
        "name": "Nintendo 64",
        "category": "Console",
        "generation": 5,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "n64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl78.jpg",
    },
    "nds": {
        "id": 20,
        "name": "Nintendo DS",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "nds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6t.jpg",
    },
    "pc60": {
        "id": 157,
        "name": "NEC PC-6000 Series",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "nec-pc-6000-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaa.jpg",
    },
    "neogeocd": {
        "id": 136,
        "name": "Neo Geo CD",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "neo-geo-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7t.jpg",
    },
    "ngp": {
        "id": 119,
        "name": "Neo Geo Pocket",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "neo-geo-pocket",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plau.jpg",
    },
    "ngpc": {
        "id": 120,
        "name": "Neo Geo Pocket Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "neo-geo-pocket-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7h.jpg",
    },
    "neogeoaes": {
        "id": 80,
        "name": "Neo Geo AES",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "neogeoaes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hamfdrgnhenxb2d9g8mh.jpg",
    },
    "neogeomvs": {
        "id": 79,
        "name": "Neo Geo MVS",
        "category": "Arcade",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "neogeomvs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/cbhfilmhdgwdql8nzsy0.jpg",
    },
    "nes": {
        "id": 18,
        "name": "Nintendo Entertainment System",
        "category": "Console",
        "generation": 3,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "nes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmo.jpg",
    },
    "new3ds": {
        "id": 137,
        "name": "New Nintendo 3DS",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "new-nintendo-3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6j.jpg",
    },
    "ngage": {
        "id": 42,
        "name": "N-Gage",
        "category": "Portable Console",
        "generation": 6,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ngage",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl76.jpg",
    },
    "ngc": {
        "id": 21,
        "name": "Nintendo GameCube",
        "category": "Console",
        "generation": 6,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "ngc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7a.jpg",
    },
    "dsi": {
        "id": 159,
        "name": "Nintendo DSi",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "nintendo-dsi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6u.jpg",
    },
    "switch2": {
        "id": 508,
        "name": "Nintendo Switch 2",
        "category": "Console",
        "generation": 9,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "nintendo-switch-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plow.jpg",
    },
    "nuon": {
        "id": 122,
        "name": "Nuon",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "nuon",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7g.jpg",
    },
    "oculusgo": {
        "id": 387,
        "name": "Oculus Go",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "oculus-go",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkk.jpg",
    },
    "oculusquest": {
        "id": 384,
        "name": "Oculus Quest",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "oculus-quest",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plh7.jpg",
    },
    "oculusrift": {
        "id": 385,
        "name": "Oculus Rift",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "oculus-rift",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln8.jpg",
    },
    "oculusvr": {
        "id": 162,
        "name": "Oculus VR",
        "category": "Unknown",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "oculus-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pivaofe9ll2b8cqfvvbu.jpg",
    },
    "odyssey": {
        "id": 88,
        "name": "Odyssey",
        "category": "Console",
        "generation": 1,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "odyssey--1",
        "url_logo": "",
    },
    "odyssey2": {
        "id": 133,
        "name": "Odyssey 2 / Videopac G7000",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "odyssey-2-slash-videopac-g7000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fqwnmmpanb5se6ebccm3.jpg",
    },
    "onlive": {
        "id": 113,
        "name": "OnLive Game System",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "onlive-game-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plan.jpg",
    },
    "ooparts": {
        "id": 372,
        "name": "OOParts",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ooparts",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgi.jpg",
    },
    "ouya": {
        "id": 72,
        "name": "Ouya",
        "category": "Console",
        "generation": 8,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ouya",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6k.jpg",
    },
    "palmos": {
        "id": 417,
        "name": "Palm OS",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "palm-os",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj9.jpg",
    },
    "panasonicjungle": {
        "id": 477,
        "name": "Panasonic Jungle",
        "category": "Portable Console",
        "generation": 8,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "panasonic-jungle",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnp.jpg",
    },
    "panasonicm2": {
        "id": 478,
        "name": "Panasonic M2",
        "category": "Console",
        "generation": 6,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "panasonic-m2",
        "url_logo": "",
    },
    "pc50": {
        "id": 142,
        "name": "PC-50X Family",
        "category": "Console",
        "generation": 1,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pc-50x-family",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/dpwrkxrjkuxwqroqwjsw.jpg",
    },
    "pc88": {
        "id": 125,
        "name": "PC-8800 Series",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pc-8800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf2.jpg",
    },
    "pc98": {
        "id": 149,
        "name": "PC-9800 Series",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pc-9800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla6.jpg",
    },
    "pcfx": {
        "id": 274,
        "name": "PC-FX",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pc-fx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf8.jpg",
    },
    "pcenginecd": {
        "id": 150,
        "name": "Turbografx-16/PC Engine CD",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "turbografx-16-slash-pc-engine-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl83.jpg",
    },
    "pdp1": {
        "id": 95,
        "name": "PDP-1",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pdp1",
        "url_logo": "",
    },
    "pdp10": {
        "id": 96,
        "name": "PDP-10",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pdp10",
        "url_logo": "",
    },
    "pdp11": {
        "id": 108,
        "name": "PDP-11",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "pdp11",
        "url_logo": "",
    },
    "cdi": {
        "id": 117,
        "name": "Philips CD-i",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "philips-cd-i",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl80.jpg",
    },
    "pico": {
        "id": 339,
        "name": "Sega Pico",
        "category": "Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "sega-pico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgo.jpg",
    },
    "plato": {
        "id": 110,
        "name": "PLATO",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "plato--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaf.jpg",
    },
    "playdate": {
        "id": 381,
        "name": "Playdate",
        "category": "Portable Console",
        "generation": 9,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "playdate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgx.jpg",
    },
    "playdia": {
        "id": 308,
        "name": "Playdia",
        "category": "Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "playdia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ples.jpg",
    },
    "plugnplay": {
        "id": 377,
        "name": "Plug & Play",
        "category": "Platform",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "plug-and-play",
        "url_logo": "",
    },
    "pocketstation": {
        "id": 441,
        "name": "PocketStation",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "pocketstation",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkc.jpg",
    },
    "pokemini": {
        "id": 166,
        "name": "Pokémon mini",
        "category": "Portable Console",
        "generation": None,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "pokemon-mini",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7f.jpg",
    },
    "psx": {
        "id": 7,
        "name": "PlayStation",
        "category": "Console",
        "generation": 5,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "ps",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmb.jpg",
    },
    "ps2": {
        "id": 8,
        "name": "PlayStation 2",
        "category": "Console",
        "generation": 6,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "ps2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl72.jpg",
    },
    "ps3": {
        "id": 9,
        "name": "PlayStation 3",
        "category": "Console",
        "generation": 7,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "ps3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/tuyy1nrqodtmbqajp4jg.jpg",
    },
    "ps4": {
        "id": 48,
        "name": "PlayStation 4",
        "category": "Console",
        "generation": 8,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "ps4--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6f.jpg",
    },
    "ps5": {
        "id": 167,
        "name": "PlayStation 5",
        "category": "Console",
        "generation": 9,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "ps5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plos.jpg",
    },
    "psp": {
        "id": 38,
        "name": "PlayStation Portable",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "psp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5y.jpg",
    },
    "psvita": {
        "id": 46,
        "name": "PlayStation Vita",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "psvita",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6g.jpg",
    },
    "psvr": {
        "id": 165,
        "name": "PlayStation VR",
        "category": "Console",
        "generation": 8,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "psvr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnc.jpg",
    },
    "psvr2": {
        "id": 390,
        "name": "PlayStation VR2",
        "category": "Console",
        "generation": 9,
        "family_name": "PlayStation",
        "family_slug": "playstation",
        "igdb_slug": "psvr2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo5.jpg",
    },
    "rzone": {
        "id": 475,
        "name": "R-Zone",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "r-zone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnm.jpg",
    },
    "satellaview": {
        "id": 306,
        "name": "Satellaview",
        "category": "Console",
        "generation": 4,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "satellaview",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgj.jpg",
    },
    "saturn": {
        "id": 32,
        "name": "Sega Saturn",
        "category": "Console",
        "generation": 5,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "saturn",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hrmqljpwunky1all3v78.jpg",
    },
    "scv": {
        "id": 376,
        "name": "Epoch Super Cassette Vision",
        "category": "Console",
        "generation": 3,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "epoch-super-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkn.jpg",
    },
    "sdssigma7": {
        "id": 106,
        "name": "SDS Sigma 7",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sdssigma7",
        "url_logo": "",
    },
    "sega-cd-32x": {
        "id": 482,
        "name": "Sega CD 32X",
        "category": "Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "sega-cd-32x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnu.jpg",
    },
    "sega32": {
        "id": 30,
        "name": "Sega 32X",
        "category": "Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "sega32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7r.jpg",
    },
    "segacd": {
        "id": 78,
        "name": "Sega CD",
        "category": "Console",
        "generation": 4,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "segacd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7w.jpg",
    },
    "series-x-s": {
        "id": 169,
        "name": "Xbox Series X|S",
        "category": "Console",
        "generation": 9,
        "family_name": "Xbox",
        "family_slug": "xbox",
        "igdb_slug": "series-x-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plfl.jpg",
    },
    "sfam": {
        "id": 58,
        "name": "Super Famicom",
        "category": "Console",
        "generation": 4,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "sfam",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/a9x7xjy4p9sqynrvomcf.jpg",
    },
    "sg1000": {
        "id": 84,
        "name": "SG-1000",
        "category": "Console",
        "generation": 3,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "sg1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmn.jpg",
    },
    "sharp-mz-2200": {
        "id": 374,
        "name": "Sharp MZ-2200",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sharp-mz-2200",
        "url_logo": "",
    },
    "sharp-x68000": {
        "id": 121,
        "name": "Sharp X68000",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sharp-x68000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8i.jpg",
    },
    "sinclair-ql": {
        "id": 406,
        "name": "Sinclair QL",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sinclair-ql",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plih.jpg",
    },
    "sinclair-zx81": {
        "id": 373,
        "name": "Sinclair ZX81",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sinclair-zx81",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgr.jpg",
    },
    "sms": {
        "id": 64,
        "name": "Sega Master System/Mark III",
        "category": "Console",
        "generation": 3,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "sms",
        "url_logo": "",
    },
    "snes": {
        "id": 19,
        "name": "Super Nintendo Entertainment System",
        "category": "Console",
        "generation": 4,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "snes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ifw2tvdkynyxayquiyk4.jpg",
    },
    "sol-20": {
        "id": 237,
        "name": "Sol-20",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "sol-20",
        "url_logo": "",
    },
    "stadia": {
        "id": 170,
        "name": "Google Stadia",
        "category": "Platform",
        "generation": None,
        "family_name": "Linux",
        "family_slug": "linux",
        "igdb_slug": "stadia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl94.jpg",
    },
    "steam-vr": {
        "id": 163,
        "name": "SteamVR",
        "category": "Unknown",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "steam-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ipbdzzx7z3rwuzm9big4.jpg",
    },
    "super-acan": {
        "id": 480,
        "name": "Super A'Can",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "super-acan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plns.jpg",
    },
    "super-nes-cd-rom-system": {
        "id": 131,
        "name": "Super NES CD-ROM System",
        "category": "Console",
        "generation": 4,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "super-nes-cd-rom-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plep.jpg",
    },
    "supergrafx": {
        "id": 128,
        "name": "PC Engine SuperGrafx",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "supergrafx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla4.jpg",
    },
    "swancrystal": {
        "id": 124,
        "name": "SwanCrystal",
        "category": "Portable Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "swancrystal",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8v.jpg",
    },
    "switch": {
        "id": 130,
        "name": "Nintendo Switch",
        "category": "Console",
        "generation": 8,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "switch",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgu.jpg",
    },
    "tatung-einstein": {
        "id": 155,
        "name": "Tatung Einstein",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "tatung-einstein",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla8.jpg",
    },
    "terebikko-slash-see-n-say-video-phone": {
        "id": 479,
        "name": "Terebikko / See 'n Say Video Phone",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "terebikko-slash-see-n-say-video-phone",
        "url_logo": "",
    },
    "thomson": {
        "id": 156,
        "name": "Thomson MO5",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "thomson-mo5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plex.jpg",
    },
    "ti-99": {
        "id": 129,
        "name": "Texas Instruments TI-99",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "ti-99",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf0.jpg",
    },
    "tomy-tutor-slash-pyuta-slash-grandstand-tutor": {
        "id": 481,
        "name": "Tomy Tutor / Pyuta / Grandstand Tutor",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "tomy-tutor-slash-pyuta-slash-grandstand-tutor",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnt.jpg",
    },
    "trs-80": {
        "id": 126,
        "name": "TRS-80",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "trs-80",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plac.jpg",
    },
    "trs-80-color-computer": {
        "id": 151,
        "name": "TRS-80 Color Computer",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "trs-80-color-computer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf1.jpg",
    },
    "turbografx16--1": {
        "id": 86,
        "name": "TurboGrafx-16/PC Engine",
        "category": "Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "turbografx16--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl88.jpg",
    },
    "uzebox": {
        "id": 504,
        "name": "Uzebox",
        "category": "Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "uzebox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plor.jpg",
    },
    "vc": {
        "id": 47,
        "name": "Virtual Console",
        "category": "Platform",
        "generation": None,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "vc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plao.jpg",
    },
    "vc-4000": {
        "id": 138,
        "name": "VC 4000",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "vc-4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/phikgyfmv1fevj2jhzr5.jpg",
    },
    "vectrex": {
        "id": 70,
        "name": "Vectrex",
        "category": "Console",
        "generation": 2,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "vectrex",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8h.jpg",
    },
    "vic-20": {
        "id": 71,
        "name": "Commodore VIC-20",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "vic-20",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8p.jpg",
    },
    "virtualboy": {
        "id": 87,
        "name": "Virtual Boy",
        "category": "Console",
        "generation": 5,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "virtualboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7s.jpg",
    },
    "visionos": {
        "id": 472,
        "name": "visionOS",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "visionos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnj.jpg",
    },
    "visual-memory-unit-slash-visual-memory-system": {
        "id": 440,
        "name": "Visual Memory Unit / Visual Memory System",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "Sega",
        "family_slug": "sega",
        "igdb_slug": "visual-memory-unit-slash-visual-memory-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk8.jpg",
    },
    "vsmile": {
        "id": 439,
        "name": "V.Smile",
        "category": "Console",
        "generation": 6,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "vsmile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk7.jpg",
    },
    "watara-slash-quickshot-supervision": {
        "id": 415,
        "name": "Watara/QuickShot Supervision",
        "category": "Portable Console",
        "generation": 4,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "watara-slash-quickshot-supervision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj7.jpg",
    },
    "wii": {
        "id": 5,
        "name": "Wii",
        "category": "Console",
        "generation": 7,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "wii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl92.jpg",
    },
    "wiiu": {
        "id": 41,
        "name": "Wii U",
        "category": "Console",
        "generation": 8,
        "family_name": "Nintendo",
        "family_slug": "nintendo",
        "igdb_slug": "wiiu",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6n.jpg",
    },
    "win": {
        "id": 6,
        "name": "PC (Microsoft Windows)",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "win",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plim.jpg",
    },
    "windows-mixed-reality": {
        "id": 161,
        "name": "Windows Mixed Reality",
        "category": "Unknown",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "windows-mixed-reality",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm4.jpg",
    },
    "windows-mobile": {
        "id": 405,
        "name": "Windows Mobile",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "windows-mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkl.jpg",
    },
    "winphone": {
        "id": 74,
        "name": "Windows Phone",
        "category": "Operative System",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "winphone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla3.jpg",
    },
    "wonderswan": {
        "id": 57,
        "name": "WonderSwan",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "wonderswan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7b.jpg",
    },
    "wonderswan-color": {
        "id": 123,
        "name": "WonderSwan Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "wonderswan-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl79.jpg",
    },
    "x1": {
        "id": 77,
        "name": "Sharp X1",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "x1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl89.jpg",
    },
    "xbox": {
        "id": 11,
        "name": "Xbox",
        "category": "Console",
        "generation": 6,
        "family_name": "Xbox",
        "family_slug": "xbox",
        "igdb_slug": "xbox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7e.jpg",
    },
    "xbox360": {
        "id": 12,
        "name": "Xbox 360",
        "category": "Console",
        "generation": 7,
        "family_name": "Xbox",
        "family_slug": "xbox",
        "igdb_slug": "xbox360",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plha.jpg",
    },
    "xboxone": {
        "id": 49,
        "name": "Xbox One",
        "category": "Console",
        "generation": 8,
        "family_name": "Xbox",
        "family_slug": "xbox",
        "igdb_slug": "xboxone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl95.jpg",
    },
    "zeebo": {
        "id": 240,
        "name": "Zeebo",
        "category": "Console",
        "generation": 7,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "zeebo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbx.jpg",
    },
    "zod": {
        "id": 44,
        "name": "Tapwave Zodiac",
        "category": "Portable Console",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "zod",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lfsdnlko80ftakbugceu.jpg",
    },
    "zxs": {
        "id": 26,
        "name": "ZX Spectrum",
        "category": "Computer",
        "generation": None,
        "family_name": None,
        "family_slug": None,
        "igdb_slug": "zxs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plab.jpg",
    },
}


# Reverse lookup
IGDB_ID_TO_PLATFORM = {v["id"]: k for k, v in SLUG_TO_IGDB_PLATFORM.items()}

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
