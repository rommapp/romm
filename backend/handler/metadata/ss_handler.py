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
    UniversalPlatformSlug,
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
        if not slug:
            return SSPlatform(ss_id=None, slug=slug)

        try:
            slug = UniversalPlatformSlug(slug)
        except ValueError:
            log.info(f"Unknown slug: {slug}")
            return SSPlatform(ss_id=None, slug=slug)

        platform = SLUG_TO_SS_PLATFORM.get(slug, None)
        if not platform:
            return SSPlatform(ss_id=None, slug=slug.value)

        return SSPlatform(
            ss_id=platform["id"],
            slug=slug.value,
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

        if not res:
            return fallback_rom

        res_id = res.get("id")
        if not res_id:
            return fallback_rom

        rom = {
            "ss_id": int(res_id),
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


SLUG_TO_SS_PLATFORM: dict[UniversalPlatformSlug, SlugToSSId] = {
    UniversalPlatformSlug._3DO: {"id": 29, "name": "3DO"},
    UniversalPlatformSlug._3DS: {"id": 17, "name": "Nintendo 3DS"},
    UniversalPlatformSlug.ACORNELECTRON: {"id": 85, "name": "Electron"},
    UniversalPlatformSlug.AMIGA: {"id": 64, "name": "Amiga"},
    UniversalPlatformSlug.AMIGACD32: {"id": 134, "name": "Amiga CD"},
    UniversalPlatformSlug.AMSTRADCPC: {"id": 60, "name": "Amstrad CPC"},
    UniversalPlatformSlug.ANDROID: {"id": 63, "name": "Android"},
    UniversalPlatformSlug.APPLE2: {"id": 86, "name": "Apple II"},
    UniversalPlatformSlug.APPLE2GS: {"id": 217, "name": "Apple IIGS"},
    UniversalPlatformSlug.ARCADIA: {"id": 94, "name": "Arcadia 2001"},
    UniversalPlatformSlug.ARDUBOY: {"id": 263, "name": "Arduboy"},
    UniversalPlatformSlug.ASTROCADE: {"id": 44, "name": "Astrocade"},
    UniversalPlatformSlug.ATARI2600: {"id": 26, "name": "Atari 2600"},
    UniversalPlatformSlug.ATARI5200: {"id": 40, "name": "Atari 5200"},
    UniversalPlatformSlug.ATARI7800: {"id": 41, "name": "Atari 7800"},
    UniversalPlatformSlug.ATARI8BIT: {"id": 43, "name": "Atari 8bit"},
    UniversalPlatformSlug.ATARIST: {"id": 42, "name": "Atari ST"},
    UniversalPlatformSlug.ATOM: {"id": 36, "name": "Atom"},
    UniversalPlatformSlug.BBCMICRO: {"id": 37, "name": "BBC Micro"},
    UniversalPlatformSlug.C128: {"id": 66, "name": "Commodore 64"},
    UniversalPlatformSlug.C16: {"id": 99, "name": "Plus/4"},
    UniversalPlatformSlug.C20: {"id": 73, "name": "Vic-20"},
    UniversalPlatformSlug.C64: {"id": 66, "name": "Commodore 64"},
    UniversalPlatformSlug.CAMPLYNX: {"id": 88, "name": "Camputers Lynx"},
    UniversalPlatformSlug.CDI: {"id": 133, "name": "CD-i"},
    UniversalPlatformSlug.CDTV: {"id": 129, "name": "Amiga CDTV"},
    UniversalPlatformSlug.CHANNELF: {"id": 80, "name": "Channel F"},
    UniversalPlatformSlug.COCO: {"id": 144, "name": "TRS-80 Color Computer"},
    UniversalPlatformSlug.COLECOADAM: {"id": 89, "name": "Adam"},
    UniversalPlatformSlug.COLECOVISION: {"id": 48, "name": "Colecovision"},
    UniversalPlatformSlug.COLOURGENIE: {"id": 92, "name": "EG2000 Colour Genie"},
    UniversalPlatformSlug.CPET: {"id": 240, "name": "PET"},
    UniversalPlatformSlug.CPLUS4: {"id": 99, "name": "Commodore Plus/4"},
    UniversalPlatformSlug.CREATIVISION: {"id": 241, "name": "CreatiVision"},
    UniversalPlatformSlug.DOS: {"id": 135, "name": "PC Dos"},
    UniversalPlatformSlug.DRAGON32: {"id": 91, "name": "Dragon 32/64"},
    UniversalPlatformSlug.DREAMCAST: {"id": 23, "name": "Dreamcast"},
    UniversalPlatformSlug.DSI: {"id": 15, "name": "Nintendo DSi"},
    UniversalPlatformSlug.EGPC: {"id": 95, "name": "Game Pocket Computer"},
    UniversalPlatformSlug.EXELVISION: {"id": 96, "name": "EXL 100"},
    UniversalPlatformSlug.EXIDYSORCERER: {"id": 165, "name": "Exidy"},
    UniversalPlatformSlug.FDS: {"id": 106, "name": "Family Computer Disk System"},
    UniversalPlatformSlug.FM7: {"id": 97, "name": "FM-7"},
    UniversalPlatformSlug.FMTOWNS: {"id": 253, "name": "FM Towns"},
    UniversalPlatformSlug.GAMEANDWATCH: {"id": 52, "name": "Game & Watch"},
    UniversalPlatformSlug.GAMECOM: {"id": 121, "name": "Game.com"},
    UniversalPlatformSlug.GAMEGEAR: {"id": 21, "name": "Game Gear"},
    UniversalPlatformSlug.GB: {"id": 9, "name": "Game Boy"},
    UniversalPlatformSlug.GBA: {"id": 12, "name": "Game Boy Advance"},
    UniversalPlatformSlug.GBC: {"id": 10, "name": "Game Boy Color"},
    UniversalPlatformSlug.GP32: {"id": 101, "name": "GP32"},
    UniversalPlatformSlug.INTELLIVISION: {"id": 115, "name": "Intellivision"},
    UniversalPlatformSlug.JAGUAR: {"id": 27, "name": "Jaguar"},
    UniversalPlatformSlug.JUPITERACE: {"id": 126, "name": "Jupiter Ace"},
    UniversalPlatformSlug.LINUX: {"id": 145, "name": "Linux"},
    UniversalPlatformSlug.LOOPY: {"id": 98, "name": "Loopy"},
    UniversalPlatformSlug.LYNX: {"id": 28, "name": "Lynx"},
    UniversalPlatformSlug.MAC: {"id": 146, "name": "Mac OS"},
    UniversalPlatformSlug.MACINTOSH: {"id": 146, "name": "Mac OS"},
    UniversalPlatformSlug.MEGADRIVE: {"id": 1, "name": "Megadrive"},
    UniversalPlatformSlug.MSX: {"id": 113, "name": "MSX"},
    UniversalPlatformSlug.N64: {"id": 14, "name": "Nintendo 64"},
    UniversalPlatformSlug.NDS: {"id": 15, "name": "Nintendo DS"},
    UniversalPlatformSlug.NEOGEOAES: {"id": 142, "name": "Neo-Geo"},
    UniversalPlatformSlug.NEOGEOCD: {"id": 70, "name": "Neo-Geo CD"},
    UniversalPlatformSlug.NEOGEOMVS: {"id": 68, "name": "Neo-Geo MVS"},
    UniversalPlatformSlug.NES: {"id": 3, "name": "NES"},
    UniversalPlatformSlug.NGAGE: {"id": 30, "name": "N-Gage"},
    UniversalPlatformSlug.NGC: {"id": 13, "name": "GameCube"},
    UniversalPlatformSlug.NGP: {"id": 25, "name": "Neo-Geo Pocket"},
    UniversalPlatformSlug.NGPC: {"id": 82, "name": "Neo-Geo Pocket Color"},
    UniversalPlatformSlug.ODYSSEY2: {"id": 104, "name": "Videopac G7000"},
    UniversalPlatformSlug.ORIC: {"id": 131, "name": "Oric 1 / Atmos"},
    UniversalPlatformSlug.PALMOS: {"id": 219, "name": "Palm OS"},
    UniversalPlatformSlug.PC88: {"id": 221, "name": "NEC PC-8801"},
    UniversalPlatformSlug.PC98: {"id": 208, "name": "NEC PC-9801"},
    UniversalPlatformSlug.PCENGINE: {"id": 31, "name": "PC Engine"},
    UniversalPlatformSlug.PCENGINECD: {"id": 114, "name": "PC Engine CD-Rom"},
    UniversalPlatformSlug.PCFX: {"id": 72, "name": "PC-FX"},
    UniversalPlatformSlug.PET: {"id": 240, "name": "PET"},
    UniversalPlatformSlug.PICO: {"id": 250, "name": "Sega Pico"},
    UniversalPlatformSlug.PICO8: {"id": 234, "name": "Pico-8"},
    UniversalPlatformSlug.POKEMINI: {"id": 211, "name": "Pokémon mini"},
    UniversalPlatformSlug.PS2: {"id": 58, "name": "Playstation 2"},
    UniversalPlatformSlug.PS3: {"id": 59, "name": "Playstation 3"},
    UniversalPlatformSlug.PS4: {"id": 60, "name": "Playstation 4"},
    UniversalPlatformSlug.PS5: {"id": 284, "name": "Playstation 5"},
    UniversalPlatformSlug.PSP: {"id": 61, "name": "PSP"},
    UniversalPlatformSlug.PSVITA: {"id": 62, "name": "PS Vita"},
    UniversalPlatformSlug.PSX: {"id": 57, "name": "Playstation"},
    UniversalPlatformSlug.PV1000: {"id": 74, "name": "PV-1000"},
    UniversalPlatformSlug.SAMCOUPE: {"id": 213, "name": "MGT SAM Coupé"},
    UniversalPlatformSlug.SATURN: {"id": 22, "name": "Saturn"},
    UniversalPlatformSlug.SCV: {"id": 67, "name": "Super Cassette Vision"},
    UniversalPlatformSlug.SEGA32X: {"id": 19, "name": "Megadrive 32X"},
    UniversalPlatformSlug.SEGACD: {"id": 20, "name": "Mega-CD"},
    UniversalPlatformSlug.SG1000: {"id": 109, "name": "SG-1000"},
    UniversalPlatformSlug.SMS: {"id": 2, "name": "Master System"},
    UniversalPlatformSlug.SNES: {"id": 4, "name": "Super Nintendo"},
    UniversalPlatformSlug.SPECTRAVIDEO: {"id": 218, "name": "Spectravideo"},
    UniversalPlatformSlug.SUPERACAN: {"id": 100, "name": "Super A'can"},
    UniversalPlatformSlug.SUPERGRAFX: {"id": 105, "name": "PC Engine SuperGrafx"},
    UniversalPlatformSlug.SUPERVISION: {"id": 207, "name": "Watara Supervision"},
    UniversalPlatformSlug.SWITCH: {"id": 225, "name": "Switch"},
    UniversalPlatformSlug.THOMSONMO: {"id": 141, "name": "Thomson MO/TO"},
    UniversalPlatformSlug.TI99: {"id": 205, "name": "TI-99/4A"},
    UniversalPlatformSlug.VECTREX: {"id": 102, "name": "Vectrex"},
    UniversalPlatformSlug.VG5000: {"id": 261, "name": "Philips VG 5000"},
    UniversalPlatformSlug.VIDEOPACPLUS: {"id": 104, "name": "Videopac G7000"},
    UniversalPlatformSlug.VIRTUALBOY: {"id": 11, "name": "Virtual Boy"},
    UniversalPlatformSlug.VSMILE: {"id": 120, "name": "V.Smile"},
    UniversalPlatformSlug.WII: {"id": 18, "name": "Wii"},
    UniversalPlatformSlug.WIIU: {"id": 18, "name": "Wii U"},
    UniversalPlatformSlug.WIN: {"id": 138, "name": "PC Windows"},
    UniversalPlatformSlug.WIN3X: {"id": 136, "name": "PC Win3.xx"},
    UniversalPlatformSlug.WINDOWS: {"id": 3, "name": "Windows"},
    UniversalPlatformSlug.WSWAN: {"id": 45, "name": "WonderSwan"},
    UniversalPlatformSlug.WSWANC: {"id": 46, "name": "WonderSwan Color"},
    UniversalPlatformSlug.X1: {"id": 220, "name": "Sharp X1"},
    UniversalPlatformSlug.X55: {"id": 112, "name": "Type X"},
    UniversalPlatformSlug.X68000: {"id": 79, "name": "Sharp X68000"},
    UniversalPlatformSlug.XBOX: {"id": 32, "name": "Xbox"},
    UniversalPlatformSlug.XBOX360: {"id": 33, "name": "Xbox 360"},
    UniversalPlatformSlug.XBOXONE: {"id": 34, "name": "Xbox One"},
    UniversalPlatformSlug.ZMACHINE: {"id": 215, "name": "Z-Machine"},
    UniversalPlatformSlug.ZX81: {"id": 77, "name": "ZX81"},
    UniversalPlatformSlug.ZXS: {"id": 76, "name": "ZX Spectrum"},
}

SS_PLATFORM_SLUGS = SLUG_TO_SS_PLATFORM.keys()
# Reverse lookup
SS_ID_TO_SS_PLATFORM = {v["id"]: k for k, v in SLUG_TO_SS_PLATFORM.items()}
