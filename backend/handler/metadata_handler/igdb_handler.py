import functools
import re
import sys
import time
from typing import Final, Optional, TypedDict, NotRequired

import pydash
import requests
from config import IGDB_CLIENT_ID, IGDB_CLIENT_SECRET
from handler.redis_handler import cache
from logger.logger import log
from requests.exceptions import HTTPError, Timeout
from unidecode import unidecode as uc

from . import (
    MetadataHandler,
    PS2_OPL_REGEX,
    SWITCH_TITLEDB_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
)

MAIN_GAME_CATEGORY: Final = 0
EXPANDED_GAME_CATEGORY: Final = 10
N_SCREENSHOTS: Final = 5
PS2_IGDB_ID: Final = 8
SWITCH_IGDB_ID: Final = 130
ARCADE_IGDB_IDS: Final = [52, 79, 80]


class IGDBPlatform(TypedDict):
    igdb_id: int
    slug: str
    name: NotRequired[str]


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
    genres: list[str]
    franchises: list[str]
    alternative_names: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    platforms: list[IGDBPlatform]
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
    igdb_metadata: Optional[IGDBMetadata]


def extract_metadata_from_igdb_rom(rom: dict) -> IGDBMetadata:
    return IGDBMetadata(
        {
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
                {"igdb_id": p.get("id", ""), "name": p.get("name", "")}
                for p in rom.get("platforms", [])
            ],
            "expansions": [
                {"cover_url": pydash.get(e, "cover.url", ""), "type": "expansion", **e}
                for e in rom.get("expansions", [])
            ],
            "dlcs": [
                {"cover_url": pydash.get(d, "cover.url", ""), "type": "dlc", **d}
                for d in rom.get("dlcs", [])
            ],
            "remasters": [
                {"cover_url": pydash.get(r, "cover.url", ""), "type": "remaster", **r}
                for r in rom.get("remasters", [])
            ],
            "remakes": [
                {"cover_url": pydash.get(r, "cover.url", ""), "type": "remake", **r}
                for r in rom.get("remakes", [])
            ],
            "expanded_games": [
                {"cover_url": pydash.get(g, "cover.url", ""), "type": "expanded", **g}
                for g in rom.get("expanded_games", [])
            ],
            "ports": [
                {"cover_url": pydash.get(p, "cover.url", ""), "type": "port", **p}
                for p in rom.get("ports", [])
            ],
            "similar_games": [
                {"cover_url": pydash.get(s, "cover.url", ""), "type": "similar", **s}
                for s in rom.get("similar_games", [])
            ],
        }
    )


class IGDBHandler(MetadataHandler):
    def __init__(self) -> None:
        self.platform_endpoint = "https://api.igdb.com/v4/platforms"
        self.platform_version_endpoint = "https://api.igdb.com/v4/platform_versions"
        self.platforms_fields = ["id", "name"]
        self.games_endpoint = "https://api.igdb.com/v4/games"
        self.games_fields = GAMES_FIELDS
        self.search_endpoint = "https://api.igdb.com/v4/search"
        self.search_fields = ["game.id", "name"]
        self.pagination_limit = 200
        self.twitch_auth = TwitchAuth()
        self.headers = {
            "Client-ID": IGDB_CLIENT_ID,
            "Authorization": f"Bearer {self.twitch_auth.get_oauth_token()}",
            "Accept": "application/json",
        }

    @staticmethod
    def check_twitch_token(func):
        @functools.wraps(func)
        def wrapper(*args):
            args[0].headers[
                "Authorization"
            ] = f"Bearer {args[0].twitch_auth.get_oauth_token()}"
            return func(*args)

        return wrapper

    def _request(self, url: str, data: str, timeout: int = 120) -> list:
        try:
            res = requests.post(
                url,
                f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=timeout,
            )
            res.raise_for_status()
            return res.json()
        except HTTPError as err:
            # Retry once if the auth token is invalid
            if err.response.status_code != 401:
                log.error(err)
                return []  # All requests to the IGDB API return a list

            # Attempt to force a token refresh if the token is invalid
            log.warning("Twitch token invalid: fetching a new one...")
            token = self.twitch_auth._update_twitch_token()
            self.headers["Authorization"] = f"Bearer {token}"
        except Timeout:
            # Retry once the request if it times out
            pass

        try:
            res = requests.post(
                url,
                f"{data} limit {self.pagination_limit};",
                headers=self.headers,
                timeout=timeout,
            )
            res.raise_for_status()
        except (HTTPError, Timeout) as err:
            # Log the error and return an empty list if the request fails again
            log.error(err)
            return []

        return res.json()

    def _search_rom(
        self, search_term: str, platform_idgb_id: int, category: int = 0
    ) -> dict | None:
        search_term = uc(search_term)
        category_filter: str = f"& category={category}" if category else ""
        roms = self._request(
            self.games_endpoint,
            data=f'search "{search_term}"; fields {",".join(self.games_fields)}; where platforms=[{platform_idgb_id}] {category_filter};',
        )

        if not roms:
            roms = self._request(
                self.search_endpoint,
                data=f'fields {",".join(self.search_fields)}; where game.platforms=[{platform_idgb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*);',
            )
            if roms:
                roms = self._request(
                    self.games_endpoint,
                    f'fields {",".join(self.games_fields)}; where id={roms[0]["game"]["id"]};',
                )

        exact_matches = [
            rom
            for rom in roms
            if rom["name"].lower() == search_term.lower()
            or rom["slug"].lower() == search_term.lower()
        ]

        return pydash.get(exact_matches or roms, "[0]", None)

    @check_twitch_token
    def get_platform(self, slug: str) -> IGDBPlatform:
        platforms = self._request(
            self.platform_endpoint,
            data=f'fields {",".join(self.platforms_fields)}; where slug="{slug.lower()}";',
        )

        platform = pydash.get(platforms, "[0]", None)
        if platform:
            return IGDBPlatform(
                igdb_id=platform["id"],
                slug=slug,
                name=platform["name"],
            )

        # Check if platform is a version if not found
        platform_versions = self._request(
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
    async def get_rom(self, file_name: str, platform_idgb_id: int) -> IGDBRom:
        from handler import fs_rom_handler

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)

        # Support for PS2 OPL filename format
        match = re.match(PS2_OPL_REGEX, file_name)
        if platform_idgb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)

        # Support for switch titleID filename format
        match = re.search(SWITCH_TITLEDB_REGEX, file_name)
        if platform_idgb_id == SWITCH_IGDB_ID and match:
            search_term = await self._switch_titledb_format(match, search_term)

        # Support for switch productID filename format
        match = re.search(SWITCH_PRODUCT_ID_REGEX, file_name)
        if platform_idgb_id == SWITCH_IGDB_ID and match:
            search_term = await self._switch_productid_format(match, search_term)

        # Support for MAME arcade filename format
        if platform_idgb_id in ARCADE_IGDB_IDS:
            search_term = await self._mame_format(search_term)

        search_term = self._normalize_search_term(search_term)

        rom = (
            self._search_rom(search_term, platform_idgb_id, MAIN_GAME_CATEGORY)
            or self._search_rom(search_term, platform_idgb_id, EXPANDED_GAME_CATEGORY)
            or self._search_rom(search_term, platform_idgb_id)
        )

        if not rom:
            return IGDBRom(igdb_id=None)

        return IGDBRom(
            igdb_id=rom["id"],
            slug=rom["slug"],
            name=rom["name"],
            summary=rom.get("summary", ""),
            url_cover=self._normalize_cover_url(rom.get("cover", {}).get("url", "")),
            url_screenshots=[
                self._normalize_cover_url(s.get("url", "")).replace(
                    "t_thumb", "t_original"
                )
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(rom),
        )

    @check_twitch_token
    def get_rom_by_id(self, igdb_id: int) -> IGDBRom:
        roms = self._request(
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
            url_cover=self._normalize_cover_url(rom.get("cover", {}).get("url", "")),
            url_screenshots=[
                self._normalize_cover_url(s.get("url", "")).replace(
                    "t_thumb", "t_original"
                )
                for s in rom.get("screenshots", [])
            ],
            igdb_metadata=extract_metadata_from_igdb_rom(rom),
        )

    @check_twitch_token
    def get_matched_roms_by_id(self, igdb_id: int) -> list[IGDBRom]:
        return [self.get_rom_by_id(igdb_id)]

    @check_twitch_token
    def get_matched_roms_by_name(
        self, search_term: str, platform_idgb_id: int, search_extended: bool = False
    ) -> list[IGDBRom]:
        if not platform_idgb_id:
            return []

        search_term = uc(search_term)
        matched_roms = self._request(
            self.games_endpoint,
            data=f'search "{search_term}"; fields {",".join(self.games_fields)}; where platforms=[{platform_idgb_id}];',
        )

        if not matched_roms or search_extended:
            log.info("Extended searching...")
            alternative_matched_roms = self._request(
                self.search_endpoint,
                data=f'fields {",".join(self.search_fields)}; where game.platforms=[{platform_idgb_id}] & (name ~ *"{search_term}"* | alternative_name ~ *"{search_term}"*);',
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
                alternative_matched_roms = self._request(
                    self.games_endpoint,
                    f'fields {",".join(self.games_fields)}; where {id_filter};',
                )
                matched_roms.extend(alternative_matched_roms)

        # Use a dictionary to keep track of unique ids
        unique_ids = {}

        # Use a list comprehension to filter duplicates based on the 'id' key
        matched_roms = [
            unique_ids.setdefault(rom["id"], rom)
            for rom in matched_roms
            if rom["id"] not in unique_ids
        ]

        return [
            IGDBRom(
                {
                    k: v
                    for k, v in {
                        "igdb_id": rom["id"],
                        "slug": rom["slug"],
                        "name": rom["name"],
                        "summary": rom.get("summary", ""),
                        "url_cover": self._normalize_cover_url(
                            rom.get("cover", {})
                            .get("url", "")
                            .replace("t_thumb", "t_cover_big")
                        ),
                        "url_screenshots": [
                            self._normalize_cover_url(s.get("url", "")).replace(
                                "t_thumb", "t_original"
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


class TwitchAuth:
    def _update_twitch_token(self) -> str:
        res = requests.post(
            url="https://id.twitch.tv/oauth2/token",
            params={
                "client_id": IGDB_CLIENT_ID,
                "client_secret": IGDB_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=30,
        ).json()

        token = res.get("access_token", "")
        expires_in = res.get("expires_in", 0)
        if not token or expires_in == 0:
            log.error(
                "Could not get twitch auth token: check client_id and client_secret"
            )
            sys.exit(2)

        # Set token in redis to expire in <expires_in> seconds
        cache.set("romm:twitch_token", token, ex=expires_in - 10)  # type: ignore[attr-defined]
        cache.set("romm:twitch_token_expires_at", time.time() + expires_in - 10)  # type: ignore[attr-defined]

        log.info("Twitch token fetched!")

        return token

    def get_oauth_token(self) -> str:
        # Use a fake token when running tests
        if "pytest" in sys.modules:
            return "test_token"

        # Fetch the token cache
        token = cache.get("romm:twitch_token")  # type: ignore[attr-defined]
        token_expires_at = cache.get("romm:twitch_token_expires_at")  # type: ignore[attr-defined]

        if not token or time.time() > float(token_expires_at or 0):
            log.warning("Twitch token invalid: fetching a new one...")
            return self._update_twitch_token()

        return token


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
]
