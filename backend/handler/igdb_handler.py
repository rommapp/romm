import sys
import functools
from time import time
from unidecode import unidecode as uc

import requests
from config import CLIENT_ID, CLIENT_SECRET
from utils import get_file_name_with_no_tags as get_search_term
from logger.logger import log


class IGDBHandler:
    def __init__(self) -> None:
        self.platform_url = "https://api.igdb.com/v4/platforms/"
        self.games_url = "https://api.igdb.com/v4/games/"
        self.covers_url = "https://api.igdb.com/v4/covers/"
        self.screenshots_url = "https://api.igdb.com/v4/screenshots/"
        self.twitch_auth = TwitchAuth()
        self.headers = {
            "Client-ID": self.twitch_auth.client_id,
            "Authorization": f"Bearer {self.twitch_auth.get_oauth_token()}",
            "Accept": "application/json",
        }

    def check_twitch_token(func) -> tuple:
        @functools.wraps(func)
        def wrapper(*args):
            args[0].headers[
                "Authorization"
            ] = f"Bearer {args[0].twitch_auth.get_oauth_token()}"
            return func(*args)

        return wrapper

    def _search_rom(
        self, search_term: str, p_igdb_id: int, category: int = None
    ) -> dict:
        category_filter: str = f"& category={category}" if category else ""
        try:
            return requests.post(
                self.games_url,
                headers=self.headers,
                data=f"""
                    search "{search_term}";
                    fields id, slug, name, summary, screenshots;
                    where platforms=[{p_igdb_id}] {category_filter};
                """,
            ).json()[0]
        except IndexError:
            return {}

    @staticmethod
    def _normalize_cover_url(url: str) -> str:
        return f"https:{url.replace('https:', '')}"

    def _search_cover(self, rom_id: str) -> str:
        try:
            res = requests.post(
                self.covers_url,
                headers=self.headers,
                data=f"fields url; where game={rom_id};",
                timeout=120,
            ).json()[0]
        except IndexError:
            return ""

        return self._normalize_cover_url(res["url"]) if "url" in res.keys() else ""

    def _search_screenshots(self, rom_id: str) -> list:
        res = requests.post(
            self.screenshots_url,
            headers=self.headers,
            data=f"fields url; where game={rom_id}; limit 5;",
            timeout=120,
        ).json()
        return [
            self._normalize_cover_url(r["url"]).replace("t_thumb", "t_original")
            for r in res
            if "url" in r.keys()
        ]

    @check_twitch_token
    def get_platform(self, slug: str):
        try:
            res = requests.post(
                self.platform_url,
                headers=self.headers,
                data=f'fields id, name; where slug="{slug.lower()}";',
                timeout=120,
            ).json()[0]

            return {
                "igdb_id": res["id"],
                "name": res["name"],
                "slug": slug,
            }
        except IndexError:
            log.warning(f"{slug} not found in IGDB")

        return {
            "igdb_id": "",
            "name": slug,
            "slug": slug,
        }

    @check_twitch_token
    def get_rom(self, file_name: str, p_igdb_id: int):
        search_term = uc(get_search_term(file_name))
        res = (
            self._search_rom(search_term, p_igdb_id, 0)
            or self._search_rom(search_term, p_igdb_id, 10)
            or self._search_rom(search_term, p_igdb_id)
        )

        r_igdb_id = res.get("id", 0)
        r_slug = res.get("slug", "")
        r_name = res.get("name", search_term)
        summary = res.get("summary", "")

        if not r_igdb_id:
            log.warning(f"{r_name} not found in IGDB")

        return {
            "r_igdb_id": r_igdb_id,
            "r_slug": r_slug,
            "r_name": r_name,
            "summary": summary,
            "url_cover": self._search_cover(r_igdb_id),
            "url_screenshots": self._search_screenshots(r_igdb_id),
        }

    @check_twitch_token
    def get_rom_by_id(self, r_igdb_id: str):
        res = requests.post(
            self.games_url,
            headers=self.headers,
            data=f"fields slug, name, summary; where id={r_igdb_id};",
            timeout=120,
        )

        try:
            rom = res.json()[0]
            return {
                "r_igdb_id": r_igdb_id,
                "r_slug": rom.get("slug", ""),
                "r_name": rom.get("name", ""),
                "summary": rom.get("summary", ""),
                "url_cover": self._search_cover(r_igdb_id),
                "url_screenshots": self._search_screenshots(r_igdb_id),
            }
        except IndexError:
            return {}

    @check_twitch_token
    def get_matched_roms_by_id(self, r_igdb_id: str):
        matched_rom = self.get_rom_by_id(r_igdb_id)
        matched_rom.update(
            url_cover=matched_rom["url_cover"].replace("t_thumb", "t_cover_big"),
        )
        return [matched_rom]

    @check_twitch_token
    def get_matched_roms_by_name(self, search_term: str, p_igdb_id: int):
        matched_roms = requests.post(
            self.games_url,
            headers=self.headers,
            data=f"""
                search "{uc(search_term)}";
                fields id, slug, name, summary;
                where platforms=[{p_igdb_id}];
            """,
            timeout=120,
        ).json()

        return [
            dict(
                rom,
                url_cover=self._search_cover(rom["id"]).replace(
                    "t_thumb", "t_cover_big"
                ),
                url_screenshots=self._search_screenshots(rom["id"]),
                r_igdb_id=rom.pop("id"),
                r_slug=rom.pop("slug"),
                r_name=rom.pop("name"),
            )
            for rom in matched_roms
        ]

    @check_twitch_token
    def get_matched_roms(self, file_name: str, p_igdb_id: int):
        if not p_igdb_id:
            return []

        matched_roms = requests.post(
            self.games_url,
            headers=self.headers,
            data=f"""
                search "{uc(get_search_term(file_name))}";
                fields id, slug, name, summary;
                where platforms=[{p_igdb_id}];
            """,
            timeout=120,
        ).json()

        return [
            dict(
                rom,
                url_cover=self._search_cover(rom["id"]).replace(
                    "t_thumb", "t_cover_big"
                ),
                url_screenshots=self._search_screenshots(rom["id"]),
                r_igdb_id=rom.pop("id"),
                r_slug=rom.pop("slug"),
                r_name=rom.pop("name"),
            )
            for rom in matched_roms
        ]


class TwitchAuth:
    def __init__(self) -> None:
        self.base_url = "https://id.twitch.tv/oauth2/token"
        self.token = ""
        self.token_checkout = int(time())
        self.secure_seconds_offset = 10  # seconds offset to avoid invalid token
        self.token_valid_seconds = 0
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET

    def _is_token_valid(self) -> bool:
        return (
            int(time()) + self.secure_seconds_offset - self.token_checkout
            < self.token_valid_seconds
        )

    def _update_twitch_token(self):
        res = requests.post(
            url=self.base_url,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        ).json()

        self.token_checkout = int(time())
        self.token_valid_seconds = res.get("expires_in", 0)
        self.token = res.get("access_token", "")

        if not self.token:
            log.error(
                "Could not get twitch auth token: check client_id and client_secret"
            )
            sys.exit(2)

        log.info("Twitch token fetched!")

    def get_oauth_token(self) -> str:
        if not self._is_token_valid():
            log.warning("Twitch token invalid: fetching a new one…")
            self._update_twitch_token()

        return self.token
