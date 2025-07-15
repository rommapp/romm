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
    BaseRom,
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
    generation: NotRequired[int]
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


class IGDBRom(BaseRom):
    igdb_id: int | None
    slug: NotRequired[str]
    igdb_metadata: NotRequired[IGDBMetadata]


def extract_metadata_from_igdb_rom(self: MetadataHandler, rom: dict) -> IGDBMetadata:
    return IGDBMetadata(
        {
            "youtube_video_id": pydash.get(rom, "videos[0].video_id", None),
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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
                    cover_url=self.normalize_cover_url(
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

    async def _request(self, url: str, data: str) -> list:
        httpx_client = ctx_httpx_client.get()
        masked_headers = {}

        try:
            masked_headers = self._mask_sensitive_values(self.headers)
            log.debug(
                "API request: URL=%s, Headers=%s, Content=%s, Timeout=%s",
                url,
                masked_headers,
                f"{data} limit {self.pagination_limit};",
                120,
            )
            res = await httpx_client.post(
                url,
                content=f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=120,
            )

            res.raise_for_status()
            return res.json()
        except httpx.LocalProtocolError as exc:
            if str(exc) == "Illegal header value b'Bearer '":
                log.critical("IGDB Error: Invalid IGDB_CLIENT_ID or IGDB_CLIENT_SECRET")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Invalid IGDB credentials",
                ) from exc
            else:
                log.critical("Connection error: can't connect to IGDB")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Can't connect to IGDB, check your internet connection",
                ) from exc
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
            log.info("Twitch token invalid: fetching a new one...")
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
                120,
            )
            res = await httpx_client.post(
                url,
                content=f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=120,
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

            # Check both the ROM name and alternative names for an exact match.
            rom_names = [rom["name"]] + [
                alternative_name["name"]
                for alternative_name in rom.get("alternative_names", [])
            ]

            return any(
                (
                    rom_name.lower() == search_term_lower
                    or self.normalize_search_term(rom_name) == search_term
                )
                for rom_name in rom_names
            )

        log.debug("Searching in games endpoint with game_type %s", game_type_filter)
        roms = await self._request(
            self.games_endpoint,
            data=f'search "{uc(search_term)}"; fields {",".join(self.games_fields)}; where platforms=[{platform_igdb_id}] {game_type_filter};',
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
        platform = IGDB_PLATFORM_LIST.get(slug, None)

        if platform:
            return IGDBPlatform(
                igdb_id=platform["id"],
                slug=slug,
                name=platform["name"],
                category=platform["category"],
                generation=platform["generation"],
                family_name=platform["family_name"],
                family_slug=platform["family_slug"],
                url=platform["url"],
                url_logo=self.normalize_cover_url(platform["url_logo"]),
            )

        platform_version = IGDB_PLATFORM_VERSIONS.get(slug, None)
        if platform_version:
            return IGDBPlatform(
                igdb_id=platform_version["id"],
                slug=platform_version["platform_slug"],
                name=platform_version["name"],
                url=platform_version["url"],
                url_logo=self.normalize_cover_url(platform_version["url_logo"]),
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

        # IGDB search is fuzzy so no need to split the search term by special characters
        if not rom:
            return fallback_rom

        return IGDBRom(
            igdb_id=rom["id"],
            slug=rom["slug"],
            name=rom["name"],
            summary=rom.get("summary", ""),
            url_cover=self.normalize_cover_url(
                pydash.get(rom, "cover.url", "")
            ).replace("t_thumb", "t_1080p"),
            url_screenshots=[
                self.normalize_cover_url(s.get("url", "")).replace("t_thumb", "t_720p")
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(self, rom),
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
            url_cover=self.normalize_cover_url(
                pydash.get(rom, "cover.url", "")
            ).replace("t_thumb", "t_1080p"),
            url_screenshots=[
                self.normalize_cover_url(s.get("url", "")).replace("t_thumb", "t_720p")
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(self, rom),
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

        matched_roms = await self._request(
            self.games_endpoint,
            data=f'search "{uc(search_term)}"; fields {",".join(self.games_fields)}; where platforms=[{platform_igdb_id}];',
        )

        alternative_matched_roms = await self._request(
            self.search_endpoint,
            data=f'fields {",".join(self.search_fields)}; where game.platforms=[{platform_igdb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*);',
        )

        if alternative_matched_roms:
            alternative_roms_ids = []
            for rom in alternative_matched_roms:
                alternative_roms_ids.append(
                    pydash.get(rom, "game.id", "")
                    if "game" in rom.keys()
                    else rom.get("id", "")
                )
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
                        "url_cover": self.normalize_cover_url(
                            pydash.get(rom, "cover.url", "").replace(
                                "t_thumb", "t_1080p"
                            )
                        ),
                        "url_screenshots": [
                            self.normalize_cover_url(s.get("url", "")).replace(  # type: ignore[attr-defined]
                                "t_thumb", "t_720p"
                            )
                            for s in rom.get("screenshots", [])
                        ],
                        "igdb_metadata": extract_metadata_from_igdb_rom(self, rom),
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
            log.info("Twitch token invalid: fetching a new one...")
            return await self._update_twitch_token()

        return token


PLATFORMS_FIELDS = (
    "id",
    "slug",
    "name",
    "platform_type",
    "generation",
    "url",
    "platform_family.name",
    "platform_family.slug",
    "platform_logo.url",
)

PLATFORMS_VERSION_FIELDS = (
    "id",
    "slug",
    "name",
    "url",
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


IGDB_PLATFORM_CATEGORIES: dict[int, str] = {
    0: "Unknown",
    1: "Console",
    2: "Arcade",
    3: "Platform",
    4: "Operative System",
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


IGDB_PLATFORM_LIST: dict[str, SlugToIGDB] = {
    "satellaview": {
        "id": 306,
        "slug": "satellaview",
        "name": "Satellaview",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/satellaview",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgj.jpg",
    },
    "sega-pico": {
        "id": 339,
        "slug": "sega-pico",
        "name": "Sega Pico",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sega-pico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgo.jpg",
    },
    "epoch-super-cassette-vision": {
        "id": 376,
        "slug": "epoch-super-cassette-vision",
        "name": "Epoch Super Cassette Vision",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/epoch-super-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkn.jpg",
    },
    "xbox360": {
        "id": 12,
        "slug": "xbox360",
        "name": "Xbox 360",
        "category": "Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/xbox360",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plha.jpg",
    },
    "saturn": {
        "id": 32,
        "slug": "saturn",
        "name": "Sega Saturn",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/saturn",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hrmqljpwunky1all3v78.jpg",
    },
    "jaguar": {
        "id": 62,
        "slug": "jaguar",
        "name": "Atari Jaguar",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/jaguar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7y.jpg",
    },
    "ay-3-8607": {
        "id": 148,
        "slug": "ay-3-8607",
        "name": "AY-3-8607",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8607",
        "url_logo": "",
    },
    "turbografx-16-slash-pc-engine-cd": {
        "id": 150,
        "slug": "turbografx-16-slash-pc-engine-cd",
        "name": "Turbografx-16/PC Engine CD",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/turbografx-16-slash-pc-engine-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl83.jpg",
    },
    "thomson-mo5": {
        "id": 156,
        "slug": "thomson-mo5",
        "name": "Thomson MO5",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/thomson-mo5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plex.jpg",
    },
    "e-reader-slash-card-e-reader": {
        "id": 510,
        "slug": "e-reader-slash-card-e-reader",
        "name": "e-Reader / Card-e Reader",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploy.jpg",
    },
    "evercade": {
        "id": 309,
        "slug": "evercade",
        "name": "Evercade",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/evercade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plky.jpg",
    },
    "airconsole": {
        "id": 389,
        "slug": "airconsole",
        "name": "AirConsole",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/airconsole",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkq.jpg",
    },
    "dos": {
        "id": 13,
        "slug": "dos",
        "name": "DOS",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/dos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/sqgw6vespav1buezgjjn.jpg",
    },
    "wiiu": {
        "id": 41,
        "slug": "wiiu",
        "name": "Wii U",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/wiiu",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6n.jpg",
    },
    "atari7800": {
        "id": 60,
        "slug": "atari7800",
        "name": "Atari 7800",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari7800",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8f.jpg",
    },
    "microcomputer--1": {
        "id": 112,
        "slug": "microcomputer--1",
        "name": "Microcomputer",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/microcomputer--1",
        "url_logo": "",
    },
    "atari-jaguar-cd": {
        "id": 410,
        "slug": "atari-jaguar-cd",
        "name": "Atari Jaguar CD",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari-jaguar-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj4.jpg",
    },
    "sega32": {
        "id": 30,
        "slug": "sega32",
        "name": "Sega 32X",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sega32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7r.jpg",
    },
    "msx2": {
        "id": 53,
        "slug": "msx2",
        "name": "MSX2",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/msx2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8k.jpg",
    },
    "lynx": {
        "id": 61,
        "slug": "lynx",
        "name": "Atari Lynx",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/lynx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl82.jpg",
    },
    "x1": {
        "id": 77,
        "slug": "x1",
        "name": "Sharp X1",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/x1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl89.jpg",
    },
    "neo-geo-pocket-color": {
        "id": 120,
        "slug": "neo-geo-pocket-color",
        "name": "Neo Geo Pocket Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/neo-geo-pocket-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7h.jpg",
    },
    "fairchild-channel-f": {
        "id": 127,
        "slug": "fairchild-channel-f",
        "name": "Fairchild Channel F",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/fairchild-channel-f",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8s.jpg",
    },
    "amazon-fire-tv": {
        "id": 132,
        "slug": "amazon-fire-tv",
        "name": "Amazon Fire TV",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/amazon-fire-tv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl91.jpg",
    },
    "leapster-explorer-slash-leadpad-explorer": {
        "id": 413,
        "slug": "leapster-explorer-slash-leadpad-explorer",
        "name": "Leapster Explorer/LeadPad Explorer",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/leapster-explorer-slash-leadpad-explorer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plna.jpg",
    },
    "ay-3-8500": {
        "id": 140,
        "slug": "ay-3-8500",
        "name": "AY-3-8500",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8500",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/x42zeitpbuo2ltn7ybb2.jpg",
    },
    "ay-3-8760": {
        "id": 143,
        "slug": "ay-3-8760",
        "name": "AY-3-8760",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8760",
        "url_logo": "",
    },
    "dragon-32-slash-64": {
        "id": 153,
        "slug": "dragon-32-slash-64",
        "name": "Dragon 32/64",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/dragon-32-slash-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8e.jpg",
    },
    "amstrad-pcw": {
        "id": 154,
        "slug": "amstrad-pcw",
        "name": "Amstrad PCW",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/amstrad-pcw",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf7.jpg",
    },
    "ps5": {
        "id": 167,
        "slug": "ps5",
        "name": "PlayStation 5",
        "category": "Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ps5",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plos.jpg",
    },
    "vectrex": {
        "id": 70,
        "slug": "vectrex",
        "name": "Vectrex",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/vectrex",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8h.jpg",
    },
    "virtualboy": {
        "id": 87,
        "slug": "virtualboy",
        "name": "Virtual Boy",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/virtualboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7s.jpg",
    },
    "ay-3-8603": {
        "id": 145,
        "slug": "ay-3-8603",
        "name": "AY-3-8603",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8603",
        "url_logo": "",
    },
    "meta-quest-2": {
        "id": 386,
        "slug": "meta-quest-2",
        "name": "Meta Quest 2",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/meta-quest-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll0.jpg",
    },
    "psvr2": {
        "id": 390,
        "slug": "psvr2",
        "name": "PlayStation VR2",
        "category": "Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/psvr2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo5.jpg",
    },
    "panasonic-jungle": {
        "id": 477,
        "slug": "panasonic-jungle",
        "name": "Panasonic Jungle",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/panasonic-jungle",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnp.jpg",
    },
    "uzebox": {
        "id": 504,
        "slug": "uzebox",
        "name": "Uzebox",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/uzebox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plor.jpg",
    },
    "atari8bit": {
        "id": 65,
        "slug": "atari8bit",
        "name": "Atari 8-bit",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari8bit",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plad.jpg",
    },
    "commodore-cdtv": {
        "id": 158,
        "slug": "commodore-cdtv",
        "name": "Commodore CDTV",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/commodore-cdtv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl84.jpg",
    },
    "psvr": {
        "id": 165,
        "slug": "psvr",
        "name": "PlayStation VR",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/psvr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnc.jpg",
    },
    "visual-memory-unit-slash-visual-memory-system": {
        "id": 440,
        "slug": "visual-memory-unit-slash-visual-memory-system",
        "name": "Visual Memory Unit / Visual Memory System",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/visual-memory-unit-slash-visual-memory-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk8.jpg",
    },
    "arcadia-2001": {
        "id": 473,
        "slug": "arcadia-2001",
        "name": "Arcadia 2001",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/arcadia-2001",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnk.jpg",
    },
    "gizmondo": {
        "id": 474,
        "slug": "gizmondo",
        "name": "Gizmondo",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gizmondo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnl.jpg",
    },
    "ps4--1": {
        "id": 48,
        "slug": "ps4--1",
        "name": "PlayStation 4",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ps4--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6f.jpg",
    },
    "fds": {
        "id": 51,
        "slug": "fds",
        "name": "Family Computer Disk System",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/fds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8b.jpg",
    },
    "microvision--1": {
        "id": 89,
        "slug": "microvision--1",
        "name": "Microvision",
        "category": "Portable Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/microvision--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8q.jpg",
    },
    "c-plus-4": {
        "id": 94,
        "slug": "c-plus-4",
        "name": "Commodore Plus/4",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/c-plus-4",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8m.jpg",
    },
    "wonderswan-color": {
        "id": 123,
        "slug": "wonderswan-color",
        "name": "WonderSwan Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/wonderswan-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl79.jpg",
    },
    "supergrafx": {
        "id": 128,
        "slug": "supergrafx",
        "name": "PC Engine SuperGrafx",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/supergrafx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla4.jpg",
    },
    "ti-99": {
        "id": 129,
        "slug": "ti-99",
        "name": "Texas Instruments TI-99",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ti-99",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf0.jpg",
    },
    "sega-cd-32x": {
        "id": 482,
        "slug": "sega-cd-32x",
        "name": "Sega CD 32X",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sega-cd-32x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnu.jpg",
    },
    "linux": {
        "id": 3,
        "slug": "linux",
        "name": "Linux",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/linux",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plak.jpg",
    },
    "win": {
        "id": 6,
        "slug": "win",
        "name": "PC (Microsoft Windows)",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/win",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plim.jpg",
    },
    "ps2": {
        "id": 8,
        "slug": "ps2",
        "name": "PlayStation 2",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ps2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl72.jpg",
    },
    "dc": {
        "id": 23,
        "slug": "dc",
        "name": "Dreamcast",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/dc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7i.jpg",
    },
    "gamegear": {
        "id": 35,
        "slug": "gamegear",
        "name": "Sega Game Gear",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gamegear",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7z.jpg",
    },
    "ios": {
        "id": 39,
        "slug": "ios",
        "name": "iOS",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ios",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6w.jpg",
    },
    "zod": {
        "id": 44,
        "slug": "zod",
        "name": "Tapwave Zodiac",
        "category": "Portable Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/zod",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lfsdnlko80ftakbugceu.jpg",
    },
    "odyssey--1": {
        "id": 88,
        "slug": "odyssey--1",
        "name": "Odyssey",
        "category": "Console",
        "generation": 1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/odyssey--1",
        "url_logo": "",
    },
    "pdp-8--1": {
        "id": 97,
        "slug": "pdp-8--1",
        "name": "PDP-8",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pdp-8--1",
        "url_logo": "",
    },
    "acorn-electron": {
        "id": 134,
        "slug": "acorn-electron",
        "name": "Acorn Electron",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/acorn-electron",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8d.jpg",
    },
    "neo-geo-cd": {
        "id": 136,
        "slug": "neo-geo-cd",
        "name": "Neo Geo CD",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/neo-geo-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7t.jpg",
    },
    "sinclair-zx81": {
        "id": 373,
        "slug": "sinclair-zx81",
        "name": "Sinclair ZX81",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sinclair-zx81",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgr.jpg",
    },
    "elektor-tv-games-computer": {
        "id": 505,
        "slug": "elektor-tv-games-computer",
        "name": "Elektor TV Games Computer",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/elektor-tv-games-computer",
        "url_logo": "",
    },
    "gba": {
        "id": 24,
        "slug": "gba",
        "name": "Game Boy Advance",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gba",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl74.jpg",
    },
    "ouya": {
        "id": 72,
        "slug": "ouya",
        "name": "Ouya",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ouya",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6k.jpg",
    },
    "donner30": {
        "id": 85,
        "slug": "donner30",
        "name": "Donner Model 30",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/donner30",
        "url_logo": "",
    },
    "steam-vr": {
        "id": 163,
        "slug": "steam-vr",
        "name": "SteamVR",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/steam-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ipbdzzx7z3rwuzm9big4.jpg",
    },
    "apple-iigs": {
        "id": 115,
        "slug": "apple-iigs",
        "name": "Apple IIGS",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/apple-iigs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl87.jpg",
    },
    "neo-geo-pocket": {
        "id": 119,
        "slug": "neo-geo-pocket",
        "name": "Neo Geo Pocket",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/neo-geo-pocket",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plau.jpg",
    },
    "pc-8800-series": {
        "id": 125,
        "slug": "pc-8800-series",
        "name": "PC-8800 Series",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pc-8800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf2.jpg",
    },
    "odyssey-2-slash-videopac-g7000": {
        "id": 133,
        "slug": "odyssey-2-slash-videopac-g7000",
        "name": "Odyssey 2 / Videopac G7000",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/odyssey-2-slash-videopac-g7000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fqwnmmpanb5se6ebccm3.jpg",
    },
    "hyper-neo-geo-64": {
        "id": 135,
        "slug": "hyper-neo-geo-64",
        "name": "Hyper Neo Geo 64",
        "category": "Arcade",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/hyper-neo-geo-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ubf1qgytr069wm0ikh0z.jpg",
    },
    "pc-50x-family": {
        "id": 142,
        "slug": "pc-50x-family",
        "name": "PC-50X Family",
        "category": "Console",
        "generation": 1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pc-50x-family",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/dpwrkxrjkuxwqroqwjsw.jpg",
    },
    "ay-3-8710": {
        "id": 144,
        "slug": "ay-3-8710",
        "name": "AY-3-8710",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8710",
        "url_logo": "",
    },
    "ay-3-8605": {
        "id": 146,
        "slug": "ay-3-8605",
        "name": "AY-3-8605",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8605",
        "url_logo": "",
    },
    "ay-3-8606": {
        "id": 147,
        "slug": "ay-3-8606",
        "name": "AY-3-8606",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8606",
        "url_logo": "",
    },
    "pc-9800-series": {
        "id": 149,
        "slug": "pc-9800-series",
        "name": "PC-9800 Series",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pc-9800-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla6.jpg",
    },
    "sol-20": {
        "id": 237,
        "slug": "sol-20",
        "name": "Sol-20",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sol-20",
        "url_logo": "",
    },
    "sega-cd": {
        "id": 78,
        "slug": "sega-cd",
        "name": "Sega CD",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sega-cd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7w.jpg",
    },
    "gt40": {
        "id": 98,
        "slug": "gt40",
        "name": "DEC GT40",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gt40",
        "url_logo": "",
    },
    "imlac-pds1": {
        "id": 111,
        "slug": "imlac-pds1",
        "name": "Imlac PDS-1",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/imlac-pds1",
        "url_logo": "",
    },
    "oculus-vr": {
        "id": 162,
        "slug": "oculus-vr",
        "name": "Oculus VR",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/oculus-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pivaofe9ll2b8cqfvvbu.jpg",
    },
    "g-and-w": {
        "id": 307,
        "slug": "g-and-w",
        "name": "Game & Watch",
        "category": "Portable Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/g-and-w",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pler.jpg",
    },
    "playdia": {
        "id": 308,
        "slug": "playdia",
        "name": "Playdia",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/playdia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ples.jpg",
    },
    "amstrad-gx4000": {
        "id": 506,
        "slug": "amstrad-gx4000",
        "name": "Amstrad GX4000",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/amstrad-gx4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plot.jpg",
    },
    "ps3": {
        "id": 9,
        "slug": "ps3",
        "name": "PlayStation 3",
        "category": "Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ps3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/tuyy1nrqodtmbqajp4jg.jpg",
    },
    "xbox": {
        "id": 11,
        "slug": "xbox",
        "name": "Xbox",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/xbox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7e.jpg",
    },
    "c64": {
        "id": 15,
        "slug": "c64",
        "name": "Commodore C64/128/MAX",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/c64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
    },
    "nds": {
        "id": 20,
        "slug": "nds",
        "name": "Nintendo DS",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6t.jpg",
    },
    "gbc": {
        "id": 22,
        "slug": "gbc",
        "name": "Game Boy Color",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gbc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7l.jpg",
    },
    "psvita": {
        "id": 46,
        "slug": "psvita",
        "name": "PlayStation Vita",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/psvita",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6g.jpg",
    },
    "atari5200": {
        "id": 66,
        "slug": "atari5200",
        "name": "Atari 5200",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari5200",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8g.jpg",
    },
    "intellivision": {
        "id": 67,
        "slug": "intellivision",
        "name": "Intellivision",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/intellivision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8o.jpg",
    },
    "blackberry": {
        "id": 73,
        "slug": "blackberry",
        "name": "BlackBerry OS",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/blackberry",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/bezbkk17hk0uobdkhjcv.jpg",
    },
    "turbografx16--1": {
        "id": 86,
        "slug": "turbografx16--1",
        "name": "TurboGrafx-16/PC Engine",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/turbografx16--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl88.jpg",
    },
    "nimrod": {
        "id": 101,
        "slug": "nimrod",
        "name": "Ferranti Nimrod Computer",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nimrod",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaq.jpg",
    },
    "pdp11": {
        "id": 108,
        "slug": "pdp11",
        "name": "PDP-11",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pdp11",
        "url_logo": "",
    },
    "cdccyber70": {
        "id": 109,
        "slug": "cdccyber70",
        "name": "CDC Cyber 70",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/cdccyber70",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plae.jpg",
    },
    "onlive-game-system": {
        "id": 113,
        "slug": "onlive-game-system",
        "name": "OnLive Game System",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/onlive-game-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plan.jpg",
    },
    "amiga-cd32": {
        "id": 114,
        "slug": "amiga-cd32",
        "name": "Amiga CD32",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/amiga-cd32",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7v.jpg",
    },
    "acorn-archimedes": {
        "id": 116,
        "slug": "acorn-archimedes",
        "name": "Acorn Archimedes",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/acorn-archimedes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plas.jpg",
    },
    "philips-cd-i": {
        "id": 117,
        "slug": "philips-cd-i",
        "name": "Philips CD-i",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/philips-cd-i",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl80.jpg",
    },
    "fm-towns": {
        "id": 118,
        "slug": "fm-towns",
        "name": "FM Towns",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/fm-towns",
        "url_logo": "",
    },
    "sharp-x68000": {
        "id": 121,
        "slug": "sharp-x68000",
        "name": "Sharp X68000",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sharp-x68000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8i.jpg",
    },
    "swancrystal": {
        "id": 124,
        "slug": "swancrystal",
        "name": "SwanCrystal",
        "category": "Portable Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/swancrystal",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8v.jpg",
    },
    "super-nes-cd-rom-system": {
        "id": 131,
        "slug": "super-nes-cd-rom-system",
        "name": "Super NES CD-ROM System",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/super-nes-cd-rom-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plep.jpg",
    },
    "vc-4000": {
        "id": 138,
        "slug": "vc-4000",
        "name": "VC 4000",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/vc-4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/phikgyfmv1fevj2jhzr5.jpg",
    },
    "1292-advanced-programmable-video-system": {
        "id": 139,
        "slug": "1292-advanced-programmable-video-system",
        "name": "1292 Advanced Programmable Video System",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yfdqsudagw0av25dawjr.jpg",
    },
    "fm-7": {
        "id": 152,
        "slug": "fm-7",
        "name": "FM-7",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/fm-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pley.jpg",
    },
    "tatung-einstein": {
        "id": 155,
        "slug": "tatung-einstein",
        "name": "Tatung Einstein",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/tatung-einstein",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla8.jpg",
    },
    "nec-pc-6000-series": {
        "id": 157,
        "slug": "nec-pc-6000-series",
        "name": "NEC PC-6000 Series",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nec-pc-6000-series",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaa.jpg",
    },
    "nes": {
        "id": 18,
        "slug": "nes",
        "name": "Nintendo Entertainment System",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmo.jpg",
    },
    "windows-mixed-reality": {
        "id": 161,
        "slug": "windows-mixed-reality",
        "name": "Windows Mixed Reality",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/windows-mixed-reality",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm4.jpg",
    },
    "pdp-7--1": {
        "id": 103,
        "slug": "pdp-7--1",
        "name": "PDP-7",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pdp-7--1",
        "url_logo": "",
    },
    "sharp-mz-2200": {
        "id": 374,
        "slug": "sharp-mz-2200",
        "name": "Sharp MZ-2200",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sharp-mz-2200",
        "url_logo": "",
    },
    "epoch-cassette-vision": {
        "id": 375,
        "slug": "epoch-cassette-vision",
        "name": "Epoch Cassette Vision",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/epoch-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plko.jpg",
    },
    "plug-and-play": {
        "id": 377,
        "slug": "plug-and-play",
        "name": "Plug & Play",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/plug-and-play",
        "url_logo": "",
    },
    "game-dot-com": {
        "id": 379,
        "slug": "game-dot-com",
        "name": "Game.com",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/game-dot-com",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgk.jpg",
    },
    "intellivision-amico": {
        "id": 382,
        "slug": "intellivision-amico",
        "name": "Intellivision Amico",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/intellivision-amico",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkp.jpg",
    },
    "oculus-quest": {
        "id": 384,
        "slug": "oculus-quest",
        "name": "Oculus Quest",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/oculus-quest",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plh7.jpg",
    },
    "oculus-rift": {
        "id": 385,
        "slug": "oculus-rift",
        "name": "Oculus Rift",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/oculus-rift",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln8.jpg",
    },
    "oculus-go": {
        "id": 387,
        "slug": "oculus-go",
        "name": "Oculus Go",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/oculus-go",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkk.jpg",
    },
    "gear-vr": {
        "id": 388,
        "slug": "gear-vr",
        "name": "Gear VR",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gear-vr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkj.jpg",
    },
    "terebikko-slash-see-n-say-video-phone": {
        "id": 479,
        "slug": "terebikko-slash-see-n-say-video-phone",
        "name": "Terebikko / See 'n Say Video Phone",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/terebikko-slash-see-n-say-video-phone",
        "url_logo": "",
    },
    "advanced-pico-beena": {
        "id": 507,
        "slug": "advanced-pico-beena",
        "name": "Advanced Pico Beena",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plou.jpg",
    },
    "ngc": {
        "id": 21,
        "slug": "ngc",
        "name": "Nintendo GameCube",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ngc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7a.jpg",
    },
    "gb": {
        "id": 33,
        "slug": "gb",
        "name": "Game Boy",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gb",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7m.jpg",
    },
    "psp": {
        "id": 38,
        "slug": "psp",
        "name": "PlayStation Portable",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/psp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5y.jpg",
    },
    "ngage": {
        "id": 42,
        "slug": "ngage",
        "name": "N-Gage",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ngage",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl76.jpg",
    },
    "wonderswan": {
        "id": 57,
        "slug": "wonderswan",
        "name": "WonderSwan",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/wonderswan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7b.jpg",
    },
    "bbcmicro": {
        "id": 69,
        "slug": "bbcmicro",
        "name": "BBC Microcomputer System",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/bbcmicro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl86.jpg",
    },
    "vic-20": {
        "id": 71,
        "slug": "vic-20",
        "name": "Commodore VIC-20",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/vic-20",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8p.jpg",
    },
    "winphone": {
        "id": 74,
        "slug": "winphone",
        "name": "Windows Phone",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/winphone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla3.jpg",
    },
    "neogeomvs": {
        "id": 79,
        "slug": "neogeomvs",
        "name": "Neo Geo MVS",
        "category": "Arcade",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/neogeomvs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/cbhfilmhdgwdql8nzsy0.jpg",
    },
    "neogeoaes": {
        "id": 80,
        "slug": "neogeoaes",
        "name": "Neo Geo AES",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/neogeoaes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/hamfdrgnhenxb2d9g8mh.jpg",
    },
    "sg1000": {
        "id": 84,
        "slug": "sg1000",
        "name": "SG-1000",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sg1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmn.jpg",
    },
    "astrocade": {
        "id": 91,
        "slug": "astrocade",
        "name": "Bally Astrocade",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/astrocade",
        "url_logo": "",
    },
    "c16": {
        "id": 93,
        "slug": "c16",
        "name": "Commodore 16",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/c16",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf4.jpg",
    },
    "pdp10": {
        "id": 96,
        "slug": "pdp10",
        "name": "PDP-10",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pdp10",
        "url_logo": "",
    },
    "nuon": {
        "id": 122,
        "slug": "nuon",
        "name": "Nuon",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nuon",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7g.jpg",
    },
    "new-nintendo-3ds": {
        "id": 137,
        "slug": "new-nintendo-3ds",
        "name": "New Nintendo 3DS",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/new-nintendo-3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6j.jpg",
    },
    "ay-3-8610": {
        "id": 141,
        "slug": "ay-3-8610",
        "name": "AY-3-8610",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ay-3-8610",
        "url_logo": "",
    },
    "stadia": {
        "id": 170,
        "slug": "stadia",
        "name": "Google Stadia",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/stadia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl94.jpg",
    },
    "switch-2": {
        "id": 508,
        "slug": "switch-2",
        "name": "Nintendo Switch 2",
        "category": "Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/switch-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plow.jpg",
    },
    "duplicate-stadia": {
        "id": 203,
        "slug": "duplicate-stadia",
        "name": "DUPLICATE Stadia",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/duplicate-stadia",
        "url_logo": "",
    },
    "daydream": {
        "id": 164,
        "slug": "daydream",
        "name": "Daydream",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/daydream",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lwbdsvaveyxmuwnsga7g.jpg",
    },
    "analogueelectronics": {
        "id": 100,
        "slug": "analogueelectronics",
        "name": "Analogue electronics",
        "category": "Unknown",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/analogueelectronics",
        "url_logo": "",
    },
    "ooparts": {
        "id": 372,
        "slug": "ooparts",
        "name": "OOParts",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ooparts",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgi.jpg",
    },
    "gamate": {
        "id": 378,
        "slug": "gamate",
        "name": "Gamate",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/gamate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plhf.jpg",
    },
    "casio-loopy": {
        "id": 380,
        "slug": "casio-loopy",
        "name": "Casio Loopy",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/casio-loopy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkm.jpg",
    },
    "playdate": {
        "id": 381,
        "slug": "playdate",
        "name": "Playdate",
        "category": "Portable Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/playdate",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgx.jpg",
    },
    "handheld-electronic-lcd": {
        "id": 411,
        "slug": "handheld-electronic-lcd",
        "name": "Handheld Electronic LCD",
        "category": "Portable Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd",
        "url_logo": "",
    },
    "watara-slash-quickshot-supervision": {
        "id": 415,
        "slug": "watara-slash-quickshot-supervision",
        "name": "Watara/QuickShot Supervision",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/watara-slash-quickshot-supervision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj7.jpg",
    },
    "panasonic-m2": {
        "id": 478,
        "slug": "panasonic-m2",
        "name": "Panasonic M2",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/panasonic-m2",
        "url_logo": "",
    },
    "digiblast": {
        "id": 486,
        "slug": "digiblast",
        "name": "Digiblast",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/digiblast",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo2.jpg",
    },
    "polymega": {
        "id": 509,
        "slug": "polymega",
        "name": "Polymega",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/polymega",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plox.jpg",
    },
    "zxs": {
        "id": 26,
        "slug": "zxs",
        "name": "ZX Spectrum",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/zxs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plab.jpg",
    },
    "msx": {
        "id": 27,
        "slug": "msx",
        "name": "MSX",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/msx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8j.jpg",
    },
    "3ds": {
        "id": 37,
        "slug": "3ds",
        "name": "Nintendo 3DS",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/3ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln6.jpg",
    },
    "3do": {
        "id": 50,
        "slug": "3do",
        "name": "3DO Interactive Multiplayer",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/3do",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7u.jpg",
    },
    "sms": {
        "id": 64,
        "slug": "sms",
        "name": "Sega Master System/Mark III",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sms",
        "url_logo": "",
    },
    "pdp1": {
        "id": 95,
        "slug": "pdp1",
        "name": "PDP-1",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pdp1",
        "url_logo": "",
    },
    "famicom": {
        "id": 99,
        "slug": "famicom",
        "name": "Family Computer",
        "category": "Console",
        "generation": 3,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnf.jpg",
    },
    "edsac--1": {
        "id": 102,
        "slug": "edsac--1",
        "name": "EDSAC",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/edsac--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plat.jpg",
    },
    "hp2100": {
        "id": 104,
        "slug": "hp2100",
        "name": "HP 2100",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/hp2100",
        "url_logo": "",
    },
    "hp3000": {
        "id": 105,
        "slug": "hp3000",
        "name": "HP 3000",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/hp3000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla9.jpg",
    },
    "sdssigma7": {
        "id": 106,
        "slug": "sdssigma7",
        "name": "SDS Sigma 7",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sdssigma7",
        "url_logo": "",
    },
    "call-a-computer": {
        "id": 107,
        "slug": "call-a-computer",
        "name": "Call-A-Computer time-shared mainframe computer system",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/call-a-computer",
        "url_logo": "",
    },
    "plato--1": {
        "id": 110,
        "slug": "plato--1",
        "name": "PLATO",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/plato--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaf.jpg",
    },
    "trs-80-color-computer": {
        "id": 151,
        "slug": "trs-80-color-computer",
        "name": "TRS-80 Color Computer",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/trs-80-color-computer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf1.jpg",
    },
    "pokemon-mini": {
        "id": 166,
        "slug": "pokemon-mini",
        "name": "Pokémon mini",
        "category": "Portable Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pokemon-mini",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7f.jpg",
    },
    "exidy-sorcerer": {
        "id": 236,
        "slug": "exidy-sorcerer",
        "name": "Exidy Sorcerer",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/exidy-sorcerer",
        "url_logo": "",
    },
    "dvd-player": {
        "id": 238,
        "slug": "dvd-player",
        "name": "DVD Player",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/dvd-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbu.jpg",
    },
    "blu-ray-player": {
        "id": 239,
        "slug": "blu-ray-player",
        "name": "Blu-ray Player",
        "category": "Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/blu-ray-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbv.jpg",
    },
    "zeebo": {
        "id": 240,
        "slug": "zeebo",
        "name": "Zeebo",
        "category": "Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/zeebo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbx.jpg",
    },
    "pc-fx": {
        "id": 274,
        "slug": "pc-fx",
        "name": "PC-FX",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pc-fx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf8.jpg",
    },
    "series-x-s": {
        "id": 169,
        "slug": "series-x-s",
        "name": "Xbox Series X|S",
        "category": "Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/series-x-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plfl.jpg",
    },
    "windows-mobile": {
        "id": 405,
        "slug": "windows-mobile",
        "name": "Windows Mobile",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/windows-mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkl.jpg",
    },
    "sinclair-ql": {
        "id": 406,
        "slug": "sinclair-ql",
        "name": "Sinclair QL",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sinclair-ql",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plih.jpg",
    },
    "hyperscan": {
        "id": 407,
        "slug": "hyperscan",
        "name": "HyperScan",
        "category": "Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/hyperscan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj2.jpg",
    },
    "mega-duck-slash-cougar-boy": {
        "id": 408,
        "slug": "mega-duck-slash-cougar-boy",
        "name": "Mega Duck/Cougar Boy",
        "category": "Portable Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/mega-duck-slash-cougar-boy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj3.jpg",
    },
    "legacy-computer": {
        "id": 409,
        "slug": "legacy-computer",
        "name": "Legacy Computer",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/legacy-computer",
        "url_logo": "",
    },
    "leapster": {
        "id": 412,
        "slug": "leapster",
        "name": "Leapster",
        "category": "Portable Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/leapster",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj5.jpg",
    },
    "leaptv": {
        "id": 414,
        "slug": "leaptv",
        "name": "LeapTV",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/leaptv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj6.jpg",
    },
    "64dd": {
        "id": 416,
        "slug": "64dd",
        "name": "64DD",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/64dd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj8.jpg",
    },
    "palm-os": {
        "id": 417,
        "slug": "palm-os",
        "name": "Palm OS",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/palm-os",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plj9.jpg",
    },
    "arduboy": {
        "id": 438,
        "slug": "arduboy",
        "name": "Arduboy",
        "category": "Portable Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/arduboy",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk6.jpg",
    },
    "vsmile": {
        "id": 439,
        "slug": "vsmile",
        "name": "V.Smile",
        "category": "Console",
        "generation": 6,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/vsmile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plk7.jpg",
    },
    "pocketstation": {
        "id": 441,
        "slug": "pocketstation",
        "name": "PocketStation",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/pocketstation",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkc.jpg",
    },
    "meta-quest-3": {
        "id": 471,
        "slug": "meta-quest-3",
        "name": "Meta Quest 3",
        "category": "Console",
        "generation": 9,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/meta-quest-3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnb.jpg",
    },
    "visionos": {
        "id": 472,
        "slug": "visionos",
        "name": "visionOS",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/visionos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnj.jpg",
    },
    "r-zone": {
        "id": 475,
        "slug": "r-zone",
        "name": "R-Zone",
        "category": "Portable Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/r-zone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnm.jpg",
    },
    "apple-pippin": {
        "id": 476,
        "slug": "apple-pippin",
        "name": "Apple Pippin",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/apple-pippin",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnn.jpg",
    },
    "super-acan": {
        "id": 480,
        "slug": "super-acan",
        "name": "Super A'Can",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/super-acan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plns.jpg",
    },
    "tomy-tutor-slash-pyuta-slash-grandstand-tutor": {
        "id": 481,
        "slug": "tomy-tutor-slash-pyuta-slash-grandstand-tutor",
        "name": "Tomy Tutor / Pyuta / Grandstand Tutor",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/tomy-tutor-slash-pyuta-slash-grandstand-tutor",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnt.jpg",
    },
    "ps": {
        "id": 7,
        "slug": "ps",
        "name": "PlayStation",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/ps",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmb.jpg",
    },
    "amiga": {
        "id": 16,
        "slug": "amiga",
        "name": "Amiga",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/amiga",
        "url_logo": "",
    },
    "acpc": {
        "id": 25,
        "slug": "acpc",
        "name": "Amstrad CPC",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/acpc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnh.jpg",
    },
    "genesis-slash-megadrive": {
        "id": 29,
        "slug": "genesis-slash-megadrive",
        "name": "Sega Mega Drive/Genesis",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive",
        "url_logo": "",
    },
    "android": {
        "id": 34,
        "slug": "android",
        "name": "Android",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/android",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln3.jpg",
    },
    "vc": {
        "id": 47,
        "slug": "vc",
        "name": "Virtual Console",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/vc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plao.jpg",
    },
    "arcade": {
        "id": 52,
        "slug": "arcade",
        "name": "Arcade",
        "category": "Arcade",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/arcade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmz.jpg",
    },
    "atari2600": {
        "id": 59,
        "slug": "atari2600",
        "name": "Atari 2600",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari2600",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln4.jpg",
    },
    "colecovision": {
        "id": 68,
        "slug": "colecovision",
        "name": "ColecoVision",
        "category": "Console",
        "generation": 2,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/colecovision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8n.jpg",
    },
    "laseractive": {
        "id": 487,
        "slug": "laseractive",
        "name": "LaserActive",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/laseractive",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo4.jpg",
    },
    "n64": {
        "id": 4,
        "slug": "n64",
        "name": "Nintendo 64",
        "category": "Console",
        "generation": 5,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/n64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl78.jpg",
    },
    "wii": {
        "id": 5,
        "slug": "wii",
        "name": "Wii",
        "category": "Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/wii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl92.jpg",
    },
    "mac": {
        "id": 14,
        "slug": "mac",
        "name": "Mac",
        "category": "Operative System",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/mac",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo3.jpg",
    },
    "snes": {
        "id": 19,
        "slug": "snes",
        "name": "Super Nintendo Entertainment System",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/snes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ifw2tvdkynyxayquiyk4.jpg",
    },
    "xboxone": {
        "id": 49,
        "slug": "xboxone",
        "name": "Xbox One",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/xboxone",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl95.jpg",
    },
    "mobile": {
        "id": 55,
        "slug": "mobile",
        "name": "Legacy Mobile Device",
        "category": "Portable Console",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnd.jpg",
    },
    "sfam": {
        "id": 58,
        "slug": "sfam",
        "name": "Super Famicom",
        "category": "Console",
        "generation": 4,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/sfam",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/a9x7xjy4p9sqynrvomcf.jpg",
    },
    "atari-st": {
        "id": 63,
        "slug": "atari-st",
        "name": "Atari ST/STE",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/atari-st",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla7.jpg",
    },
    "appleii": {
        "id": 75,
        "slug": "appleii",
        "name": "Apple II",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/appleii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8r.jpg",
    },
    "browser": {
        "id": 82,
        "slug": "browser",
        "name": "Web browser",
        "category": "Platform",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/browser",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmx.jpg",
    },
    "cpet": {
        "id": 90,
        "slug": "cpet",
        "name": "Commodore PET",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/cpet",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf3.jpg",
    },
    "trs-80": {
        "id": 126,
        "slug": "trs-80",
        "name": "TRS-80",
        "category": "Computer",
        "generation": -1,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/trs-80",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plac.jpg",
    },
    "switch": {
        "id": 130,
        "slug": "switch",
        "name": "Nintendo Switch",
        "category": "Console",
        "generation": 8,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/switch",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgu.jpg",
    },
    "nintendo-dsi": {
        "id": 159,
        "slug": "nintendo-dsi",
        "name": "Nintendo DSi",
        "category": "Portable Console",
        "generation": 7,
        "family_name": "",
        "family_slug": "",
        "url": "https://www.igdb.com/platforms/nintendo-dsi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6u.jpg",
    },
}


class SlugToIGDBVersion(TypedDict):
    id: int
    slug: str
    platform_slug: str
    name: str
    url: str
    url_logo: str


IGDB_PLATFORM_VERSIONS: dict[str, SlugToIGDBVersion] = {
    "opera-gx": {
        "id": 663,
        "slug": "opera-gx",
        "name": "Opera GX",
        "url": "https://www.igdb.com/platforms/browser/version/opera-gx",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmx.jpg",
        "platform_slug": "browser",
    },
    "swancrystal": {
        "id": 734,
        "slug": "swancrystal",
        "name": "SwanCrystal",
        "url": "https://www.igdb.com/platforms/wonderswan-color/version/swancrystal",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plp0.jpg",
        "platform_slug": "wonderswan-color",
    },
    "sega-neptune": {
        "id": 703,
        "slug": "sega-neptune",
        "name": "Sega Neptune",
        "url": "https://www.igdb.com/platforms/sega32/version/sega-neptune",
        "url_logo": "",
        "platform_slug": "sega32",
    },
    "initial-version": {
        "id": 200,
        "slug": "initial-version",
        "name": "Initial version",
        "url": "https://www.igdb.com/platforms/pc-50x-family/version/initial-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vckflbrulcehb6qiap6n.jpg",
        "platform_slug": "pc-50x-family",
    },
    "saba-videoplay": {
        "id": 212,
        "slug": "saba-videoplay",
        "name": "Saba Videoplay",
        "url": "https://www.igdb.com/platforms/fairchild-channel-f/version/saba-videoplay",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8t.jpg",
        "platform_slug": "fairchild-channel-f",
    },
    "super-famicom-shvc-001": {
        "id": 139,
        "slug": "super-famicom-shvc-001",
        "name": "Super Famicom (SHVC-001)",
        "url": "https://www.igdb.com/platforms/snes/version/super-famicom-shvc-001",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jj75e2f0lzrbvtyw56er.jpg",
        "platform_slug": "snes",
    },
    "xbox-360-arcade": {
        "id": 3,
        "slug": "xbox-360-arcade",
        "name": "Xbox 360 Arcade",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-arcade",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6y.jpg",
        "platform_slug": "xbox360",
    },
    "kitkat": {
        "id": 12,
        "slug": "kitkat",
        "name": "KitKat",
        "url": "https://www.igdb.com/platforms/android/version/kitkat",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/kb9wpjpv0t1dthhuypou.jpg",
        "platform_slug": "android",
    },
    "switch-lite": {
        "id": 282,
        "slug": "switch-lite",
        "name": "Switch Lite",
        "url": "https://www.igdb.com/platforms/switch/version/switch-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pleu.jpg",
        "platform_slug": "switch",
    },
    "wii-mini": {
        "id": 283,
        "slug": "wii-mini",
        "name": "Wii mini",
        "url": "https://www.igdb.com/platforms/wii/version/wii-mini",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl92.jpg",
        "platform_slug": "wii",
    },
    "jelly-bean-4-1-x-4-3-x": {
        "id": 11,
        "slug": "jelly-bean-4-1-x-4-3-x",
        "name": "Jelly Bean 4.1.x-4.3.x",
        "url": "https://www.igdb.com/platforms/android/version/jelly-bean-4-1-x-4-3-x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/w4okoupqnolhrymeqznd.jpg",
        "platform_slug": "android",
    },
    "windows-xp": {
        "id": 13,
        "slug": "windows-xp",
        "name": "Windows XP",
        "url": "https://www.igdb.com/platforms/win/version/windows-xp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/nnr9qxtqzrmh1v0s9x2p.jpg",
        "platform_slug": "win",
    },
    "web-browser": {
        "id": 86,
        "slug": "web-browser",
        "name": "Web browser",
        "url": "https://www.igdb.com/platforms/browser/version/web-browser",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plal.jpg",
        "platform_slug": "browser",
    },
    "yosemite": {
        "id": 150,
        "slug": "yosemite",
        "name": "Yosemite",
        "url": "https://www.igdb.com/platforms/mac/version/yosemite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/df1raex6oqgcp56leff4.jpg",
        "platform_slug": "mac",
    },
    "odisea-mexico-export": {
        "id": 170,
        "slug": "odisea-mexico-export",
        "name": "Odisea (Mexico Export)",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odisea-mexico-export",
        "url_logo": "",
        "platform_slug": "odyssey--1",
    },
    "super-nes-cd-rom-system": {
        "id": 174,
        "slug": "super-nes-cd-rom-system",
        "name": "Super NES CD-ROM System",
        "url": "https://www.igdb.com/platforms/super-nes-cd-rom-system/version/super-nes-cd-rom-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plep.jpg",
        "platform_slug": "super-nes-cd-rom-system",
    },
    "playstation-5-pro": {
        "id": 724,
        "slug": "playstation-5-pro",
        "name": "PlayStation 5 Pro",
        "url": "https://www.igdb.com/platforms/ps5/version/playstation-5-pro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plos.jpg",
        "platform_slug": "ps5",
    },
    "windows-95": {
        "id": 532,
        "slug": "windows-95",
        "name": "Windows 95",
        "url": "https://www.igdb.com/platforms/win/version/windows-95",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliq.jpg",
        "platform_slug": "win",
    },
    "vfd-based-handhelds": {
        "id": 691,
        "slug": "vfd-based-handhelds",
        "name": "VFD-based handhelds",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/vfd-based-handhelds",
        "url_logo": "",
        "platform_slug": "handheld-electronic-lcd",
    },
    "wonderswan-color": {
        "id": 84,
        "slug": "wonderswan-color",
        "name": "WonderSwan Color",
        "url": "https://www.igdb.com/platforms/wonderswan/version/wonderswan-color",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7d.jpg",
        "platform_slug": "wonderswan",
    },
    "nintendo-dsi-xl": {
        "id": 192,
        "slug": "nintendo-dsi-xl",
        "name": "Nintendo DSi XL",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-dsi-xl",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6t.jpg",
        "platform_slug": "nds",
    },
    "ique-player": {
        "id": 122,
        "slug": "ique-player",
        "name": "iQue Player",
        "url": "https://www.igdb.com/platforms/n64/version/ique-player",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl78.jpg",
        "platform_slug": "n64",
    },
    "psp-1000": {
        "id": 59,
        "slug": "psp-1000",
        "name": "PSP-1000",
        "url": "https://www.igdb.com/platforms/psp/version/psp-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6q.jpg",
        "platform_slug": "psp",
    },
    "amiga-a-2000": {
        "id": 111,
        "slug": "amiga-a-2000",
        "name": "Amiga A 2000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-2000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plng.jpg",
        "platform_slug": "amiga",
    },
    "xbox-one-s": {
        "id": 180,
        "slug": "xbox-one-s",
        "name": "Xbox One S",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl90.jpg",
        "platform_slug": "xboxone",
    },
    "nintendo-dsi": {
        "id": 191,
        "slug": "nintendo-dsi",
        "name": "Nintendo DSi",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-dsi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6s.jpg",
        "platform_slug": "nds",
    },
    "game-boy-advance-sp": {
        "id": 193,
        "slug": "game-boy-advance-sp",
        "name": "Game Boy Advance SP",
        "url": "https://www.igdb.com/platforms/gba/version/game-boy-advance-sp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7x.jpg",
        "platform_slug": "gba",
    },
    "stadia": {
        "id": 319,
        "slug": "stadia",
        "name": "Stadia",
        "url": "https://www.igdb.com/platforms/duplicate-stadia/version/stadia",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaw.jpg",
        "platform_slug": "duplicate-stadia",
    },
    "froyo-2-2": {
        "id": 7,
        "slug": "froyo-2-2",
        "name": "Froyo 2.2",
        "url": "https://www.igdb.com/platforms/android/version/froyo-2-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/gvskesmuwhvmtzv2zhny.jpg",
        "platform_slug": "android",
    },
    "honeycomb-3-2": {
        "id": 9,
        "slug": "honeycomb-3-2",
        "name": "Honeycomb 3.2",
        "url": "https://www.igdb.com/platforms/android/version/honeycomb-3-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/qkdxwfyrcwhqrnj1hljd.jpg",
        "platform_slug": "android",
    },
    "atari-400": {
        "id": 27,
        "slug": "atari-400",
        "name": "Atari 400",
        "url": "https://www.igdb.com/platforms/atari8bit/version/atari-400",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plad.jpg",
        "platform_slug": "atari8bit",
    },
    "zodiac-1": {
        "id": 69,
        "slug": "zodiac-1",
        "name": "Zodiac 1",
        "url": "https://www.igdb.com/platforms/zod/version/zodiac-1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lfsdnlko80ftakbugceu.jpg",
        "platform_slug": "zod",
    },
    "sg-1000-ii": {
        "id": 92,
        "slug": "sg-1000-ii",
        "name": "SG-1000 II",
        "url": "https://www.igdb.com/platforms/sg1000/version/sg-1000-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/m7lor1sj7g9gnvliwxx8.jpg",
        "platform_slug": "sg1000",
    },
    "dol-101": {
        "id": 121,
        "slug": "dol-101",
        "name": "DOL-101",
        "url": "https://www.igdb.com/platforms/ngc/version/dol-101",
        "url_logo": "",
        "platform_slug": "ngc",
    },
    "panasonic-q": {
        "id": 125,
        "slug": "panasonic-q",
        "name": "Panasonic Q",
        "url": "https://www.igdb.com/platforms/ngc/version/panasonic-q",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jtbbevwj5l6q01pkkned.jpg",
        "platform_slug": "ngc",
    },
    "euzebox": {
        "id": 721,
        "slug": "euzebox",
        "name": "EUzebox",
        "url": "https://www.igdb.com/platforms/uzebox/version/euzebox",
        "url_logo": "",
        "platform_slug": "uzebox",
    },
    "windows-98": {
        "id": 533,
        "slug": "windows-98",
        "name": "Windows 98",
        "url": "https://www.igdb.com/platforms/win/version/windows-98",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plir.jpg",
        "platform_slug": "win",
    },
    "playstation": {
        "id": 57,
        "slug": "playstation",
        "name": "PlayStation",
        "url": "https://www.igdb.com/platforms/ps/version/playstation",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7q.jpg",
        "platform_slug": "ps",
    },
    "ice-cream-sandwich": {
        "id": 10,
        "slug": "ice-cream-sandwich",
        "name": "Ice Cream Sandwich",
        "url": "https://www.igdb.com/platforms/android/version/ice-cream-sandwich",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fxe5fcitcfmnam128xc1.jpg",
        "platform_slug": "android",
    },
    "puma": {
        "id": 141,
        "slug": "puma",
        "name": "Puma",
        "url": "https://www.igdb.com/platforms/mac/version/puma",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/luxugq3uspac6qqbvqwk.jpg",
        "platform_slug": "mac",
    },
    "playstation-4-slim": {
        "id": 178,
        "slug": "playstation-4-slim",
        "name": "PlayStation 4 Slim",
        "url": "https://www.igdb.com/platforms/ps4--1/version/playstation-4-slim",
        "url_logo": "",
        "platform_slug": "ps4--1",
    },
    "tele-ball": {
        "id": 201,
        "slug": "tele-ball",
        "name": "tele-ball",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yjdciw0jagvnmvzhhubs.jpg",
        "platform_slug": "ay-3-8500",
    },
    "windows-me": {
        "id": 534,
        "slug": "windows-me",
        "name": "Windows Me",
        "url": "https://www.igdb.com/platforms/win/version/windows-me",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plis.jpg",
        "platform_slug": "win",
    },
    "tele-ball-iii": {
        "id": 203,
        "slug": "tele-ball-iii",
        "name": "tele-ball III",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-iii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fzkmxoxkrfwo1by8t9ja.jpg",
        "platform_slug": "ay-3-8500",
    },
    "fm-towns-car-marty": {
        "id": 709,
        "slug": "fm-towns-car-marty",
        "name": "FM Towns Car Marty",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-car-marty",
        "url_logo": "",
        "platform_slug": "fm-towns",
    },
    "interton-vc-4000": {
        "id": 196,
        "slug": "interton-vc-4000",
        "name": "Interton VC 4000",
        "url": "https://www.igdb.com/platforms/vc-4000/version/interton-vc-4000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/phikgyfmv1fevj2jhzr5.jpg",
        "platform_slug": "vc-4000",
    },
    "playstation-portable-street": {
        "id": 279,
        "slug": "playstation-portable-street",
        "name": "PlayStation Portable Street",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-street",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5y.jpg",
        "platform_slug": "psp",
    },
    "windows-8": {
        "id": 15,
        "slug": "windows-8",
        "name": "Windows 8",
        "url": "https://www.igdb.com/platforms/win/version/windows-8",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/itdndmarjfphtsppnlfh.jpg",
        "platform_slug": "win",
    },
    "famicom-titler": {
        "id": 646,
        "slug": "famicom-titler",
        "name": "Famicom Titler",
        "url": "https://www.igdb.com/platforms/famicom/version/famicom-titler",
        "url_logo": "",
        "platform_slug": "famicom",
    },
    "tele-ball-ii": {
        "id": 202,
        "slug": "tele-ball-ii",
        "name": "tele-ball II",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/x42zeitpbuo2ltn7ybb2.jpg",
        "platform_slug": "ay-3-8500",
    },
    "tele-ball-vii": {
        "id": 204,
        "slug": "tele-ball-vii",
        "name": "tele-ball VII",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/tele-ball-vii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vs8nzlrcte7l9ep2cqy5.jpg",
        "platform_slug": "ay-3-8500",
    },
    "n-gage-qd": {
        "id": 118,
        "slug": "n-gage-qd",
        "name": "N-Gage QD",
        "url": "https://www.igdb.com/platforms/ngage/version/n-gage-qd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl76.jpg",
        "platform_slug": "ngage",
    },
    "snow-leopard": {
        "id": 146,
        "slug": "snow-leopard",
        "name": "Snow Leopard",
        "url": "https://www.igdb.com/platforms/mac/version/snow-leopard",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jiy43xitvtxfi16wcdyd.jpg",
        "platform_slug": "mac",
    },
    "netscape-navigator": {
        "id": 656,
        "slug": "netscape-navigator",
        "name": "Netscape Navigator",
        "url": "https://www.igdb.com/platforms/browser/version/netscape-navigator",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmq.jpg",
        "platform_slug": "browser",
    },
    "windows-7": {
        "id": 1,
        "slug": "windows-7",
        "name": "Windows 7",
        "url": "https://www.igdb.com/platforms/win/version/windows-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pvjzmgepkxhwvgrgmazj.jpg",
        "platform_slug": "win",
    },
    "marshmallow": {
        "id": 237,
        "slug": "marshmallow",
        "name": "Marshmallow",
        "url": "https://www.igdb.com/platforms/android/version/marshmallow",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plai.jpg",
        "platform_slug": "android",
    },
    "odissea-italian-export": {
        "id": 171,
        "slug": "odissea-italian-export",
        "name": "Odissea (Italian Export)",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odissea-italian-export",
        "url_logo": "",
        "platform_slug": "odyssey--1",
    },
    "super-famicom-jr-model-shvc-101": {
        "id": 177,
        "slug": "super-famicom-jr-model-shvc-101",
        "name": "Super Famicom Jr. (Model SHVC-101)",
        "url": "https://www.igdb.com/platforms/snes/version/super-famicom-jr-model-shvc-101",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ifw2tvdkynyxayquiyk4.jpg",
        "platform_slug": "snes",
    },
    "xbox-one-s-all-digital": {
        "id": 188,
        "slug": "xbox-one-s-all-digital",
        "name": "Xbox One S All-Digital",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-s-all-digital",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl95.jpg",
        "platform_slug": "xboxone",
    },
    "android-1-dot-0": {
        "id": 541,
        "slug": "android-1-dot-0",
        "name": "Android 1.0",
        "url": "https://www.igdb.com/platforms/android/version/android-1-dot-0",
        "url_logo": "",
        "platform_slug": "android",
    },
    "super-nintendo-original-european-version": {
        "id": 95,
        "slug": "super-nintendo-original-european-version",
        "name": "Super Nintendo (original European version)",
        "url": "https://www.igdb.com/platforms/snes/version/super-nintendo-original-european-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7k.jpg",
        "platform_slug": "snes",
    },
    "lion": {
        "id": 147,
        "slug": "lion",
        "name": "Lion",
        "url": "https://www.igdb.com/platforms/mac/version/lion",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yaguodfpr4ucdiakputb.jpg",
        "platform_slug": "mac",
    },
    "odyssey-export": {
        "id": 167,
        "slug": "odyssey-export",
        "name": "Odyssey (Export)",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-export",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf5.jpg",
        "platform_slug": "odyssey--1",
    },
    "odyssey-german-export": {
        "id": 168,
        "slug": "odyssey-german-export",
        "name": "Odyssey (German Export)",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-german-export",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf6.jpg",
        "platform_slug": "odyssey--1",
    },
    "windows-phone-8": {
        "id": 225,
        "slug": "windows-phone-8",
        "name": "Windows Phone 8",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-8",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ui8kqoijqxolfowolj56.jpg",
        "platform_slug": "winphone",
    },
    "lollipop": {
        "id": 236,
        "slug": "lollipop",
        "name": "Lollipop",
        "url": "https://www.igdb.com/platforms/android/version/lollipop",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plah.jpg",
        "platform_slug": "android",
    },
    "pocket-pc-2002": {
        "id": 535,
        "slug": "pocket-pc-2002",
        "name": "Pocket PC 2002",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/pocket-pc-2002",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliu.jpg",
        "platform_slug": "windows-mobile",
    },
    "android-1-dot-1": {
        "id": 542,
        "slug": "android-1-dot-1",
        "name": "Android 1.1",
        "url": "https://www.igdb.com/platforms/android/version/android-1-dot-1",
        "url_logo": "",
        "platform_slug": "android",
    },
    "sonoma": {
        "id": 713,
        "slug": "sonoma",
        "name": "Sonoma",
        "url": "https://www.igdb.com/platforms/mac/version/sonoma",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo3.jpg",
        "platform_slug": "mac",
    },
    "itt-odyssee": {
        "id": 169,
        "slug": "itt-odyssee",
        "name": "ITT Odyssee",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/itt-odyssee",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8y.jpg",
        "platform_slug": "odyssey--1",
    },
    "gingerbread-2-3-3": {
        "id": 8,
        "slug": "gingerbread-2-3-3",
        "name": "Gingerbread 2.3.3",
        "url": "https://www.igdb.com/platforms/android/version/gingerbread-2-3-3",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/iftbsii6snn6geq5hi9n.jpg",
        "platform_slug": "android",
    },
    "ms-dos": {
        "id": 540,
        "slug": "ms-dos",
        "name": "MS-DOS",
        "url": "https://www.igdb.com/platforms/dos/version/ms-dos",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plix.jpg",
        "platform_slug": "dos",
    },
    "android-cupcake": {
        "id": 543,
        "slug": "android-cupcake",
        "name": "Android Cupcake",
        "url": "https://www.igdb.com/platforms/android/version/android-cupcake",
        "url_logo": "",
        "platform_slug": "android",
    },
    "playstation-vita": {
        "id": 60,
        "slug": "playstation-vita",
        "name": "PlayStation Vita",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-vita",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6g.jpg",
        "platform_slug": "psvita",
    },
    "panther": {
        "id": 143,
        "slug": "panther",
        "name": "Panther",
        "url": "https://www.igdb.com/platforms/mac/version/panther",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lgboqvrjxbhm9crh0gmk.jpg",
        "platform_slug": "mac",
    },
    "texas-instruments-ti-99-slash-4": {
        "id": 172,
        "slug": "texas-instruments-ti-99-slash-4",
        "name": "Texas Instruments TI-99/4",
        "url": "https://www.igdb.com/platforms/ti-99/version/texas-instruments-ti-99-slash-4",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plez.jpg",
        "platform_slug": "ti-99",
    },
    "playstation-3-original": {
        "id": 4,
        "slug": "playstation-3-original",
        "name": "Playstation 3 Original",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-original",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6l.jpg",
        "platform_slug": "ps3",
    },
    "sega-hikaru": {
        "id": 650,
        "slug": "sega-hikaru",
        "name": "Sega Hikaru",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-hikaru",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmj.jpg",
        "platform_slug": "arcade",
    },
    "android-donut": {
        "id": 544,
        "slug": "android-donut",
        "name": "Android Donut",
        "url": "https://www.igdb.com/platforms/android/version/android-donut",
        "url_logo": "",
        "platform_slug": "android",
    },
    "playstation-4-pro": {
        "id": 179,
        "slug": "playstation-4-pro",
        "name": "PlayStation 4 Pro",
        "url": "https://www.igdb.com/platforms/ps4--1/version/playstation-4-pro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6f.jpg",
        "platform_slug": "ps4--1",
    },
    "android-eclair": {
        "id": 545,
        "slug": "android-eclair",
        "name": "Android Eclair",
        "url": "https://www.igdb.com/platforms/android/version/android-eclair",
        "url_logo": "",
        "platform_slug": "android",
    },
    "playstation-portable-slim-and-lite": {
        "id": 276,
        "slug": "playstation-portable-slim-and-lite",
        "name": "PlayStation Portable Slim & Lite",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-slim-and-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5v.jpg",
        "platform_slug": "psp",
    },
    "android-froyo": {
        "id": 546,
        "slug": "android-froyo",
        "name": "Android Froyo",
        "url": "https://www.igdb.com/platforms/android/version/android-froyo",
        "url_logo": "",
        "platform_slug": "android",
    },
    "playstation-3-slim": {
        "id": 5,
        "slug": "playstation-3-slim",
        "name": "Playstation 3 Slim",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-slim",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6m.jpg",
        "platform_slug": "ps3",
    },
    "playstation-3-super-slim": {
        "id": 6,
        "slug": "playstation-3-super-slim",
        "name": "Playstation 3 Super Slim",
        "url": "https://www.igdb.com/platforms/ps3/version/playstation-3-super-slim",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/tuyy1nrqodtmbqajp4jg.jpg",
        "platform_slug": "ps3",
    },
    "sg-1000": {
        "id": 91,
        "slug": "sg-1000",
        "name": "SG-1000",
        "url": "https://www.igdb.com/platforms/sg1000/version/sg-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmn.jpg",
        "platform_slug": "sg1000",
    },
    "windows-phone-7": {
        "id": 224,
        "slug": "windows-phone-7",
        "name": "Windows Phone 7",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-7",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/taegabndvbq86z4dumy2.jpg",
        "platform_slug": "winphone",
    },
    "windows-10-mobile": {
        "id": 227,
        "slug": "windows-10-mobile",
        "name": "Windows 10 Mobile",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-10-mobile",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla3.jpg",
        "platform_slug": "winphone",
    },
    "telstar": {
        "id": 198,
        "slug": "telstar",
        "name": "Telstar",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/telstar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vgsvdiyyzjeayaooi1fy.jpg",
        "platform_slug": "ay-3-8500",
    },
    "playstation-portable-brite": {
        "id": 277,
        "slug": "playstation-portable-brite",
        "name": "PlayStation Portable Brite",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-brite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5w.jpg",
        "platform_slug": "psp",
    },
    "meta-quest-2": {
        "id": 593,
        "slug": "meta-quest-2",
        "name": "Meta Quest 2",
        "url": "https://www.igdb.com/platforms/meta-quest-2/version/meta-quest-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll0.jpg",
        "platform_slug": "meta-quest-2",
    },
    "windows-vista": {
        "id": 14,
        "slug": "windows-vista",
        "name": "Windows Vista",
        "url": "https://www.igdb.com/platforms/win/version/windows-vista",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/z6hjqy9uvneqbd3yh4sm.jpg",
        "platform_slug": "win",
    },
    "game-boy-light": {
        "id": 182,
        "slug": "game-boy-light",
        "name": "Game Boy Light",
        "url": "https://www.igdb.com/platforms/gb/version/game-boy-light",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7m.jpg",
        "platform_slug": "gb",
    },
    "atari-lynx-mkii": {
        "id": 189,
        "slug": "atari-lynx-mkii",
        "name": "Atari Lynx MkII",
        "url": "https://www.igdb.com/platforms/lynx/version/atari-lynx-mkii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl82.jpg",
        "platform_slug": "lynx",
    },
    "windows-phone-8-dot-1": {
        "id": 226,
        "slug": "windows-phone-8-dot-1",
        "name": "Windows Phone 8.1",
        "url": "https://www.igdb.com/platforms/winphone/version/windows-phone-8-dot-1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/gvk8xyyptd40kg3yb8j5.jpg",
        "platform_slug": "winphone",
    },
    "nougat": {
        "id": 238,
        "slug": "nougat",
        "name": "Nougat",
        "url": "https://www.igdb.com/platforms/android/version/nougat",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plaj.jpg",
        "platform_slug": "android",
    },
    "naomi-2": {
        "id": 651,
        "slug": "naomi-2",
        "name": "NAOMI 2",
        "url": "https://www.igdb.com/platforms/arcade/version/naomi-2",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm9.jpg",
        "platform_slug": "arcade",
    },
    "playstation-vita-pch-2000": {
        "id": 274,
        "slug": "playstation-vita-pch-2000",
        "name": "PlayStation Vita (PCH-2000)",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-vita-pch-2000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl5z.jpg",
        "platform_slug": "psvita",
    },
    "dvd": {
        "id": 355,
        "slug": "dvd",
        "name": "DVD",
        "url": "https://www.igdb.com/platforms/dvd-player/version/dvd",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbu.jpg",
        "platform_slug": "dvd-player",
    },
    "lcd-based-handhelds": {
        "id": 551,
        "slug": "lcd-based-handhelds",
        "name": "LCD-based handhelds",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/lcd-based-handhelds",
        "url_logo": "",
        "platform_slug": "handheld-electronic-lcd",
    },
    "opera": {
        "id": 657,
        "slug": "opera",
        "name": "Opera",
        "url": "https://www.igdb.com/platforms/browser/version/opera",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmr.jpg",
        "platform_slug": "browser",
    },
    "blu-ray-disc": {
        "id": 356,
        "slug": "blu-ray-disc",
        "name": "Blu-ray Disc",
        "url": "https://www.igdb.com/platforms/blu-ray-player/version/blu-ray-disc",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plbv.jpg",
        "platform_slug": "blu-ray-player",
    },
    "xbox-one-x--1": {
        "id": 185,
        "slug": "xbox-one-x--1",
        "name": "Xbox One X",
        "url": "https://www.igdb.com/platforms/xboxone/version/xbox-one-x--1",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fckqj8d3as6tug4fg3x4.jpg",
        "platform_slug": "xboxone",
    },
    "playstation-tv": {
        "id": 275,
        "slug": "playstation-tv",
        "name": "PlayStation TV",
        "url": "https://www.igdb.com/platforms/psvita/version/playstation-tv",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6h.jpg",
        "platform_slug": "psvita",
    },
    "xbox-series-s": {
        "id": 489,
        "slug": "xbox-series-s",
        "name": "Xbox Series S",
        "url": "https://www.igdb.com/platforms/series-x-s/version/xbox-series-s",
        "url_logo": "",
        "platform_slug": "series-x-s",
    },
    "sinclair-ql": {
        "id": 524,
        "slug": "sinclair-ql",
        "name": "Sinclair QL",
        "url": "https://www.igdb.com/platforms/sinclair-ql/version/sinclair-ql",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plih.jpg",
        "platform_slug": "sinclair-ql",
    },
    "vivaldi": {
        "id": 662,
        "slug": "vivaldi",
        "name": "Vivaldi",
        "url": "https://www.igdb.com/platforms/browser/version/vivaldi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmw.jpg",
        "platform_slug": "browser",
    },
    "game-boy-pocket": {
        "id": 181,
        "slug": "game-boy-pocket",
        "name": "Game Boy Pocket",
        "url": "https://www.igdb.com/platforms/gb/version/game-boy-pocket",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7o.jpg",
        "platform_slug": "gb",
    },
    "google-stadia-founders-edition": {
        "id": 285,
        "slug": "google-stadia-founders-edition",
        "name": "Google Stadia: Founder's Edition",
        "url": "https://www.igdb.com/platforms/stadia/version/google-stadia-founders-edition",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl94.jpg",
        "platform_slug": "stadia",
    },
    "feature-phone": {
        "id": 514,
        "slug": "feature-phone",
        "name": "Feature phone",
        "url": "https://www.igdb.com/platforms/mobile/version/feature-phone",
        "url_logo": "",
        "platform_slug": "mobile",
    },
    "sega-mega-drive-2-slash-genesis": {
        "id": 628,
        "slug": "sega-mega-drive-2-slash-genesis",
        "name": "Sega Mega Drive 2/Genesis",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-drive-2-slash-genesis",
        "url_logo": "",
        "platform_slug": "genesis-slash-megadrive",
    },
    "xbox-360-s": {
        "id": 495,
        "slug": "xbox-360-s",
        "name": "Xbox 360 S",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plha.jpg",
        "platform_slug": "xbox360",
    },
    "sears-hockey-pong": {
        "id": 510,
        "slug": "sears-hockey-pong",
        "name": "Sears Hockey-Pong",
        "url": "https://www.igdb.com/platforms/ay-3-8500/version/sears-hockey-pong",
        "url_logo": "",
        "platform_slug": "ay-3-8500",
    },
    "tele-cassetten-game": {
        "id": 205,
        "slug": "tele-cassetten-game",
        "name": "Tele-Cassetten-Game",
        "url": "https://www.igdb.com/platforms/pc-50x-family/version/tele-cassetten-game",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/dpwrkxrjkuxwqroqwjsw.jpg",
        "platform_slug": "pc-50x-family",
    },
    "advanced-pico-beena": {
        "id": 726,
        "slug": "advanced-pico-beena",
        "name": "Advanced Pico Beena",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena/version/advanced-pico-beena",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plou.jpg",
        "platform_slug": "advanced-pico-beena",
    },
    "10": {
        "id": 526,
        "slug": "10",
        "name": "10",
        "url": "https://www.igdb.com/platforms/android/version/10",
        "url_logo": "",
        "platform_slug": "android",
    },
    "11": {
        "id": 527,
        "slug": "11",
        "name": "11",
        "url": "https://www.igdb.com/platforms/android/version/11",
        "url_logo": "",
        "platform_slug": "android",
    },
    "starlight-wii-gaming-station": {
        "id": 730,
        "slug": "starlight-wii-gaming-station",
        "name": "Starlight Wii Gaming Station",
        "url": "https://www.igdb.com/platforms/wii/version/starlight-wii-gaming-station",
        "url_logo": "",
        "platform_slug": "wii",
    },
    "amiga-a-1200": {
        "id": 522,
        "slug": "amiga-a-1200",
        "name": "Amiga A 1200",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-1200",
        "url_logo": "",
        "platform_slug": "amiga",
    },
    "12": {
        "id": 528,
        "slug": "12",
        "name": "12",
        "url": "https://www.igdb.com/platforms/android/version/12",
        "url_logo": "",
        "platform_slug": "android",
    },
    "windows-3-dot-0": {
        "id": 531,
        "slug": "windows-3-dot-0",
        "name": "Windows 3.0",
        "url": "https://www.igdb.com/platforms/win/version/windows-3-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plip.jpg",
        "platform_slug": "win",
    },
    "beenalite": {
        "id": 727,
        "slug": "beenalite",
        "name": "BeenaLite",
        "url": "https://www.igdb.com/platforms/advanced-pico-beena/version/beenalite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plov.jpg",
        "platform_slug": "advanced-pico-beena",
    },
    "windows-mobile-2003": {
        "id": 536,
        "slug": "windows-mobile-2003",
        "name": "Windows Mobile 2003",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-2003",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliv.jpg",
        "platform_slug": "windows-mobile",
    },
    "windows-mobile-5-dot-0": {
        "id": 537,
        "slug": "windows-mobile-5-dot-0",
        "name": "Windows Mobile 5.0",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-5-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pliw.jpg",
        "platform_slug": "windows-mobile",
    },
    "windows-mobile-6-dot-0": {
        "id": 538,
        "slug": "windows-mobile-6-dot-0",
        "name": "Windows Mobile 6.0",
        "url": "https://www.igdb.com/platforms/windows-mobile/version/windows-mobile-6-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkl.jpg",
        "platform_slug": "windows-mobile",
    },
    "windows-10": {
        "id": 124,
        "slug": "windows-10",
        "name": "Windows 10",
        "url": "https://www.igdb.com/platforms/win/version/windows-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/irwvwpl023f8y19tidgq.jpg",
        "platform_slug": "win",
    },
    "wii-family-edition": {
        "id": 731,
        "slug": "wii-family-edition",
        "name": "Wii Family Edition",
        "url": "https://www.igdb.com/platforms/wii/version/wii-family-edition",
        "url_logo": "",
        "platform_slug": "wii",
    },
    "big-sur": {
        "id": 599,
        "slug": "big-sur",
        "name": "Big Sur",
        "url": "https://www.igdb.com/platforms/mac/version/big-sur",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plla.jpg",
        "platform_slug": "mac",
    },
    "cheetah": {
        "id": 45,
        "slug": "cheetah",
        "name": "Cheetah",
        "url": "https://www.igdb.com/platforms/mac/version/cheetah",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/eatvxlflfq0lk8p8sp2c.jpg",
        "platform_slug": "mac",
    },
    "windows-2-dot-0": {
        "id": 530,
        "slug": "windows-2-dot-0",
        "name": "Windows 2.0",
        "url": "https://www.igdb.com/platforms/win/version/windows-2-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plio.jpg",
        "platform_slug": "win",
    },
    "oculus-quest-2": {
        "id": 507,
        "slug": "oculus-quest-2",
        "name": "Oculus Quest 2",
        "url": "https://www.igdb.com/platforms/meta-quest-2/version/oculus-quest-2",
        "url_logo": "",
        "platform_slug": "meta-quest-2",
    },
    "super-famicom-box": {
        "id": 639,
        "slug": "super-famicom-box",
        "name": "Super Famicom Box",
        "url": "https://www.igdb.com/platforms/sfam/version/super-famicom-box",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmm.jpg",
        "platform_slug": "sfam",
    },
    "nokia-n-gage-classic": {
        "id": 49,
        "slug": "nokia-n-gage-classic",
        "name": "Nokia N-Gage Classic",
        "url": "https://www.igdb.com/platforms/ngage/version/nokia-n-gage-classic",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl75.jpg",
        "platform_slug": "ngage",
    },
    "tiger": {
        "id": 144,
        "slug": "tiger",
        "name": "Tiger",
        "url": "https://www.igdb.com/platforms/mac/version/tiger",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/jp06zemqemczisfaxsgl.jpg",
        "platform_slug": "mac",
    },
    "turbo-express-slash-pc-engine-gt": {
        "id": 733,
        "slug": "turbo-express-slash-pc-engine-gt",
        "name": "Turbo Express/PC Engine GT",
        "url": "https://www.igdb.com/platforms/turbografx16--1/version/turbo-express-slash-pc-engine-gt",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploz.jpg",
        "platform_slug": "turbografx16--1",
    },
    "amiga-a-3000": {
        "id": 112,
        "slug": "amiga-a-3000",
        "name": "Amiga A 3000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-3000",
        "url_logo": "",
        "platform_slug": "amiga",
    },
    "monterey": {
        "id": 600,
        "slug": "monterey",
        "name": "Monterey",
        "url": "https://www.igdb.com/platforms/mac/version/monterey",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll9.jpg",
        "platform_slug": "mac",
    },
    "pie": {
        "id": 320,
        "slug": "pie",
        "name": "Pie",
        "url": "https://www.igdb.com/platforms/android/version/pie",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plax.jpg",
        "platform_slug": "android",
    },
    "atari-2600-plus": {
        "id": 673,
        "slug": "atari-2600-plus",
        "name": "Atari 2600+",
        "url": "https://www.igdb.com/platforms/atari2600/version/atari-2600-plus",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln4.jpg",
        "platform_slug": "atari2600",
    },
    "amiga-a-3000t": {
        "id": 113,
        "slug": "amiga-a-3000t",
        "name": "Amiga A 3000T",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-3000t",
        "url_logo": "",
        "platform_slug": "amiga",
    },
    "amiga-a-500": {
        "id": 19,
        "slug": "amiga-a-500",
        "name": "Amiga A 500",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-500",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plav.jpg",
        "platform_slug": "amiga",
    },
    "master-system-girl": {
        "id": 632,
        "slug": "master-system-girl",
        "name": "Master System Girl",
        "url": "https://www.igdb.com/platforms/sms/version/master-system-girl",
        "url_logo": "",
        "platform_slug": "sms",
    },
    "ventura": {
        "id": 598,
        "slug": "ventura",
        "name": "Ventura",
        "url": "https://www.igdb.com/platforms/mac/version/ventura",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll5.jpg",
        "platform_slug": "mac",
    },
    "atari-800": {
        "id": 104,
        "slug": "atari-800",
        "name": "Atari 800",
        "url": "https://www.igdb.com/platforms/atari8bit/version/atari-800",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl68.jpg",
        "platform_slug": "atari8bit",
    },
    "el-capitan": {
        "id": 151,
        "slug": "el-capitan",
        "name": "El Capitan",
        "url": "https://www.igdb.com/platforms/mac/version/el-capitan",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll8.jpg",
        "platform_slug": "mac",
    },
    "acetronic-mpu-1000": {
        "id": 213,
        "slug": "acetronic-mpu-1000",
        "name": "Acetronic MPU-1000",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system/version/acetronic-mpu-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/yfdqsudagw0av25dawjr.jpg",
        "platform_slug": "1292-advanced-programmable-video-system",
    },
    "oculus-rift-s": {
        "id": 680,
        "slug": "oculus-rift-s",
        "name": "Oculus Rift S",
        "url": "https://www.igdb.com/platforms/oculus-rift/version/oculus-rift-s",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln9.jpg",
        "platform_slug": "oculus-rift",
    },
    "xbox-360-original": {
        "id": 83,
        "slug": "xbox-360-original",
        "name": "Xbox 360 Original",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-original",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6x.jpg",
        "platform_slug": "xbox360",
    },
    "amiga-a-600": {
        "id": 109,
        "slug": "amiga-a-600",
        "name": "Amiga A 600",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-600",
        "url_logo": "",
        "platform_slug": "amiga",
    },
    "card-e-reader": {
        "id": 735,
        "slug": "card-e-reader",
        "name": "Card-e Reader",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader/version/card-e-reader",
        "url_logo": "",
        "platform_slug": "e-reader-slash-card-e-reader",
    },
    "sega-alls": {
        "id": 696,
        "slug": "sega-alls",
        "name": "Sega ALLS",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-alls",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnq.jpg",
        "platform_slug": "arcade",
    },
    "oreo": {
        "id": 239,
        "slug": "oreo",
        "name": "Oreo",
        "url": "https://www.igdb.com/platforms/android/version/oreo",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plag.jpg",
        "platform_slug": "android",
    },
    "e-reader-slash-card-e-reader-plus": {
        "id": 732,
        "slug": "e-reader-slash-card-e-reader-plus",
        "name": "e-Reader / Card-e Reader+",
        "url": "https://www.igdb.com/platforms/e-reader-slash-card-e-reader/version/e-reader-slash-card-e-reader-plus",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ploy.jpg",
        "platform_slug": "e-reader-slash-card-e-reader",
    },
    "mega-pc": {
        "id": 625,
        "slug": "mega-pc",
        "name": "Mega PC",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/mega-pc",
        "url_logo": "",
        "platform_slug": "genesis-slash-megadrive",
    },
    "teradrive": {
        "id": 627,
        "slug": "teradrive",
        "name": "Teradrive",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/teradrive",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm5.jpg",
        "platform_slug": "genesis-slash-megadrive",
    },
    "sega-mark-iii": {
        "id": 629,
        "slug": "sega-mark-iii",
        "name": "Sega Mark III",
        "url": "https://www.igdb.com/platforms/sms/version/sega-mark-iii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm6.jpg",
        "platform_slug": "sms",
    },
    "microsoft-edge": {
        "id": 661,
        "slug": "microsoft-edge",
        "name": "Microsoft Edge",
        "url": "https://www.igdb.com/platforms/browser/version/microsoft-edge",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmv.jpg",
        "platform_slug": "browser",
    },
    "amiga-a-1000": {
        "id": 110,
        "slug": "amiga-a-1000",
        "name": "Amiga A 1000",
        "url": "https://www.igdb.com/platforms/amiga/version/amiga-a-1000",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plkf.jpg",
        "platform_slug": "amiga",
    },
    "tlv-k981g-game-vcd-player": {
        "id": 622,
        "slug": "tlv-k981g-game-vcd-player",
        "name": "TLV-K981G Game VCD Player",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/tlv-k981g-game-vcd-player",
        "url_logo": "",
        "platform_slug": "genesis-slash-megadrive",
    },
    "nintendo-super-system": {
        "id": 638,
        "slug": "nintendo-super-system",
        "name": "Nintendo Super System",
        "url": "https://www.igdb.com/platforms/arcade/version/nintendo-super-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmd.jpg",
        "platform_slug": "arcade",
    },
    "sega-game-box-9": {
        "id": 631,
        "slug": "sega-game-box-9",
        "name": "Sega Game Box 9",
        "url": "https://www.igdb.com/platforms/sms/version/sega-game-box-9",
        "url_logo": "",
        "platform_slug": "sms",
    },
    "sega-system-e": {
        "id": 634,
        "slug": "sega-system-e",
        "name": "Sega System E",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-system-e",
        "url_logo": "",
        "platform_slug": "arcade",
    },
    "firefox": {
        "id": 660,
        "slug": "firefox",
        "name": "Firefox",
        "url": "https://www.igdb.com/platforms/browser/version/firefox",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmu.jpg",
        "platform_slug": "browser",
    },
    "led-based-handheld": {
        "id": 692,
        "slug": "led-based-handheld",
        "name": "LED-based handheld",
        "url": "https://www.igdb.com/platforms/handheld-electronic-lcd/version/led-based-handheld",
        "url_logo": "",
        "platform_slug": "handheld-electronic-lcd",
    },
    "mountain-lion": {
        "id": 148,
        "slug": "mountain-lion",
        "name": "Mountain Lion",
        "url": "https://www.igdb.com/platforms/mac/version/mountain-lion",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/vpprk3kkeloztxesyoiv.jpg",
        "platform_slug": "mac",
    },
    "mega-play": {
        "id": 636,
        "slug": "mega-play",
        "name": "Mega Play",
        "url": "https://www.igdb.com/platforms/arcade/version/mega-play",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plm8.jpg",
        "platform_slug": "arcade",
    },
    "new-style-super-nes-model-sns-101": {
        "id": 97,
        "slug": "new-style-super-nes-model-sns-101",
        "name": "New-Style Super NES (Model SNS-101)",
        "url": "https://www.igdb.com/platforms/snes/version/new-style-super-nes-model-sns-101",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/mr2y5qpyhvj1phm5tivg.jpg",
        "platform_slug": "snes",
    },
    "super-famicom-jr": {
        "id": 98,
        "slug": "super-famicom-jr",
        "name": "Super Famicom Jr.",
        "url": "https://www.igdb.com/platforms/sfam/version/super-famicom-jr",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/a9x7xjy4p9sqynrvomcf.jpg",
        "platform_slug": "sfam",
    },
    "family-computer": {
        "id": 123,
        "slug": "family-computer",
        "name": "Family Computer",
        "url": "https://www.igdb.com/platforms/famicom/version/family-computer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7p.jpg",
        "platform_slug": "famicom",
    },
    "my-computer-tv": {
        "id": 645,
        "slug": "my-computer-tv",
        "name": "My Computer TV",
        "url": "https://www.igdb.com/platforms/famicom/version/my-computer-tv",
        "url_logo": "",
        "platform_slug": "famicom",
    },
    "mega-tech-system": {
        "id": 635,
        "slug": "mega-tech-system",
        "name": "Mega-Tech System",
        "url": "https://www.igdb.com/platforms/arcade/version/mega-tech-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmk.jpg",
        "platform_slug": "arcade",
    },
    "famicombox-slash-famicom-station": {
        "id": 648,
        "slug": "famicombox-slash-famicom-station",
        "name": "FamicomBox/Famicom Station",
        "url": "https://www.igdb.com/platforms/famicom/version/famicombox-slash-famicom-station",
        "url_logo": "",
        "platform_slug": "famicom",
    },
    "soft-desk-10": {
        "id": 668,
        "slug": "soft-desk-10",
        "name": "Soft Desk 10",
        "url": "https://www.igdb.com/platforms/arcade/version/soft-desk-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln0.jpg",
        "platform_slug": "arcade",
    },
    "sega-titan-video": {
        "id": 669,
        "slug": "sega-titan-video",
        "name": "Sega Titan Video",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-titan-video",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln1.jpg",
        "platform_slug": "arcade",
    },
    "terebikko-cordless": {
        "id": 698,
        "slug": "terebikko-cordless",
        "name": "Terebikko Cordless",
        "url": "https://www.igdb.com/platforms/terebikko-slash-see-n-say-video-phone/version/terebikko-cordless",
        "url_logo": "",
        "platform_slug": "terebikko-slash-see-n-say-video-phone",
    },
    "mark-iii-soft-desk-10": {
        "id": 665,
        "slug": "mark-iii-soft-desk-10",
        "name": "Mark III Soft Desk 10",
        "url": "https://www.igdb.com/platforms/arcade/version/mark-iii-soft-desk-10",
        "url_logo": "",
        "platform_slug": "arcade",
    },
    "mark-iii-soft-desk-5": {
        "id": 666,
        "slug": "mark-iii-soft-desk-5",
        "name": "Mark III Soft Desk 5",
        "url": "https://www.igdb.com/platforms/arcade/version/mark-iii-soft-desk-5",
        "url_logo": "",
        "platform_slug": "arcade",
    },
    "sega-ringedge": {
        "id": 667,
        "slug": "sega-ringedge",
        "name": "Sega RingEdge",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-ringedge",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmz.jpg",
        "platform_slug": "arcade",
    },
    "jaguar": {
        "id": 142,
        "slug": "jaguar",
        "name": "Jaguar",
        "url": "https://www.igdb.com/platforms/mac/version/jaguar",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/fua8zdpguizpoyzfvkou.jpg",
        "platform_slug": "mac",
    },
    "sega-master-system-ii": {
        "id": 633,
        "slug": "sega-master-system-ii",
        "name": "Sega Master System II",
        "url": "https://www.igdb.com/platforms/sms/version/sega-master-system-ii",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plme.jpg",
        "platform_slug": "sms",
    },
    "atomiswave": {
        "id": 652,
        "slug": "atomiswave",
        "name": "Atomiswave",
        "url": "https://www.igdb.com/platforms/arcade/version/atomiswave",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plma.jpg",
        "platform_slug": "arcade",
    },
    "ps-one": {
        "id": 653,
        "slug": "ps-one",
        "name": "PS One",
        "url": "https://www.igdb.com/platforms/ps/version/ps-one",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmb.jpg",
        "platform_slug": "ps",
    },
    "net-yaroze": {
        "id": 654,
        "slug": "net-yaroze",
        "name": "Net Yaroze",
        "url": "https://www.igdb.com/platforms/ps/version/net-yaroze",
        "url_logo": "",
        "platform_slug": "ps",
    },
    "internet-explorer": {
        "id": 655,
        "slug": "internet-explorer",
        "name": "Internet Explorer",
        "url": "https://www.igdb.com/platforms/browser/version/internet-explorer",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmp.jpg",
        "platform_slug": "browser",
    },
    "safari": {
        "id": 658,
        "slug": "safari",
        "name": "Safari",
        "url": "https://www.igdb.com/platforms/browser/version/safari",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plms.jpg",
        "platform_slug": "browser",
    },
    "sega-system-1": {
        "id": 649,
        "slug": "sega-system-1",
        "name": "Sega System 1",
        "url": "https://www.igdb.com/platforms/arcade/version/sega-system-1",
        "url_logo": "",
        "platform_slug": "arcade",
    },
    "fm-towns-marty": {
        "id": 707,
        "slug": "fm-towns-marty",
        "name": "FM Towns Marty",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-marty",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnz.jpg",
        "platform_slug": "fm-towns",
    },
    "naomi": {
        "id": 637,
        "slug": "naomi",
        "name": "NAOMI",
        "url": "https://www.igdb.com/platforms/arcade/version/naomi",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmf.jpg",
        "platform_slug": "arcade",
    },
    "triforce": {
        "id": 664,
        "slug": "triforce",
        "name": "Triforce",
        "url": "https://www.igdb.com/platforms/arcade/version/triforce",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmy.jpg",
        "platform_slug": "arcade",
    },
    "android-13": {
        "id": 672,
        "slug": "android-13",
        "name": "Android 13",
        "url": "https://www.igdb.com/platforms/android/version/android-13",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln3.jpg",
        "platform_slug": "android",
    },
    "original-version": {
        "id": 67,
        "slug": "original-version",
        "name": "Original version",
        "url": "https://www.igdb.com/platforms/sfam/version/original-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl7j.jpg",
        "platform_slug": "sfam",
    },
    "super-nintendo-original-north-american-version": {
        "id": 68,
        "slug": "super-nintendo-original-north-american-version",
        "name": "Super Nintendo (original North American version)",
        "url": "https://www.igdb.com/platforms/snes/version/super-nintendo-original-north-american-version",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/ob1omu1he33vpulatqzv.jpg",
        "platform_slug": "snes",
    },
    "nintendo-3ds-xl-slash-ll": {
        "id": 675,
        "slug": "nintendo-3ds-xl-slash-ll",
        "name": "Nintendo 3DS XL/LL",
        "url": "https://www.igdb.com/platforms/3ds/version/nintendo-3ds-xl-slash-ll",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln5.jpg",
        "platform_slug": "3ds",
    },
    "nintendo-2ds": {
        "id": 676,
        "slug": "nintendo-2ds",
        "name": "Nintendo 2DS",
        "url": "https://www.igdb.com/platforms/3ds/version/nintendo-2ds",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pln6.jpg",
        "platform_slug": "3ds",
    },
    "new-nintendo-3ds-xl": {
        "id": 677,
        "slug": "new-nintendo-3ds-xl",
        "name": "New Nintendo 3DS XL",
        "url": "https://www.igdb.com/platforms/new-nintendo-3ds/version/new-nintendo-3ds-xl",
        "url_logo": "",
        "platform_slug": "new-nintendo-3ds",
    },
    "fm-towns-marty-2": {
        "id": 708,
        "slug": "fm-towns-marty-2",
        "name": "FM Towns Marty 2",
        "url": "https://www.igdb.com/platforms/fm-towns/version/fm-towns-marty-2",
        "url_logo": "",
        "platform_slug": "fm-towns",
    },
    "sega-mega-drive-slash-genesis": {
        "id": 64,
        "slug": "sega-mega-drive-slash-genesis",
        "name": "Sega Mega Drive/Genesis",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-drive-slash-genesis",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl85.jpg",
        "platform_slug": "genesis-slash-megadrive",
    },
    "vectrex": {
        "id": 70,
        "slug": "vectrex",
        "name": "Vectrex",
        "url": "https://www.igdb.com/platforms/vectrex/version/vectrex",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8h.jpg",
        "platform_slug": "vectrex",
    },
    "digiblast": {
        "id": 712,
        "slug": "digiblast",
        "name": "Digiblast",
        "url": "https://www.igdb.com/platforms/digiblast/version/digiblast",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plo2.jpg",
        "platform_slug": "digiblast",
    },
    "slimline": {
        "id": 114,
        "slug": "slimline",
        "name": "Slimline",
        "url": "https://www.igdb.com/platforms/ps2/version/slimline",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl72.jpg",
        "platform_slug": "ps2",
    },
    "oled-model": {
        "id": 503,
        "slug": "oled-model",
        "name": "OLED Model",
        "url": "https://www.igdb.com/platforms/switch/version/oled-model",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgu.jpg",
        "platform_slug": "switch",
    },
    "commodore-64c": {
        "id": 595,
        "slug": "commodore-64c",
        "name": "Commodore 64C",
        "url": "https://www.igdb.com/platforms/c64/version/commodore-64c",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pll3.jpg",
        "platform_slug": "c64",
    },
    "xbox-360-elite": {
        "id": 2,
        "slug": "xbox-360-elite",
        "name": "Xbox 360 Elite",
        "url": "https://www.igdb.com/platforms/xbox360/version/xbox-360-elite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6z.jpg",
        "platform_slug": "xbox360",
    },
    "nintendo-ds-lite": {
        "id": 190,
        "slug": "nintendo-ds-lite",
        "name": "Nintendo DS Lite",
        "url": "https://www.igdb.com/platforms/nds/version/nintendo-ds-lite",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pdn0g4fyks0y1v2ckzws.jpg",
        "platform_slug": "nds",
    },
    "game-boy-micro": {
        "id": 194,
        "slug": "game-boy-micro",
        "name": "Game Boy Micro",
        "url": "https://www.igdb.com/platforms/gba/version/game-boy-micro",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl74.jpg",
        "platform_slug": "gba",
    },
    "sega-master-system": {
        "id": 63,
        "slug": "sega-master-system",
        "name": "Sega Master System",
        "url": "https://www.igdb.com/platforms/sms/version/sega-master-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8a.jpg",
        "platform_slug": "sms",
    },
    "odyssey-us": {
        "id": 101,
        "slug": "odyssey-us",
        "name": "Odyssey (US)",
        "url": "https://www.igdb.com/platforms/odyssey--1/version/odyssey-us",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl8u.jpg",
        "platform_slug": "odyssey--1",
    },
    "texas-instruments-ti-99-slash-4a": {
        "id": 427,
        "slug": "texas-instruments-ti-99-slash-4a",
        "name": "Texas Instruments TI-99/4A",
        "url": "https://www.igdb.com/platforms/ti-99/version/texas-instruments-ti-99-slash-4a",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plf0.jpg",
        "platform_slug": "ti-99",
    },
    "amstrad-cpc-6128": {
        "id": 525,
        "slug": "amstrad-cpc-6128",
        "name": "Amstrad CPC 6128",
        "url": "https://www.igdb.com/platforms/acpc/version/amstrad-cpc-6128",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnh.jpg",
        "platform_slug": "acpc",
    },
    "ez-games-video-game-system": {
        "id": 623,
        "slug": "ez-games-video-game-system",
        "name": "EZ Games Video Game System",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/ez-games-video-game-system",
        "url_logo": "",
        "platform_slug": "genesis-slash-megadrive",
    },
    "aleck-64": {
        "id": 681,
        "slug": "aleck-64",
        "name": "Aleck 64",
        "url": "https://www.igdb.com/platforms/arcade/version/aleck-64",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plni.jpg",
        "platform_slug": "arcade",
    },
    "evercade-vs": {
        "id": 500,
        "slug": "evercade-vs",
        "name": "Evercade VS",
        "url": "https://www.igdb.com/platforms/evercade/version/evercade-vs",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plgm.jpg",
        "platform_slug": "evercade",
    },
    "sega-mega-jet": {
        "id": 624,
        "slug": "sega-mega-jet",
        "name": "Sega Mega Jet",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-mega-jet",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plne.jpg",
        "platform_slug": "genesis-slash-megadrive",
    },
    "cpc-464": {
        "id": 20,
        "slug": "cpc-464",
        "name": "CPC 464",
        "url": "https://www.igdb.com/platforms/acpc/version/cpc-464",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/nlizydzqnuzvzfdapqoj.jpg",
        "platform_slug": "acpc",
    },
    "windows-1-dot-0": {
        "id": 529,
        "slug": "windows-1-dot-0",
        "name": "Windows 1.0",
        "url": "https://www.igdb.com/platforms/win/version/windows-1-dot-0",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plin.jpg",
        "platform_slug": "win",
    },
    "handheld-pc": {
        "id": 539,
        "slug": "handheld-pc",
        "name": "Handheld PC",
        "url": "https://www.igdb.com/platforms/mobile/version/handheld-pc",
        "url_logo": "",
        "platform_slug": "mobile",
    },
    "evercade-exp": {
        "id": 594,
        "slug": "evercade-exp",
        "name": "Evercade EXP",
        "url": "https://www.igdb.com/platforms/evercade/version/evercade-exp",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plky.jpg",
        "platform_slug": "evercade",
    },
    "vt01": {
        "id": 686,
        "slug": "vt01",
        "name": "VT01",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt01",
        "url_logo": "",
        "platform_slug": "plug-and-play",
    },
    "vt09": {
        "id": 687,
        "slug": "vt09",
        "name": "VT09",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt09",
        "url_logo": "",
        "platform_slug": "plug-and-play",
    },
    "sega-nomad": {
        "id": 626,
        "slug": "sega-nomad",
        "name": "Sega Nomad",
        "url": "https://www.igdb.com/platforms/genesis-slash-megadrive/version/sega-nomad",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmc.jpg",
        "platform_slug": "genesis-slash-megadrive",
    },
    "nintendo-vs-system": {
        "id": 640,
        "slug": "nintendo-vs-system",
        "name": "Nintendo VS. System",
        "url": "https://www.igdb.com/platforms/arcade/version/nintendo-vs-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmi.jpg",
        "platform_slug": "arcade",
    },
    "vt02": {
        "id": 684,
        "slug": "vt02",
        "name": "VT02",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt02",
        "url_logo": "",
        "platform_slug": "plug-and-play",
    },
    "vt03": {
        "id": 685,
        "slug": "vt03",
        "name": "VT03",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt03",
        "url_logo": "",
        "platform_slug": "plug-and-play",
    },
    "vt32": {
        "id": 688,
        "slug": "vt32",
        "name": "VT32",
        "url": "https://www.igdb.com/platforms/plug-and-play/version/vt32",
        "url_logo": "",
        "platform_slug": "plug-and-play",
    },
    "master-system-super-compact": {
        "id": 630,
        "slug": "master-system-super-compact",
        "name": "Master System Super Compact",
        "url": "https://www.igdb.com/platforms/sms/version/master-system-super-compact",
        "url_logo": "",
        "platform_slug": "sms",
    },
    "game-television": {
        "id": 644,
        "slug": "game-television",
        "name": "Game Television",
        "url": "https://www.igdb.com/platforms/nes/version/game-television",
        "url_logo": "",
        "platform_slug": "nes",
    },
    "twin-famicom": {
        "id": 647,
        "slug": "twin-famicom",
        "name": "Twin Famicom",
        "url": "https://www.igdb.com/platforms/famicom/version/twin-famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plml.jpg",
        "platform_slug": "famicom",
    },
    "google-chrome": {
        "id": 659,
        "slug": "google-chrome",
        "name": "Google Chrome",
        "url": "https://www.igdb.com/platforms/browser/version/google-chrome",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmt.jpg",
        "platform_slug": "browser",
    },
    "leopard": {
        "id": 145,
        "slug": "leopard",
        "name": "Leopard",
        "url": "https://www.igdb.com/platforms/mac/version/leopard",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/db0qv9ovisi8e0isgkby.jpg",
        "platform_slug": "mac",
    },
    "playchoice-10": {
        "id": 641,
        "slug": "playchoice-10",
        "name": "PlayChoice-10",
        "url": "https://www.igdb.com/platforms/arcade/version/playchoice-10",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmg.jpg",
        "platform_slug": "arcade",
    },
    "xbox-series-x": {
        "id": 284,
        "slug": "xbox-series-x",
        "name": "Xbox Series X",
        "url": "https://www.igdb.com/platforms/series-x-s/version/xbox-series-x",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plfl.jpg",
        "platform_slug": "series-x-s",
    },
    "520-st": {
        "id": 30,
        "slug": "520-st",
        "name": "520 ST",
        "url": "https://www.igdb.com/platforms/atari-st/version/520-st",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pla7.jpg",
        "platform_slug": "atari-st",
    },
    "mavericks": {
        "id": 149,
        "slug": "mavericks",
        "name": "Mavericks",
        "url": "https://www.igdb.com/platforms/mac/version/mavericks",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/lsyardp2tldsqglhscqh.jpg",
        "platform_slug": "mac",
    },
    "playstation-portable-go": {
        "id": 278,
        "slug": "playstation-portable-go",
        "name": "PlayStation Portable Go",
        "url": "https://www.igdb.com/platforms/psp/version/playstation-portable-go",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/pl6p.jpg",
        "platform_slug": "psp",
    },
    "new-famicom": {
        "id": 642,
        "slug": "new-famicom",
        "name": "New Famicom",
        "url": "https://www.igdb.com/platforms/famicom/version/new-famicom",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plnf.jpg",
        "platform_slug": "famicom",
    },
    "epoch-cassette-vision": {
        "id": 493,
        "slug": "epoch-cassette-vision",
        "name": "Epoch Cassette Vision",
        "url": "https://www.igdb.com/platforms/epoch-cassette-vision/version/epoch-cassette-vision",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plko.jpg",
        "platform_slug": "epoch-cassette-vision",
    },
    "windows-11": {
        "id": 513,
        "slug": "windows-11",
        "name": "Windows 11",
        "url": "https://www.igdb.com/platforms/win/version/windows-11",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plim.jpg",
        "platform_slug": "win",
    },
    "new-style-nes": {
        "id": 643,
        "slug": "new-style-nes",
        "name": "New-Style NES",
        "url": "https://www.igdb.com/platforms/nes/version/new-style-nes",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plmo.jpg",
        "platform_slug": "nes",
    },
    "zx-spectrum": {
        "id": 79,
        "slug": "zx-spectrum",
        "name": "ZX Spectrum",
        "url": "https://www.igdb.com/platforms/zxs/version/zx-spectrum",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/plab.jpg",
        "platform_slug": "zxs",
    },
    "audiosonic-pp-1292-advanced-programmable-video-system": {
        "id": 197,
        "slug": "audiosonic-pp-1292-advanced-programmable-video-system",
        "name": "Audiosonic PP-1292 Advanced Programmable Video System",
        "url": "https://www.igdb.com/platforms/1292-advanced-programmable-video-system/version/audiosonic-pp-1292-advanced-programmable-video-system",
        "url_logo": "https://images.igdb.com/igdb/image/upload/t_1080p/f9a4tll5lnyxhlijvxjy.jpg",
        "platform_slug": "1292-advanced-programmable-video-system",
    },
}
