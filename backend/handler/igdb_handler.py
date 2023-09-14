import sys
import functools
import pydash
import requests
import re
import time
from unidecode import unidecode as uc
from requests.exceptions import HTTPError, Timeout
from typing import Final
from typing_extensions import TypedDict

from config import IGDB_CLIENT_ID, IGDB_CLIENT_SECRET
from utils import get_file_name_with_no_tags as get_search_term
from logger.logger import log
from utils.cache import cache
from .ps2_opl_index import opl_index

MAIN_GAME_CATEGORY: Final = 0
EXPANDED_GAME_CATEGORY: Final = 10
N_SCREENSHOTS: Final = 5
PS2_IGDB_ID: Final = 8
PS2_OPL_REGEX: Final = r"^([A-Z]{4}_\d{3}\.\d{2})\..*$"


class IGDBPlatformType(TypedDict):
    igdb_id: str
    name: str


class IGDBRomType(TypedDict):
    igdb_id: str
    slug: str
    name: str
    summary: str
    url_cover: str
    url_screenshots: list[str]


class IGDBHandler:
    def __init__(self) -> None:
        self.platform_url = "https://api.igdb.com/v4/platforms/"
        self.games_url = "https://api.igdb.com/v4/games/"
        self.covers_url = "https://api.igdb.com/v4/covers/"
        self.screenshots_url = "https://api.igdb.com/v4/screenshots/"
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
            res = requests.post(url, data, headers=self.headers, timeout=timeout)
            res.raise_for_status()
            return res.json()
        except (HTTPError, Timeout) as err:
            if err.response.status_code != 401:
                log.error(err)
                return []  # All requests to the IGDB API return a list

        # Attempt to force a token refresh if the token is invalid
        log.warning("Twitch token invalid: fetching a new one...")
        token = self.twitch_auth._update_twitch_token()
        self.headers["Authorization"] = f"Bearer {token}"

        try:
            res = requests.post(url, data, headers=self.headers, timeout=timeout)
            res.raise_for_status()
        except (HTTPError, Timeout) as err:
            # Log the error and return an empty list if the request fails again
            log.error(err)
            return []

        return res.json()

    def _search_rom(
        self, search_term: str, platform_idgb_id: int, category: int = 0
    ) -> dict:
        category_filter: str = f"& category={category}" if category else ""
        roms = self._request(
            self.games_url,
            data=f"""
                search "{search_term}";
                fields id, slug, name, summary, screenshots;
                where platforms=[{platform_idgb_id}] {category_filter};
            """,
        )

        exact_matches = [
            rom
            for rom in roms
            if rom["name"].lower() == search_term.lower()
            or rom["slug"].lower() == search_term.lower()
        ]

        return pydash.get(exact_matches or roms, "[0]", {})

    @staticmethod
    def _normalize_cover_url(url: str) -> str:
        return f"https:{url.replace('https:', '')}"

    def _search_cover(self, rom_id: int) -> str:
        covers = self._request(
            self.covers_url,
            data=f"fields url; where game={rom_id};",
        )

        cover = pydash.get(covers, "[0]", None)
        return "" if not cover else self._normalize_cover_url(cover["url"])

    def _search_screenshots(self, rom_id: int) -> list:
        screenshots = self._request(
            self.screenshots_url,
            data=f"fields url; where game={rom_id}; limit {N_SCREENSHOTS};",
        )

        return [
            self._normalize_cover_url(r["url"]).replace("t_thumb", "t_original")
            for r in screenshots
            if "url" in r.keys()
        ]

    @check_twitch_token
    def get_platform(self, slug: str) -> IGDBPlatformType:
        platforms = self._request(
            self.platform_url,
            data=f'fields id, name; where slug="{slug.lower()}";',
        )

        platform = pydash.get(platforms, "[0]", None)
        if not platform:
            return {
                "igdb_id": "",
                "name": slug,
            }

        return {
            "igdb_id": platform["id"],
            "name": platform["name"],
        }

    @check_twitch_token
    def get_rom(self, file_name: str, platform_idgb_id: int) -> IGDBRomType:
        search_term = get_search_term(file_name)

        # Patch support for PS2 OPL flename format
        match = re.match(PS2_OPL_REGEX, search_term)
        if platform_idgb_id == PS2_IGDB_ID and match:
            serial_code = match.group(1)
            index_entry = opl_index.get(serial_code, None)
            if index_entry:
                search_term = index_entry["Name"]  # type: ignore

        res = (
            self._search_rom(uc(search_term), platform_idgb_id, MAIN_GAME_CATEGORY)
            or self._search_rom(
                uc(search_term), platform_idgb_id, EXPANDED_GAME_CATEGORY
            )
            or self._search_rom(uc(search_term), platform_idgb_id)
        )

        igdb_id = res.get("id", None)
        slug = res.get("slug", "")
        name = res.get("name", search_term)
        summary = res.get("summary", "")

        return {
            "igdb_id": igdb_id,
            "slug": slug,
            "name": name,
            "summary": summary,
            "url_cover": self._search_cover(igdb_id),
            "url_screenshots": self._search_screenshots(igdb_id),
        }

    @check_twitch_token
    def get_rom_by_id(self, igdb_id: int) -> IGDBRomType:
        roms = self._request(
            self.games_url,
            f"fields slug, name, summary; where id={igdb_id};",
        )
        rom = pydash.get(roms, "[0]", {})

        return {
            "igdb_id": igdb_id,
            "slug": rom.get("slug", ""),
            "name": rom.get("name", ""),
            "summary": rom.get("summary", ""),
            "url_cover": self._search_cover(igdb_id),
            "url_screenshots": self._search_screenshots(igdb_id),
        }

    @check_twitch_token
    def get_matched_roms_by_id(self, igdb_id: int) -> list[IGDBRomType]:
        matched_rom = self.get_rom_by_id(igdb_id)
        matched_rom.update(
            url_cover=matched_rom["url_cover"].replace("t_thumb", "t_cover_big"),
        )
        return [matched_rom]

    @check_twitch_token
    def get_matched_roms_by_name(
        self, search_term: str, platform_idgb_id: int
    ) -> list[IGDBRomType]:
        if not platform_idgb_id:
            return []

        matched_roms = self._request(
            self.games_url,
            data=f"""
                search "{uc(search_term)}";
                fields id, slug, name, summary;
                where platforms=[{platform_idgb_id}];
            """,
        )

        return [
            dict(
                rom,
                url_cover=self._search_cover(rom["id"]).replace(
                    "t_thumb", "t_cover_big"
                ),
                url_screenshots=self._search_screenshots(rom["id"]),
                igdb_id=rom.pop("id"),
                slug=rom.pop("slug"),
                name=rom.pop("name"),
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
