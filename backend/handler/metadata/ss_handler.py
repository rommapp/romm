import asyncio
import base64
import http
import json
import re
from datetime import datetime
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import httpx
import pydash
import yarl
from config import SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
from fastapi import HTTPException, status
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

# Used to display the Screenscraper API status in the frontend
SS_API_ENABLED: Final = bool(SCREENSCRAPER_USER) and bool(SCREENSCRAPER_PASSWORD)
SS_DEV_ID: Final = base64.b64decode("enVyZGkxNQ==").decode()
SS_DEV_PASSWORD: Final = base64.b64decode("eFRKd29PRmpPUUc=").decode()

PS1_SS_ID: Final = 57
PS2_SS_ID: Final = 58
PSP_SS_ID: Final = 61
SWITCH_SS_ID: Final = 225
ARCADE_SS_IDS: Final = [
    6,
    7,
    8,
    47,
    49,
    52,
    53,
    54,
    55,
    56,
    68,
    69,
    75,
    112,
    142,
    147,
    148,
    149,
    150,
    151,
    152,
    153,
    154,
    155,
    156,
    157,
    158,
    159,
    160,
    161,
    162,
    163,
    164,
    165,
    166,
    167,
    168,
    169,
    170,
    173,
    174,
    175,
    176,
    177,
    178,
    179,
    180,
    181,
    182,
    183,
    184,
    185,
    186,
    187,
    188,
    189,
    190,
    191,
    192,
    193,
    194,
    195,
    196,
    209,
    227,
    130,
    158,
    269,
]


class SSPlatform(TypedDict):
    slug: str
    ss_id: int | None
    name: NotRequired[str]


class SSAgeRating(TypedDict):
    rating: str
    category: str
    rating_cover_url: str


class SSMetadata(TypedDict):
    ss_score: str
    first_release_date: int | None
    alternative_names: list[str]
    companies: list[str]
    franchises: list[str]
    game_modes: list[str]
    genres: list[str]


class SSRom(TypedDict):
    ss_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_manual: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    ss_metadata: NotRequired[SSMetadata]


def extract_metadata_from_ss_rom(rom: dict) -> SSMetadata:
    def _normalize_score(score: str) -> str:
        """Normalize the score to be between 0 and 10 because for some reason Screenscraper likes to rate over 20."""
        try:
            return str(int(score) / 2)
        except (ValueError, TypeError):
            return ""

    def _get_lowest_date(dates: list[str]) -> int | None:
        lowest_date = pydash.chain(dates).map("text").sort().head().value()
        if lowest_date:
            try:
                lowest_date = int(
                    datetime.strptime(lowest_date, "%Y-%m-%d").timestamp()
                )
            except ValueError:
                try:
                    lowest_date = int(datetime.strptime(lowest_date, "%Y").timestamp())
                except ValueError:
                    lowest_date = None
        else:
            lowest_date = None
        return lowest_date

    def _get_genres(rom: dict) -> list[str]:
        return (
            pydash.chain(rom.get("genres", []))
            .map("noms")
            .flatten()
            .filter({"langue": "en"})
            .map("text")
            .value()
        )

    def _get_franchises(rom: dict) -> list[str]:
        return (
            pydash.chain(rom.get("familles", []))
            .map("noms")
            .flatten()
            .filter({"langue": "en"})
            .map("text")
            .value()
            or pydash.chain(rom.get("familles", []))
            .map("noms")
            .flatten()
            .filter({"langue": "fr"})
            .map("text")
            .value()
        )

    def _get_game_modes(rom: dict) -> list[str]:
        return (
            pydash.chain(rom.get("modes", []))
            .map("noms")
            .flatten()
            .filter({"langue": "en"})
            .map("text")
            .value()
            or pydash.chain(rom.get("modes", []))
            .map("noms")
            .flatten()
            .filter({"langue": "fr"})
            .map("text")
            .value()
        )

    return SSMetadata(
        {
            "ss_score": _normalize_score(pydash.get(rom, "note.text", None)),
            "alternative_names": pydash.map_(rom.get("noms", []), "text"),
            "companies": pydash.compact(
                [
                    pydash.get(rom, "editeur.text", None),
                    pydash.get(rom, "developpeur.text", None),
                ]
            ),
            "genres": _get_genres(rom),
            "first_release_date": _get_lowest_date(rom.get("dates", [])),
            "franchises": _get_franchises(rom),
            "game_modes": _get_game_modes(rom),
        }
    )


class SSHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.screenscraper.fr/api2"
        self.search_endpoint = f"{self.BASE_URL}/jeuRecherche.php"
        self.platform_endpoint = f"{self.BASE_URL}/systemesListe.php"
        self.games_endpoint = f"{self.BASE_URL}/jeuInfos.php"
        self.LOGIN_ERROR_CHECK: Final = "Erreur de login"

    async def _request(self, url: str, timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = yarl.URL(url).update_query(
            ssid=SCREENSCRAPER_USER,
            sspassword=SCREENSCRAPER_PASSWORD,
            devid=SS_DEV_ID,
            devpassword=SS_DEV_PASSWORD,
            softname="romm",
            output="json",
        )
        masked_url = authorized_url.with_query(
            self._mask_sensitive_values(dict(authorized_url.query))
        )

        log.debug(
            "API request: URL=%s, Timeout=%s",
            masked_url,
            timeout,
        )

        try:
            res = await httpx_client.get(str(authorized_url), timeout=timeout)
            res.raise_for_status()
            if self.LOGIN_ERROR_CHECK in res.text:
                log.error("Invalid screenscraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid screenscraper credentials",
                )

            return res.json()
        except httpx.NetworkError as exc:
            log.critical(
                "Connection error: can't connect to Screenscrapper", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Screenscrapper, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == http.HTTPStatus.UNAUTHORIZED:
                # Sometimes Screenscrapper returns 401 even with a valid API key
                log.error(exc)
                return {}
            elif exc.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(exc)
                return {}
        except json.decoder.JSONDecodeError as exc:
            # Log the error and return an empty list if the response is not valid JSON
            log.error(exc)
            return {}
        except httpx.TimeoutException:
            log.debug(
                "Request to URL=%s timed out. Retrying with URL=%s", masked_url, url
            )

        # Retry the request once if it times out
        try:
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                timeout,
            )
            res = await httpx_client.get(url, timeout=timeout)
            res.raise_for_status()

            if self.LOGIN_ERROR_CHECK in res.text:
                log.error("Invalid screenscraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid screenscraper credentials",
                )

            return res.json()
        except (
            httpx.HTTPStatusError,
            httpx.TimeoutException,
            json.decoder.JSONDecodeError,
        ) as exc:
            # Log the error and return an empty dict if the request fails with a different code
            log.error(exc)
            return {}

    async def _search_rom(self, search_term: str, platform_ss_id: int) -> dict | None:
        if not platform_ss_id:
            return None

        search_term = uc(search_term)
        url = yarl.URL(self.search_endpoint).with_query(
            systemeid=[platform_ss_id],
            recherche=quote(search_term, safe="/ "),
        )
        found_roms = (await self._request(str(url))).get("response", {}).get("jeux", [])
        # If no roms are return, "jeux" is list with an empty dict that can lead to issues. It needs to be checked.
        roms = [] if len(found_roms) == 1 and not found_roms[0] else found_roms
        return pydash.get(roms, "[0]", None)

    def get_platform(self, slug: str) -> SSPlatform:
        platform = SLUG_TO_SS_ID.get(slug, None)

        if not platform:
            return SSPlatform(ss_id=None, slug=slug)

        return SSPlatform(
            ss_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, file_name: str, platform_ss_id: int) -> SSRom:
        from handler.filesystem import fs_rom_handler

        if not SS_API_ENABLED:
            return SSRom(ss_id=None)

        if not platform_ss_id:
            return SSRom(ss_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = SSRom(ss_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(file_name)
        if platform_ss_id == PS2_SS_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = SSRom(ss_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(file_name, re.IGNORECASE)
        if platform_ss_id == PS1_SS_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = SSRom(ss_id=None, name=search_term)

        if platform_ss_id == PS2_SS_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = SSRom(ss_id=None, name=search_term)

        if platform_ss_id == PSP_SS_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = SSRom(ss_id=None, name=search_term)

        # Support for switch titleID filename format
        match = SWITCH_TITLEDB_REGEX.search(file_name)
        if platform_ss_id == SWITCH_SS_ID and match:
            search_term, index_entry = await self._switch_titledb_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = SSRom(
                    ss_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_manual=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for switch productID filename format
        match = SWITCH_PRODUCT_ID_REGEX.search(file_name)
        if platform_ss_id == SWITCH_SS_ID and match:
            search_term, index_entry = await self._switch_productid_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = SSRom(
                    ss_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_manual=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for MAME arcade filename format
        if platform_ss_id in ARCADE_SS_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = SSRom(ss_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)
        res = await self._search_rom(search_term, platform_ss_id)

        # Some MAME games have two titles split by a slash
        if not res and "/" in search_term:
            for term in search_term.split("/"):
                res = await self._search_rom(term.strip(), platform_ss_id)
                if res:
                    break

        if not res or not res.get("id", None):
            return fallback_rom

        ss_id: int = int(res.get("id", None))

        rom = {
            "ss_id": ss_id,
            "name": pydash.chain(res.get("noms", []))
            .filter({"region": "ss"})
            .map("text")
            .head()
            .value(),
            "slug": pydash.chain(res.get("noms", []))
            .filter({"region": "ss"})
            .map("text")
            .head()
            .value(),
            "summary": pydash.chain(res.get("synopsis", []))
            .filter({"langue": "en"})
            .map("text")
            .head()
            .value(),
            "url_cover": pydash.chain(res.get("medias", []))
            .filter({"region": "us", "type": "box-2D", "parent": "jeu"})
            .map("url")
            .head()
            .value()
            or "",
            "url_manual": pydash.chain(res.get("medias", []))
            .filter(
                {"region": "us", "type": "manuel", "parent": "jeu", "format": "pdf"}
            )
            .map("url")
            .head()
            .value()
            or pydash.chain(res.get("medias", []))
            .filter(
                {"region": "eu", "type": "manuel", "parent": "jeu", "format": "pdf"}
            )
            .map("url")
            .head()
            .value()
            or "",
            "url_screenshots": [],
            "ss_metadata": extract_metadata_from_ss_rom(res),
        }

        return SSRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, ss_id: int) -> SSRom:
        if not SS_API_ENABLED:
            return SSRom(ss_id=None)

        url = yarl.URL(self.games_endpoint).with_query(gameid=ss_id)
        res = (await self._request(str(url))).get("response", {}).get("jeu", [])

        if not res:
            return SSRom(ss_id=None)

        rom = {
            "ss_id": res.get("id"),
            "name": pydash.chain(res.get("noms", []))
            .filter({"region": "ss"})
            .map("text")
            .head()
            .value(),
            "slug": pydash.chain(res.get("noms", []))
            .filter({"region": "ss"})
            .map("text")
            .head()
            .value(),
            "summary": pydash.chain(res.get("synopsis", []))
            .filter({"langue": "en"})
            .map("text")
            .head()
            .value(),
            "url_cover": pydash.chain(res.get("medias", []))
            .filter({"region": "us", "type": "box-2D", "parent": "jeu"})
            .map("url")
            .head()
            .value()
            or "",
            "url_manual": pydash.chain(res.get("medias", []))
            .filter(
                {"region": "us", "type": "manuel", "parent": "jeu", "format": "pdf"}
            )
            .map("url")
            .head()
            .value()
            or pydash.chain(res.get("medias", []))
            .filter(
                {"region": "eu", "type": "manuel", "parent": "jeu", "format": "pdf"}
            )
            .map("url")
            .head()
            .value()
            or "",
            "url_screenshots": [],
            "ss_metadata": extract_metadata_from_ss_rom(res),
        }

        return SSRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_matched_rom_by_id(self, ss_id: int) -> SSRom | None:
        if not SS_API_ENABLED:
            return None

        rom = await self.get_rom_by_id(ss_id)
        return rom if rom.get("ss_id", "") else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_ss_id: int
    ) -> list[SSRom]:
        if not SS_API_ENABLED:
            return []

        if not platform_ss_id:
            return []

        search_term = uc(search_term)
        url = yarl.URL(self.search_endpoint).with_query(
            systemeid=[platform_ss_id],
            recherche=quote(search_term, safe="/ "),
        )
        roms = (await self._request(str(url))).get("response", {}).get("jeux", [])
        # If no roms are return, "jeux" is list with an empty dict that can lead to issues. It needs to be checked.
        matched_roms = [] if len(roms) == 1 and not roms[0] else roms

        def _get_name(rom: dict) -> str | None:
            return (
                pydash.chain(rom.get("noms", []))
                .filter({"region": "ss"})
                .map("text")
                .head()
                .value()
            )

        def _get_slug(rom: dict) -> str | None:
            return (
                pydash.chain(rom.get("noms", []))
                .filter({"region": "ss"})
                .map("text")
                .head()
                .value()
            )

        def _get_summary(rom: dict) -> str | None:
            return (
                pydash.chain(rom.get("synopsis", []))
                .filter({"langue": "en"})
                .map("text")
                .head()
                .value()
            )

        def _get_url_cover(rom: dict) -> str:
            return (
                pydash.chain(rom.get("medias", []))
                .filter({"region": "us", "type": "box-2D", "parent": "jeu"})
                .map("url")
                .head()
                .value()
                or ""
            )

        def _get_url_manual(rom: dict) -> str:
            return (
                pydash.chain(rom.get("medias", []))
                .filter(
                    {
                        "region": "us",
                        "type": "manuel",
                        "parent": "jeu",
                        "format": "pdf",
                    }
                )
                .map("url")
                .head()
                .value()
                or pydash.chain(rom.get("medias", []))
                .filter(
                    {
                        "region": "eu",
                        "type": "manuel",
                        "parent": "jeu",
                        "format": "pdf",
                    }
                )
                .map("url")
                .head()
                .value()
                or ""
            )

        def _is_ss_region(rom: dict) -> bool:
            return bool(
                pydash.chain(rom.get("noms", []))
                .filter({"region": "ss"})
                .map("text")
                .head()
                .value()
            )

        return [
            SSRom(
                {  # type: ignore[misc]
                    k: v
                    for k, v in {
                        "ss_id": rom.get("id"),
                        "name": _get_name(rom),
                        "slug": _get_slug(rom),
                        "summary": _get_summary(rom),
                        "url_cover": _get_url_cover(rom),
                        "url_manual": _get_url_manual(rom),
                        "url_screenshots": [],
                        "ss_metadata": extract_metadata_from_ss_rom(rom),
                    }.items()
                    if v and _is_ss_region(rom) and rom.get("id", False)
                }
            )
            for rom in matched_roms
        ]


class SlugToSSId(TypedDict):
    id: int
    name: str


SLUG_TO_SS_ID: dict[str, SlugToSSId] = {
    "3do": {"id": 29, "name": "3DO"},
    "amiga": {"id": 64, "name": "Amiga"},
    "amiga-cd32": {"id": 134, "name": "Amiga CD"},
    "cpc": {"id": 60, "name": "CPC"},
    "acpc": {"id": 60, "name": "CPC"},  # IGDB
    "android": {"id": 63, "name": "Android"},
    "apple2": {"id": 86, "name": "Apple II"},
    "appleii": {"id": 86, "name": "Apple II"},  # IGDB
    "apple2gs": {"id": 217, "name": "Apple IIGS"},
    "apple-iigs": {"id": 51, "name": "Apple IIGS"},  # IGDB
    "arcadia-2001": {"id": 94, "name": "Arcadia 2001"},
    "arduboy": {"id": 263, "name": "Arduboy"},
    "atari-2600": {"id": 26, "name": "Atari 2600"},
    "atari2600": {"id": 26, "name": "Atari 2600"},  # IGDB
    "atari-5200": {"id": 40, "name": "Atari 5200"},
    "atari5200": {"id": 40, "name": "Atari 5200"},  # IGDB
    "atari-7800": {"id": 41, "name": "Atari 7800"},
    "atari7800": {"id": 41, "name": "Atari 7800"},  # IGDB
    "atari-8-bit": {"id": 43, "name": "Atari 8bit"},
    "atari8bit": {"id": 43, "name": "Atari 8bit"},  # IGDB
    "atari-st": {"id": 42, "name": "Atari ST"},
    "atom": {"id": 36, "name": "Atom"},
    "bbc-micro": {"id": 37, "name": "BBC Micro"},
    "bbcmicro": {"id": 37, "name": "BBC Micro"},  # IGDB
    "bally-astrocade": {"id": 44, "name": "Astrocade"},
    "astrocade": {"id": 44, "name": "Astrocade"},  # IGDB
    "cd-i": {"id": 133, "name": "CD-i"},
    "philips-cd-i": {"id": 133, "name": "CD-i"},  # IGDB
    "cdtv": {"id": 129, "name": "Amiga CDTV"},
    "commodore-cdtv": {"id": 129, "name": "Amiga CDTV"},  # IGDB
    "camputers-lynx": {"id": 88, "name": "Camputers Lynx"},
    "casio-loopy": {"id": 98, "name": "Loopy"},
    "casio-pv-1000": {"id": 74, "name": "PV-1000"},
    "channel-f": {"id": 80, "name": "Channel F"},
    "fairchild-channel-f": {"id": 80, "name": "Channel F"},  # IGDB
    "colecoadam": {"id": 89, "name": "Adam"},
    "colecovision": {"id": 48, "name": "Colecovision"},
    "colour-genie": {"id": 92, "name": "EG2000 Colour Genie"},
    "c128": {"id": 66, "name": "Commodore 64"},
    "commodore-16-plus4": {"id": 99, "name": "Plus/4"},
    "c-plus-4": {"id": 99, "name": "Plus/4"},  # IGDB
    "c16": {"id": 99, "name": "Plus/4"},  # IGDB
    "c64": {"id": 66, "name": "Commodore 64"},
    "pet": {"id": 240, "name": "PET"},
    "cpet": {"id": 240, "name": "PET"},  # IGDB
    "creativision": {"id": 241, "name": "CreatiVision"},
    "dos": {"id": 135, "name": "PC Dos"},
    "dragon-3264": {"id": 91, "name": "Dragon 32/64"},
    "dragon-32-slash-64": {"id": 91, "name": "Dragon 32/64"},  # IGDB
    "dreamcast": {"id": 23, "name": "Dreamcast"},
    "dc": {"id": 23, "name": "Dreamcast"},  # IGDB
    "electron": {"id": 85, "name": "Electron"},
    "acorn-electron": {"id": 85, "name": "Electron"},  # IGDB
    "epoch-game-pocket-computer": {"id": 95, "name": "Game Pocket Computer"},
    "epoch-super-cassette-vision": {"id": 67, "name": "Super Cassette Vision"},
    "exelvision": {"id": 96, "name": "EXL 100"},
    "exidy-sorcerer": {"id": 165, "name": "Exidy"},
    "fmtowns": {"id": 253, "name": "FM Towns"},
    "fm-towns": {"id": 253, "name": "FM Towns"},  # IGDB
    "fm-7": {"id": 97, "name": "FM-7"},
    "g-and-w": {"id": 52, "name": "Game & Watch"},  # IGDB (Game & Watch)
    "gp32": {"id": 101, "name": "GP32"},
    "gameboy": {"id": 9, "name": "Game Boy"},
    "gb": {"id": 9, "name": "Game Boy"},  # IGDB
    "gameboy-advance": {"id": 12, "name": "Game Boy Advance"},
    "gba": {"id": 12, "name": "Game Boy Advance"},  # IGDB
    "gameboy-color": {"id": 10, "name": "Game Boy Color"},
    "gbc": {"id": 10, "name": "Game Boy Color"},  # IGDB
    "game-gear": {"id": 21, "name": "Game Gear"},
    "gamegear": {"id": 21, "name": "Game Gear"},  # IGDB
    "game-com": {"id": 121, "name": "Game.com"},
    "game-dot-com": {"id": 121, "name": "Game.com"},  # IGDB
    "gamecube": {"id": 13, "name": "GameCube"},
    "ngc": {"id": 13, "name": "GameCube"},  # IGDB
    "genesis": {"id": 1, "name": "Megadrive"},
    "genesis-slash-megadrive": {"id": 1, "name": "Megadrive"},
    "intellivision": {"id": 115, "name": "Intellivision"},
    "jaguar": {"id": 27, "name": "Jaguar"},
    "jupiter-ace": {"id": 126, "name": "Jupiter Ace"},
    "linux": {"id": 145, "name": "Linux"},
    "lynx": {"id": 28, "name": "Lynx"},
    "msx": {"id": 113, "name": "MSX"},
    "macintosh": {"id": 146, "name": "Mac OS"},
    "mac": {"id": 146, "name": "Mac OS"},  # IGDB
    "ngage": {"id": 30, "name": "N-Gage"},
    "nes": {"id": 3, "name": "NES"},
    "famicom": {"id": 3, "name": "NES"},
    "neo-geo": {"id": 142, "name": "Neo-Geo"},
    "neogeoaes": {"id": 142, "name": "Neo-Geo"},  # IGDB
    "neogeomvs": {"id": 68, "name": "Neo-Geo MVS"},  # IGDB
    "neo-geo-cd": {"id": 70, "name": "Neo-Geo CD"},
    "neo-geo-pocket": {"id": 25, "name": "Neo-Geo Pocket"},
    "neo-geo-pocket-color": {"id": 82, "name": "Neo-Geo Pocket Color"},
    "3ds": {"id": 17, "name": "Nintendo 3DS"},
    "n64": {"id": 14, "name": "Nintendo 64"},
    "nintendo-ds": {"id": 15, "name": "Nintendo DS"},
    "nds": {"id": 15, "name": "Nintendo DS"},  # IGDB
    "nintendo-dsi": {"id": 15, "name": "Nintendo DS"},
    "switch": {"id": 225, "name": "Switch"},
    "odyssey-2": {"id": 104, "name": "Videopac G7000"},
    "odyssey-2-slash-videopac-g7000": {"id": 104, "name": "Videopac G7000"},
    "oric": {"id": 131, "name": "Oric 1 / Atmos"},
    "pc88": {"id": 221, "name": "NEC PC-8801"},
    "pc-8800-series": {"id": 221, "name": "NEC PC-8801"},  # IGDB
    "pc98": {"id": 208, "name": "NEC PC-9801"},
    "pc-9800-series": {"id": 208, "name": "NEC PC-9801"},  # IGDB
    "pc-fx": {"id": 72, "name": "PC-FX"},
    "pico": {"id": 234, "name": "Pico-8"},
    "ps-vita": {"id": 62, "name": "PS Vita"},
    "psvita": {"id": 62, "name": "PS Vita"},  # IGDB
    "psp": {"id": 61, "name": "PSP"},
    "palmos": {"id": 219, "name": "Palm OS"},
    "palm-os": {"id": 219, "name": "Palm OS"},  # IGDB
    "philips-vg-5000": {"id": 261, "name": "Philips VG 5000"},
    "playstation": {"id": 57, "name": "Playstation"},
    "ps": {"id": 57, "name": "Playstation"},  # IGDB
    "ps2": {"id": 58, "name": "Playstation 2"},
    "ps3": {"id": 59, "name": "Playstation 3"},
    "playstation-4": {"id": 60, "name": "Playstation 4"},
    "ps4--1": {"id": 60, "name": "Playstation 4"},  # IGDB
    "playstation-5": {"id": 284, "name": "Playstation 5"},
    "ps5": {"id": 284, "name": "Playstation 5"},  # IGDB
    "pokemon-mini": {"id": 211, "name": "Pokémon mini"},
    "sam-coupe": {"id": 213, "name": "MGT SAM Coupé"},
    "sega-32x": {"id": 19, "name": "Megadrive 32X"},
    "sega32": {"id": 19, "name": "Megadrive 32X"},  # IGDB
    "sega-cd": {"id": 20, "name": "Mega-CD"},
    "segacd": {"id": 20, "name": "Mega-CD"},  # IGDB
    "sega-master-system": {"id": 2, "name": "Master System"},
    "sms": {"id": 2, "name": "Master System"},  # IGDB
    "sega-pico": {"id": 250, "name": "Sega Pico"},
    "sega-saturn": {"id": 22, "name": "Saturn"},
    "saturn": {"id": 22, "name": "Saturn"},  # IGDB
    "sg-1000": {"id": 109, "name": "SG-1000"},
    "snes": {"id": 4, "name": "Super Nintendo"},
    "sharp-x1": {"id": 220, "name": "Sharp X1"},
    "x1": {"id": 220, "name": "Sharp X1"},  # IGDB
    "sharp-x68000": {"id": 79, "name": "Sharp X68000"},
    "spectravideo": {"id": 218, "name": "Spectravideo"},
    "super-acan": {"id": 100, "name": "Super A'can"},
    "supergrafx": {"id": 105, "name": "PC Engine SuperGrafx"},
    "supervision": {"id": 207, "name": "Watara Supervision"},
    "ti-99": {"id": 205, "name": "TI-99/4A"},  # IGDB
    "trs-80-coco": {"id": 144, "name": "TRS-80 Color Computer"},
    "trs-80-color-computer": {"id": 144, "name": "TRS-80 Color Computer"},  # IGDB
    "taito-x-55": {"id": 112, "name": "Type X"},
    "thomson-mo": {"id": 141, "name": "Thomson MO/TO"},
    "thomson-mo5": {"id": 141, "name": "Thomson MO/TO"},
    "thomson-to": {"id": 141, "name": "Thomson MO/TO"},
    "turbografx-cd": {"id": 114, "name": "PC Engine CD-Rom"},
    "turbografx-16-slash-pc-engine-cd": {"id": 114, "name": "PC Engine CD-Rom"},
    "turbo-grafx": {"id": 31, "name": "PC Engine"},
    "turbografx16--1": {"id": 31, "name": "PC Engine"},  # IGDB
    "vsmile": {"id": 120, "name": "V.Smile"},
    "vic-20": {"id": 73, "name": "Vic-20"},
    "vectrex": {"id": 102, "name": "Vectrex"},
    "videopac-g7400": {"id": 104, "name": "Videopac G7000"},
    "virtual-boy": {"id": 11, "name": "Virtual Boy"},
    "virtualboy": {"id": 11, "name": "Virtual Boy"},
    "wii": {"id": 18, "name": "Wii"},
    "wii-u": {"id": 18, "name": "Wii U"},
    "wiiu": {"id": 18, "name": "Wii U"},
    "windows": {"id": 3, "name": "Windows"},
    "win": {"id": 138, "name": "PC Windows"},  # IGDB
    "win3x": {"id": 136, "name": "PC Win3.xx"},
    "wonderswan": {"id": 45, "name": "WonderSwan"},
    "wonderswan-color": {"id": 46, "name": "WonderSwan Color"},
    "xbox": {"id": 32, "name": "Xbox"},
    "xbox360": {"id": 33, "name": "Xbox 360"},
    "xbox-one": {"id": 34, "name": "Xbox One"},
    "xboxone": {"id": 34, "name": "Xbox One"},
    "z-machine": {"id": 215, "name": "Z-Machine"},
    "zx-spectrum": {"id": 76, "name": "ZX Spectrum"},
    "zx81": {"id": 77, "name": "ZX81"},
    "sinclair-zx81": {"id": 77, "name": "ZX81"},  # IGDB
}

# Reverse lookup
SS_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_SS_ID.items()}
