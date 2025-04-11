import asyncio
import http
import json
import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import httpx
import pydash
import yarl
from config import MOBYGAMES_API_KEY
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

# Used to display the Mobygames API status in the frontend
MOBY_API_ENABLED: Final = bool(MOBYGAMES_API_KEY)

PS1_MOBY_ID: Final = 6
PS2_MOBY_ID: Final = 7
PSP_MOBY_ID: Final = 46
SWITCH_MOBY_ID: Final = 203
ARCADE_MOBY_IDS: Final = [143, 36]


class MobyGamesPlatform(TypedDict):
    slug: str
    moby_id: int | None
    name: NotRequired[str]


class MobyMetadataPlatform(TypedDict):
    moby_id: int
    name: str


class MobyMetadata(TypedDict):
    moby_score: str
    genres: list[str]
    alternate_titles: list[str]
    platforms: list[MobyMetadataPlatform]


class MobyGamesRom(TypedDict):
    moby_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    moby_metadata: NotRequired[MobyMetadata]


def extract_metadata_from_moby_rom(rom: dict) -> MobyMetadata:
    return MobyMetadata(
        {
            "moby_score": str(rom.get("moby_score", "")),
            "genres": rom.get("genres.genre_name", []),
            "alternate_titles": rom.get("alternate_titles.title", []),
            "platforms": [
                {
                    "moby_id": p["platform_id"],
                    "name": p["platform_name"],
                }
                for p in rom.get("platforms", [])
            ],
        }
    )


class MobyGamesHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.mobygames.com/v1"
        self.platform_endpoint = f"{self.BASE_URL}/platforms"
        self.games_endpoint = f"{self.BASE_URL}/games"

    async def _request(self, url: str, timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = yarl.URL(url).update_query(api_key=MOBYGAMES_API_KEY)
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
            return res.json()
        except httpx.NetworkError as exc:
            log.critical("Connection error: can't connect to Mobygames", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Mobygames, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == http.HTTPStatus.UNAUTHORIZED:
                # Sometimes Mobygames returns 401 even with a valid API key
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
            return res.json()
        except (
            httpx.HTTPStatusError,
            httpx.TimeoutException,
            json.decoder.JSONDecodeError,
        ) as exc:
            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code == http.HTTPStatus.UNAUTHORIZED
            ):
                # Sometimes Mobygames returns 401 even with a valid API key
                return {}

            # Log the error and return an empty dict if the request fails with a different code
            log.error(exc)
            return {}

    async def _search_rom(self, search_term: str, platform_moby_id: int) -> dict | None:
        if not platform_moby_id:
            return None

        search_term = uc(search_term)
        url = yarl.URL(self.games_endpoint).with_query(
            platform=[platform_moby_id],
            title=quote(search_term, safe="/ "),
        )
        roms = (await self._request(str(url))).get("games", [])

        exact_matches = [
            rom
            for rom in roms
            if (
                rom["title"].lower() == search_term.lower()
                or (
                    self._normalize_exact_match(rom["title"])
                    == self._normalize_exact_match(search_term)
                )
            )
        ]

        return pydash.get(exact_matches or roms, "[0]", None)

    def get_platform(self, slug: str) -> MobyGamesPlatform:
        if not slug:
            return MobyGamesPlatform(moby_id=None, slug="")

        try:
            slug = UniversalPlatformSlug(slug)
        except ValueError:
            log.info(f"Unknown slug: {slug}")
            return MobyGamesPlatform(moby_id=None, slug="")

        platform = SLUG_TO_MOBY_PLATFORM.get(slug, None)
        if not platform:
            return MobyGamesPlatform(moby_id=None, slug=slug.value)

        return MobyGamesPlatform(
            moby_id=platform["id"],
            slug=slug.value,
            name=platform["name"],
        )

    async def get_rom(self, fs_name: str, platform_moby_id: int) -> MobyGamesRom:
        from handler.filesystem import fs_rom_handler

        if not MOBY_API_ENABLED:
            return MobyGamesRom(moby_id=None)

        if not platform_moby_id:
            return MobyGamesRom(moby_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = MobyGamesRom(moby_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(fs_name)
        if platform_moby_id == PS2_MOBY_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(fs_name, re.IGNORECASE)
        if platform_moby_id == PS1_MOBY_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        if platform_moby_id == PS2_MOBY_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        if platform_moby_id == PSP_MOBY_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        # Support for switch titleID filename format
        match = SWITCH_TITLEDB_REGEX.search(fs_name)
        if platform_moby_id == SWITCH_MOBY_ID and match:
            search_term, index_entry = await self._switch_titledb_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = MobyGamesRom(
                    moby_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for switch productID filename format
        match = SWITCH_PRODUCT_ID_REGEX.search(fs_name)
        if platform_moby_id == SWITCH_MOBY_ID and match:
            search_term, index_entry = await self._switch_productid_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = MobyGamesRom(
                    moby_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for MAME arcade filename format
        if platform_moby_id in ARCADE_MOBY_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)
        res = await self._search_rom(search_term, platform_moby_id)

        # Split the search term since mobygames search doesn't support special caracters
        if not res and ":" in search_term:
            for term in search_term.split(":")[::-1]:
                res = await self._search_rom(term, platform_moby_id)
                if res:
                    break

        # Some MAME games have two titles split by a slash
        if not res and "/" in search_term:
            for term in search_term.split("/"):
                res = await self._search_rom(term.strip(), platform_moby_id)
                if res:
                    break

        if not res:
            return fallback_rom

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "moby_slug": res["moby_url"].split("/")[-1],
            "summary": res.get("description", ""),
            "url_cover": pydash.get(res, "sample_cover.image", ""),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return MobyGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, moby_id: int) -> MobyGamesRom:
        if not MOBY_API_ENABLED:
            return MobyGamesRom(moby_id=None)

        url = yarl.URL(self.games_endpoint).with_query(id=moby_id)
        roms = (await self._request(str(url))).get("games", [])
        res = pydash.get(roms, "[0]", None)

        if not res:
            return MobyGamesRom(moby_id=None)

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "moby_slug": res["moby_url"].split("/")[-1],
            "summary": res.get("description", None),
            "url_cover": pydash.get(res, "sample_cover.image", None),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return MobyGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_matched_rom_by_id(self, moby_id: int) -> MobyGamesRom | None:
        if not MOBY_API_ENABLED:
            return None

        rom = await self.get_rom_by_id(moby_id)
        return rom if rom["moby_id"] else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_moby_id: int | None
    ) -> list[MobyGamesRom]:
        if not MOBY_API_ENABLED:
            return []

        if not platform_moby_id:
            return []

        search_term = uc(search_term)
        url = yarl.URL(self.games_endpoint).with_query(
            platform=[platform_moby_id], title=quote(search_term, safe="/ ")
        )
        matched_roms = (await self._request(str(url))).get("games", [])

        return [
            MobyGamesRom(
                {  # type: ignore[misc]
                    k: v
                    for k, v in {
                        "moby_id": rom["game_id"],
                        "name": rom["title"],
                        "moby_slug": rom["moby_url"].split("/")[-1],
                        "summary": rom.get("description", ""),
                        "url_cover": pydash.get(rom, "sample_cover.image", ""),
                        "url_screenshots": [
                            s["image"] for s in rom.get("sample_screenshots", [])
                        ],
                        "moby_metadata": extract_metadata_from_moby_rom(rom),
                    }.items()
                    if v
                }
            )
            for rom in matched_roms
        ]


class SlugToMobyPlatform(TypedDict):
    id: int
    name: str
    moby_slug: str


SLUG_TO_MOBY_PLATFORM: dict[UniversalPlatformSlug, SlugToMobyPlatform] = {
    UniversalPlatformSlug._1292APVS: {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
        "moby_slug": "1292-advanced-programmable-video-system",
    },
    UniversalPlatformSlug._3DO: {"id": 35, "name": "3DO", "moby_slug": "3do"},
    UniversalPlatformSlug._3DS: {"id": 101, "name": "Nintendo 3DS", "moby_slug": "3ds"},
    UniversalPlatformSlug.ABC80: {"id": 318, "name": "ABC 80", "moby_slug": "abc-80"},
    UniversalPlatformSlug.ACORNARCHIMEDES: {
        "id": 117,
        "name": "Acorn Archimedes",
        "moby_slug": "acornarchimedes",
    },
    UniversalPlatformSlug.ACORNELECTRON: {
        "id": 93,
        "name": "Electron",
        "moby_slug": "electron",
    },
    UniversalPlatformSlug.ADVISION: {
        "id": 210,
        "name": "Adventure Vision",
        "moby_slug": "adventure-vision",
    },
    UniversalPlatformSlug.AIRCONSOLE: {
        "id": 305,
        "name": "AirConsole",
        "moby_slug": "airconsole",
    },
    UniversalPlatformSlug.ALICE3290: {
        "id": 194,
        "name": "Alice 32/90",
        "moby_slug": "alice-3290",
    },
    UniversalPlatformSlug.ALTAIR680: {
        "id": 265,
        "name": "Altair 680",
        "moby_slug": "altair-680",
    },
    UniversalPlatformSlug.ALTAIR8800: {
        "id": 222,
        "name": "Altair 8800",
        "moby_slug": "altair-8800",
    },
    UniversalPlatformSlug.AMAZONALEXA: {
        "id": 237,
        "name": "Amazon Alexa",
        "moby_slug": "amazonalexa",
    },
    UniversalPlatformSlug.AMAZONFIRETV: {
        "id": 159,
        "name": "Fire TV",
        "moby_slug": "amazonfiretv",
    },
    UniversalPlatformSlug.AMIGA: {"id": 19, "name": "Amiga", "moby_slug": "amiga"},
    UniversalPlatformSlug.AMIGACD32: {
        "id": 56,
        "name": "Amiga CD32",
        "moby_slug": "amiga-cd32",
    },
    UniversalPlatformSlug.AMSTRADCPC: {
        "id": 60,
        "name": "Amstrad CPC",
        "moby_slug": "amstradcpc",
    },
    UniversalPlatformSlug.AMSTRADPCW: {
        "id": 136,
        "name": "Amstrad PCW",
        "moby_slug": "amstrad-pcw",
    },
    UniversalPlatformSlug.ANDROID: {
        "id": 91,
        "name": "Android",
        "moby_slug": "android",
    },
    UniversalPlatformSlug.ANTSTREAM: {
        "id": 286,
        "name": "Antstream",
        "moby_slug": "antstream",
    },
    UniversalPlatformSlug.APF: {
        "id": 213,
        "name": "APF MP1000/Imagination Machine",
        "moby_slug": "apf",
    },
    UniversalPlatformSlug.APPLE: {"id": 245, "name": "Apple I", "moby_slug": "apple-i"},
    UniversalPlatformSlug.APPLE2: {"id": 31, "name": "Apple II", "moby_slug": "apple2"},
    UniversalPlatformSlug.APPLE2GS: {
        "id": 51,
        "name": "Apple IIGS",
        "moby_slug": "apple2gs",
    },
    UniversalPlatformSlug.AQUARIUS: {
        "id": 135,
        "name": "Mattel Aquarius",
        "moby_slug": "mattel-aquarius",
    },
    UniversalPlatformSlug.ARCADE: {"id": 143, "name": "Arcade", "moby_slug": "arcade"},
    UniversalPlatformSlug.ARCADIA: {
        "id": 162,
        "name": "Arcadia 2001",
        "moby_slug": "arcadia-2001",
    },
    UniversalPlatformSlug.ARDUBOY: {
        "id": 215,
        "name": "Arduboy",
        "moby_slug": "arduboy",
    },
    UniversalPlatformSlug.ASTRAL2000: {
        "id": 241,
        "name": "Astral 2000",
        "moby_slug": "astral-2000",
    },
    UniversalPlatformSlug.ASTROCADE: {
        "id": 160,
        "name": "Bally Astrocade",
        "moby_slug": "bally-astrocade",
    },
    UniversalPlatformSlug.ATARI2600: {
        "id": 28,
        "name": "Atari 2600",
        "moby_slug": "atari-2600",
    },
    UniversalPlatformSlug.ATARI5200: {
        "id": 33,
        "name": "Atari 5200",
        "moby_slug": "atari-5200",
    },
    UniversalPlatformSlug.ATARI7800: {
        "id": 34,
        "name": "Atari 7800",
        "moby_slug": "atari-7800",
    },
    UniversalPlatformSlug.ATARI8BIT: {
        "id": 39,
        "name": "Atari 8-bit",
        "moby_slug": "atari-8-bit",
    },
    UniversalPlatformSlug.ATARIST: {
        "id": 24,
        "name": "Atari ST",
        "moby_slug": "atari-st",
    },
    UniversalPlatformSlug.ATARIVCS: {
        "id": 319,
        "name": "Atari VCS",
        "moby_slug": "atari-vcs",
    },
    UniversalPlatformSlug.ATOM: {"id": 129, "name": "Atom", "moby_slug": "atom"},
    UniversalPlatformSlug.BADA: {"id": 99, "name": "bada", "moby_slug": "bada"},
    UniversalPlatformSlug.BBCMICRO: {
        "id": 92,
        "name": "BBC Micro",
        "moby_slug": "bbc-micro",
    },
    UniversalPlatformSlug.BEOS: {"id": 165, "name": "BeOS", "moby_slug": "beos"},
    UniversalPlatformSlug.BLACKBERRY: {
        "id": 90,
        "name": "BlackBerry",
        "moby_slug": "blackberry",
    },
    UniversalPlatformSlug.BLACKNUT: {
        "id": 290,
        "name": "Blacknut",
        "moby_slug": "blacknut",
    },
    UniversalPlatformSlug.BLURAY: {
        "id": 168,
        "name": "Blu-ray Player",
        "moby_slug": "blu-ray-disc-player",
    },
    UniversalPlatformSlug.BREW: {"id": 63, "name": "BREW", "moby_slug": "brew"},
    UniversalPlatformSlug.BROWSER: {
        "id": 84,
        "name": "Browser",
        "moby_slug": "browser",
    },
    UniversalPlatformSlug.BUBBLE: {"id": 231, "name": "Bubble", "moby_slug": "bubble"},
    UniversalPlatformSlug.C128: {
        "id": 61,
        "name": "Commodore 128",
        "moby_slug": "c128",
    },
    UniversalPlatformSlug.C16: {"id": 115, "name": "Commodore 16", "moby_slug": "c16"},
    UniversalPlatformSlug.C16PLUS4: {
        "id": 115,
        "name": "Commodore 16, Plus/4",
        "moby_slug": "commodore-16-plus4",
    },
    UniversalPlatformSlug.C20: {"id": 43, "name": "VIC-20", "moby_slug": "vic-20"},
    UniversalPlatformSlug.C64: {"id": 27, "name": "Commodore 64", "moby_slug": "c64"},
    UniversalPlatformSlug.CAMPLYNX: {
        "id": 154,
        "name": "Camputers Lynx",
        "moby_slug": "camputers-lynx",
    },
    UniversalPlatformSlug.CASIOCALC: {
        "id": 306,
        "name": "Casio Programmable Calculator",
        "moby_slug": "casio-programmable-calculator",
    },
    UniversalPlatformSlug.CDI: {"id": 73, "name": "CD-i", "moby_slug": "cd-i"},
    UniversalPlatformSlug.CDTV: {"id": 83, "name": "CDTV", "moby_slug": "cdtv"},
    UniversalPlatformSlug.CHAMPION2711: {
        "id": 298,
        "name": "Champion 2711",
        "moby_slug": "champion-2711",
    },
    UniversalPlatformSlug.CHANNELF: {
        "id": 76,
        "name": "Channel F",
        "moby_slug": "channel-f",
    },
    UniversalPlatformSlug.CLICKSTART: {
        "id": 188,
        "name": "ClickStart",
        "moby_slug": "clickstart",
    },
    UniversalPlatformSlug.COCO: {
        "id": 62,
        "name": "TRS-80 Color Computer",
        "moby_slug": "trs-80-coco",
    },
    UniversalPlatformSlug.COLECOADAM: {
        "id": 156,
        "name": "Coleco Adam",
        "moby_slug": "colecoadam",
    },
    UniversalPlatformSlug.COLECOVISION: {
        "id": 29,
        "name": "ColecoVision",
        "moby_slug": "colecovision",
    },
    UniversalPlatformSlug.COLOURGENIE: {
        "id": 197,
        "name": "Colour Genie",
        "moby_slug": "colour-genie",
    },
    UniversalPlatformSlug.COMPUCOLOR: {
        "id": 243,
        "name": "Compucolor I",
        "moby_slug": "compucolor-i",
    },
    UniversalPlatformSlug.COMPUCOLOR2: {
        "id": 198,
        "name": "Compucolor II",
        "moby_slug": "compucolor-ii",
    },
    UniversalPlatformSlug.COMPUCORPCALC: {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
        "moby_slug": "compucorp-programmable-calculator",
    },
    UniversalPlatformSlug.COSMAC: {
        "id": 216,
        "name": "COSMAC",
        "moby_slug": "fred-cosmac",
    },
    UniversalPlatformSlug.CPET: {
        "id": 77,
        "name": "Commodore PET/CBM",
        "moby_slug": "cpet",
    },
    UniversalPlatformSlug.CPLUS4: {
        "id": 115,
        "name": "Commodore Plus/4",
        "moby_slug": "c-plus-4",
    },
    UniversalPlatformSlug.CPM: {"id": 261, "name": "CP/M", "moby_slug": "cpm"},
    UniversalPlatformSlug.CREATIVISION: {
        "id": 212,
        "name": "CreatiVision",
        "moby_slug": "creativision",
    },
    UniversalPlatformSlug.CYBERVISION: {
        "id": 301,
        "name": "Cybervision",
        "moby_slug": "cybervision",
    },
    UniversalPlatformSlug.DANGEROS: {
        "id": 285,
        "name": "Danger OS",
        "moby_slug": "danger-os",
    },
    UniversalPlatformSlug.DEDICATEDCONSOLE: {
        "id": 204,
        "name": "Dedicated console",
        "moby_slug": "dedicated-console",
    },
    UniversalPlatformSlug.DEDICATEDHANDHELD: {
        "id": 205,
        "name": "Dedicated handheld",
        "moby_slug": "dedicated-handheld",
    },
    UniversalPlatformSlug.DIDJ: {"id": 184, "name": "Didj", "moby_slug": "didj"},
    UniversalPlatformSlug.DIGIBLAST: {
        "id": 187,
        "name": "digiBlast",
        "moby_slug": "digiblast",
    },
    UniversalPlatformSlug.DOJA: {"id": 72, "name": "DoJa", "moby_slug": "doja"},
    UniversalPlatformSlug.DOS: {"id": 2, "name": "DOS", "moby_slug": "dos"},
    UniversalPlatformSlug.DRAGON32: {
        "id": 79,
        "name": "Dragon 32/64",
        "moby_slug": "dragon-3264",
    },
    UniversalPlatformSlug.DREAMCAST: {
        "id": 8,
        "name": "Dreamcast",
        "moby_slug": "dreamcast",
    },
    UniversalPlatformSlug.DSI: {
        "id": 87,
        "name": "Nintendo DSi",
        "moby_slug": "nintendo-dsi",
    },
    UniversalPlatformSlug.DVD: {
        "id": 166,
        "name": "DVD Player",
        "moby_slug": "dvd-player",
    },
    UniversalPlatformSlug.ECV: {
        "id": 137,
        "name": "Epoch Cassette Vision",
        "moby_slug": "epoch-cassette-vision",
    },
    UniversalPlatformSlug.EGPC: {
        "id": 139,
        "name": "Epoch Game Pocket Computer",
        "moby_slug": "epoch-game-pocket-computer",
    },
    UniversalPlatformSlug.ENTERPRISE: {
        "id": 161,
        "name": "Enterprise",
        "moby_slug": "enterprise",
    },
    UniversalPlatformSlug.EVERCADE: {
        "id": 284,
        "name": "Evercade",
        "moby_slug": "evercade",
    },
    UniversalPlatformSlug.EXELVISION: {
        "id": 195,
        "name": "Exelvision",
        "moby_slug": "exelvision",
    },
    UniversalPlatformSlug.EXEN: {"id": 70, "name": "ExEn", "moby_slug": "exen"},
    UniversalPlatformSlug.EXIDYSORCERER: {
        "id": 176,
        "name": "Exidy Sorcerer",
        "moby_slug": "exidy-sorcerer",
    },
    UniversalPlatformSlug.FAMICOM: {"id": 22, "name": "NES", "moby_slug": "famicom"},
    UniversalPlatformSlug.FIREOS: {
        "id": 159,
        "name": "Fire OS",
        "moby_slug": "fire-os",
    },
    UniversalPlatformSlug.FM7: {"id": 126, "name": "FM-7", "moby_slug": "fm-7"},
    UniversalPlatformSlug.FMTOWNS: {
        "id": 102,
        "name": "FM Towns",
        "moby_slug": "fmtowns",
    },
    UniversalPlatformSlug.FREEBOX: {
        "id": 268,
        "name": "Freebox",
        "moby_slug": "freebox",
    },
    UniversalPlatformSlug.GALAKSIJA: {
        "id": 236,
        "name": "Galaksija",
        "moby_slug": "galaksija",
    },
    UniversalPlatformSlug.GAMEANDWATCH: {
        "id": 205,
        "name": "Dedicated handheld",
        "moby_slug": "g-and-w",
    },
    UniversalPlatformSlug.GAMECOM: {
        "id": 50,
        "name": "Game.Com",
        "moby_slug": "game-com",
    },
    UniversalPlatformSlug.GAMEGEAR: {
        "id": 25,
        "name": "Game Gear",
        "moby_slug": "game-gear",
    },
    UniversalPlatformSlug.GAMESTICK: {
        "id": 155,
        "name": "GameStick",
        "moby_slug": "gamestick",
    },
    UniversalPlatformSlug.GAMEWAVE: {
        "id": 104,
        "name": "Game Wave",
        "moby_slug": "game-wave",
    },
    UniversalPlatformSlug.GB: {"id": 10, "name": "Game Boy", "moby_slug": "gameboy"},
    UniversalPlatformSlug.GBA: {
        "id": 12,
        "name": "Game Boy Advance",
        "moby_slug": "gameboy-advance",
    },
    UniversalPlatformSlug.GBC: {
        "id": 11,
        "name": "Game Boy Color",
        "moby_slug": "gameboy-color",
    },
    UniversalPlatformSlug.GCLUSTER: {
        "id": 302,
        "name": "G-cluster",
        "moby_slug": "g-cluster",
    },
    UniversalPlatformSlug.GIMINI: {"id": 251, "name": "GIMINI", "moby_slug": "gimini"},
    UniversalPlatformSlug.GIZMONDO: {
        "id": 55,
        "name": "Gizmondo",
        "moby_slug": "gizmondo",
    },
    UniversalPlatformSlug.GLOUD: {"id": 292, "name": "Gloud", "moby_slug": "gloud"},
    UniversalPlatformSlug.GLULX: {"id": 172, "name": "Glulx", "moby_slug": "glulx"},
    UniversalPlatformSlug.GNEX: {"id": 258, "name": "GNEX", "moby_slug": "gnex"},
    UniversalPlatformSlug.GP2X: {"id": 122, "name": "GP2X", "moby_slug": "gp2x"},
    UniversalPlatformSlug.GP2XWIZ: {
        "id": 123,
        "name": "GP2X Wiz",
        "moby_slug": "gp2x-wiz",
    },
    UniversalPlatformSlug.GP32: {"id": 108, "name": "GP32", "moby_slug": "gp32"},
    UniversalPlatformSlug.GVM: {"id": 257, "name": "GVM", "moby_slug": "gvm"},
    UniversalPlatformSlug.HDDVD: {
        "id": 167,
        "name": "HD DVD Player",
        "moby_slug": "hd-dvd-player",
    },
    UniversalPlatformSlug.HEATHKITH11: {
        "id": 248,
        "name": "Heathkit H11",
        "moby_slug": "heathkit-h11",
    },
    UniversalPlatformSlug.HEATHZENITH: {
        "id": 262,
        "name": "Heath/Zenith H8/H89",
        "moby_slug": "heathzenith",
    },
    UniversalPlatformSlug.HITACHIS1: {
        "id": 274,
        "name": "Hitachi S1",
        "moby_slug": "hitachi-s1",
    },
    UniversalPlatformSlug.HP9800: {
        "id": 219,
        "name": "HP 9800",
        "moby_slug": "hp-9800",
    },
    UniversalPlatformSlug.HPCALC: {
        "id": 234,
        "name": "HP Programmable Calculator",
        "moby_slug": "hp-programmable-calculator",
    },
    UniversalPlatformSlug.HUGO: {"id": 170, "name": "Hugo", "moby_slug": "hugo"},
    UniversalPlatformSlug.HYPERSCAN: {
        "id": 192,
        "name": "HyperScan",
        "moby_slug": "hyperscan",
    },
    UniversalPlatformSlug.IBM5100: {
        "id": 250,
        "name": "IBM 5100",
        "moby_slug": "ibm-5100",
    },
    UniversalPlatformSlug.IDEALCOMPUTER: {
        "id": 252,
        "name": "Ideal-Computer",
        "moby_slug": "ideal-computer",
    },
    UniversalPlatformSlug.IIRCADE: {
        "id": 314,
        "name": "iiRcade",
        "moby_slug": "iircade",
    },
    UniversalPlatformSlug.INTEL8008: {
        "id": 224,
        "name": "Intel 8008",
        "moby_slug": "intel-8008",
    },
    UniversalPlatformSlug.INTEL8080: {
        "id": 225,
        "name": "Intel 8080",
        "moby_slug": "intel-8080",
    },
    UniversalPlatformSlug.INTEL8086: {
        "id": 317,
        "name": "Intel 8086 / 8088",
        "moby_slug": "intel-8086",
    },
    UniversalPlatformSlug.INTELLIVISION: {
        "id": 30,
        "name": "Intellivision",
        "moby_slug": "intellivision",
    },
    UniversalPlatformSlug.INTERACTM1: {
        "id": 295,
        "name": "Interact Model One",
        "moby_slug": "interact-model-one",
    },
    UniversalPlatformSlug.INTERTONV2000: {
        "id": 221,
        "name": "Interton Video 2000",
        "moby_slug": "interton-video-2000",
    },
    UniversalPlatformSlug.IOS: {"id": 86, "name": "iOS", "moby_slug": "ios"},
    UniversalPlatformSlug.IPAD: {"id": 96, "name": "iPad", "moby_slug": "ipad"},
    UniversalPlatformSlug.IPHONE: {"id": 86, "name": "iPhone", "moby_slug": "iphone"},
    UniversalPlatformSlug.IPOD: {
        "id": 80,
        "name": "iPod Classic",
        "moby_slug": "ipod-classic",
    },
    UniversalPlatformSlug.J2ME: {"id": 64, "name": "J2ME", "moby_slug": "j2me"},
    UniversalPlatformSlug.JAGUAR: {"id": 17, "name": "Jaguar", "moby_slug": "jaguar"},
    UniversalPlatformSlug.JOLT: {"id": 247, "name": "Jolt", "moby_slug": "jolt"},
    UniversalPlatformSlug.JUPITERACE: {
        "id": 153,
        "name": "Jupiter Ace",
        "moby_slug": "jupiter-ace",
    },
    UniversalPlatformSlug.KAIOS: {"id": 313, "name": "KaiOS", "moby_slug": "kaios"},
    UniversalPlatformSlug.KIM1: {"id": 226, "name": "KIM-1", "moby_slug": "kim-1"},
    UniversalPlatformSlug.KINDLE: {
        "id": 145,
        "name": "Kindle Classic",
        "moby_slug": "kindle",
    },
    UniversalPlatformSlug.LASER200: {
        "id": 264,
        "name": "Laser 200",
        "moby_slug": "laser200",
    },
    UniversalPlatformSlug.LASERACTIVE: {
        "id": 163,
        "name": "LaserActive",
        "moby_slug": "laseractive",
    },
    UniversalPlatformSlug.LEAPSTER: {
        "id": 183,
        "name": "Leapster",
        "moby_slug": "leapster",
    },
    UniversalPlatformSlug.LEAPSTEREXPLORER: {
        "id": 185,
        "name": "LeapFrog Explorer",
        "moby_slug": "leapfrog-explorer",
    },
    UniversalPlatformSlug.LEAPTV: {"id": 186, "name": "LeapTV", "moby_slug": "leaptv"},
    UniversalPlatformSlug.LINUX: {"id": 1, "name": "Linux", "moby_slug": "linux"},
    UniversalPlatformSlug.LOOPY: {
        "id": 124,
        "name": "Casio Loopy",
        "moby_slug": "casio-loopy",
    },
    UniversalPlatformSlug.LUNA: {"id": 297, "name": "Luna", "moby_slug": "luna"},
    UniversalPlatformSlug.LYNX: {"id": 18, "name": "Lynx", "moby_slug": "lynx"},
    UniversalPlatformSlug.MAC: {
        "id": 74,
        "name": "Macintosh",
        "moby_slug": "macintosh",
    },
    UniversalPlatformSlug.MAEMO: {"id": 157, "name": "Maemo", "moby_slug": "maemo"},
    UniversalPlatformSlug.MAINFRAME: {
        "id": 208,
        "name": "Mainframe",
        "moby_slug": "mainframe",
    },
    UniversalPlatformSlug.MATSUSHITAPANASONICJR: {
        "id": 307,
        "name": "Matsushita/Panasonic JR",
        "moby_slug": "matsushitapanasonic-jr",
    },
    UniversalPlatformSlug.MEEGO: {"id": 158, "name": "MeeGo", "moby_slug": "meego"},
    UniversalPlatformSlug.MEGADRIVE: {
        "id": 16,
        "name": "Genesis/Mega Drive",
        "moby_slug": "genesis",
    },
    UniversalPlatformSlug.MEMOTECHMTX: {
        "id": 148,
        "name": "Memotech MTX",
        "moby_slug": "memotech-mtx",
    },
    UniversalPlatformSlug.MERITUM: {
        "id": 311,
        "name": "Meritum",
        "moby_slug": "meritum",
    },
    UniversalPlatformSlug.MICROBEE: {
        "id": 200,
        "name": "Microbee",
        "moby_slug": "microbee",
    },
    UniversalPlatformSlug.MICROMIND: {
        "id": 269,
        "name": "ECD Micromind",
        "moby_slug": "ecd-micromind",
    },
    UniversalPlatformSlug.MICROTAN65: {
        "id": 232,
        "name": "Microtan 65",
        "moby_slug": "microtan-65",
    },
    UniversalPlatformSlug.MICROVISION: {
        "id": 97,
        "name": "Microvision",
        "moby_slug": "microvision",
    },
    UniversalPlatformSlug.MOBILE: {
        "id": 315,
        "name": "Feature phone",
        "moby_slug": "mobile-custom",
    },
    UniversalPlatformSlug.MOPHUN: {"id": 71, "name": "Mophun", "moby_slug": "mophun"},
    UniversalPlatformSlug.MOS6502: {
        "id": 240,
        "name": "MOS Technology 6502",
        "moby_slug": "mos-technology-6502",
    },
    UniversalPlatformSlug.MOTOROLA6800: {
        "id": 235,
        "name": "Motorola 6800",
        "moby_slug": "motorola-6800",
    },
    UniversalPlatformSlug.MOTOROLA68K: {
        "id": 275,
        "name": "Motorola 68k",
        "moby_slug": "motorola-68k",
    },
    UniversalPlatformSlug.MRE: {"id": 229, "name": "MRE", "moby_slug": "mre"},
    UniversalPlatformSlug.MSX: {"id": 57, "name": "MSX", "moby_slug": "msx"},
    UniversalPlatformSlug.N64: {"id": 9, "name": "Nintendo 64", "moby_slug": "n64"},
    UniversalPlatformSlug.NASCOM: {"id": 175, "name": "Nascom", "moby_slug": "nascom"},
    UniversalPlatformSlug.NDS: {
        "id": 44,
        "name": "Nintendo DS",
        "moby_slug": "nintendo-ds",
    },
    UniversalPlatformSlug.NEOGEOAES: {
        "id": 36,
        "name": "Neo Geo",
        "moby_slug": "neo-geo",
    },
    UniversalPlatformSlug.NEOGEOCD: {
        "id": 54,
        "name": "Neo Geo CD",
        "moby_slug": "neo-geo-cd",
    },
    UniversalPlatformSlug.NEOGEOMVS: {
        "id": 36,
        "name": "Neo Geo",
        "moby_slug": "neo-geo",
    },
    UniversalPlatformSlug.NEOGEOX: {
        "id": 279,
        "name": "Neo Geo X",
        "moby_slug": "neo-geo-x",
    },
    UniversalPlatformSlug.NES: {"id": 22, "name": "NES", "moby_slug": "nes"},
    UniversalPlatformSlug.NEW3DS: {
        "id": 174,
        "name": "New Nintendo 3DS",
        "moby_slug": "new-nintendo-3ds",
    },
    UniversalPlatformSlug.NEWBRAIN: {
        "id": 177,
        "name": "NewBrain",
        "moby_slug": "newbrain",
    },
    UniversalPlatformSlug.NEWTON: {"id": 207, "name": "Newton", "moby_slug": "newton"},
    UniversalPlatformSlug.NGAGE: {"id": 32, "name": "N-Gage", "moby_slug": "ngage"},
    UniversalPlatformSlug.NGAGE2: {
        "id": 89,
        "name": "N-Gage (service)",
        "moby_slug": "ngage2",
    },
    UniversalPlatformSlug.NGC: {"id": 14, "name": "GameCube", "moby_slug": "gamecube"},
    UniversalPlatformSlug.NGP: {
        "id": 52,
        "name": "Neo Geo Pocket",
        "moby_slug": "neo-geo-pocket",
    },
    UniversalPlatformSlug.NGPC: {
        "id": 53,
        "name": "Neo Geo Pocket Color",
        "moby_slug": "neo-geo-pocket-color",
    },
    UniversalPlatformSlug.NORTHSTAR: {
        "id": 266,
        "name": "North Star",
        "moby_slug": "northstar",
    },
    UniversalPlatformSlug.NOVAL760: {
        "id": 244,
        "name": "Noval 760",
        "moby_slug": "noval-760",
    },
    UniversalPlatformSlug.NUON: {"id": 116, "name": "Nuon", "moby_slug": "nuon"},
    UniversalPlatformSlug.OCULUSGO: {
        "id": 218,
        "name": "Oculus Go",
        "moby_slug": "oculus-go",
    },
    UniversalPlatformSlug.OCULUSQUEST: {
        "id": 271,
        "name": "Quest",
        "moby_slug": "oculus-quest",
    },
    UniversalPlatformSlug.ODYSSEY: {
        "id": 75,
        "name": "Odyssey",
        "moby_slug": "odyssey",
    },
    UniversalPlatformSlug.ODYSSEY2: {
        "id": 78,
        "name": "Odyssey 2",
        "moby_slug": "odyssey-2",
    },
    UniversalPlatformSlug.OHIOSCI: {
        "id": 178,
        "name": "Ohio Scientific",
        "moby_slug": "ohio-scientific",
    },
    UniversalPlatformSlug.ONLIVE: {"id": 282, "name": "OnLive", "moby_slug": "onlive"},
    UniversalPlatformSlug.OOPARTS: {
        "id": 300,
        "name": "OOParts",
        "moby_slug": "ooparts",
    },
    UniversalPlatformSlug.ORAO: {"id": 270, "name": "Orao", "moby_slug": "orao"},
    UniversalPlatformSlug.ORIC: {"id": 111, "name": "Oric", "moby_slug": "oric"},
    UniversalPlatformSlug.OS2: {"id": 146, "name": "OS/2", "moby_slug": "os2"},
    UniversalPlatformSlug.OUYA: {"id": 144, "name": "Ouya", "moby_slug": "ouya"},
    UniversalPlatformSlug.PALMOS: {"id": 65, "name": "Palm OS", "moby_slug": "palmos"},
    UniversalPlatformSlug.PANDORA: {
        "id": 308,
        "name": "Pandora",
        "moby_slug": "pandora",
    },
    UniversalPlatformSlug.PC60: {"id": 149, "name": "PC-6001", "moby_slug": "pc-6001"},
    UniversalPlatformSlug.PC8000: {
        "id": 201,
        "name": "PC-8000",
        "moby_slug": "pc-8000",
    },
    UniversalPlatformSlug.PC88: {"id": 94, "name": "PC-88", "moby_slug": "pc88"},
    UniversalPlatformSlug.PC98: {"id": 95, "name": "PC-98", "moby_slug": "pc98"},
    UniversalPlatformSlug.PCBOOTER: {
        "id": 4,
        "name": "PC Booter",
        "moby_slug": "pc-booter",
    },
    UniversalPlatformSlug.PCENGINE: {
        "id": 40,
        "name": "TurboGrafx-16",
        "moby_slug": "turbo-grafx",
    },
    UniversalPlatformSlug.PCENGINECD: {
        "id": 45,
        "name": "TurboGrafx CD",
        "moby_slug": "turbografx-cd",
    },
    UniversalPlatformSlug.PCFX: {"id": 59, "name": "PC-FX", "moby_slug": "pc-fx"},
    UniversalPlatformSlug.PEBBLE: {"id": 304, "name": "Pebble", "moby_slug": "pebble"},
    UniversalPlatformSlug.PET: {
        "id": 77,
        "name": "Commodore PET/CBM",
        "moby_slug": "pet",
    },
    UniversalPlatformSlug.PHOTOCD: {
        "id": 272,
        "name": "Photo CD",
        "moby_slug": "photocd",
    },
    UniversalPlatformSlug.PICO: {
        "id": 103,
        "name": "SEGA Pico",
        "moby_slug": "sega-pico",
    },
    UniversalPlatformSlug.PIPPIN: {"id": 112, "name": "Pippin", "moby_slug": "pippin"},
    UniversalPlatformSlug.PLAYDATE: {
        "id": 303,
        "name": "Playdate",
        "moby_slug": "playdate",
    },
    UniversalPlatformSlug.PLAYDIA: {
        "id": 107,
        "name": "Playdia",
        "moby_slug": "playdia",
    },
    UniversalPlatformSlug.PLEXARCADE: {
        "id": 291,
        "name": "Plex Arcade",
        "moby_slug": "plex-arcade",
    },
    UniversalPlatformSlug.POKEMINI: {
        "id": 152,
        "name": "Pokémon Mini",
        "moby_slug": "pokemon-mini",
    },
    UniversalPlatformSlug.POKITTO: {
        "id": 230,
        "name": "Pokitto",
        "moby_slug": "pokitto",
    },
    UniversalPlatformSlug.POLY88: {
        "id": 249,
        "name": "Poly-88",
        "moby_slug": "poly-88",
    },
    UniversalPlatformSlug.PS2: {"id": 7, "name": "PlayStation 2", "moby_slug": "ps2"},
    UniversalPlatformSlug.PS3: {"id": 81, "name": "PlayStation 3", "moby_slug": "ps3"},
    UniversalPlatformSlug.PS4: {
        "id": 141,
        "name": "PlayStation 4",
        "moby_slug": "playstation-4",
    },
    UniversalPlatformSlug.PS5: {
        "id": 288,
        "name": "PlayStation 5",
        "moby_slug": "playstation-5",
    },
    UniversalPlatformSlug.PSNOW: {
        "id": 294,
        "name": "PlayStation Now",
        "moby_slug": "playstation-now",
    },
    UniversalPlatformSlug.PSP: {"id": 46, "name": "PSP", "moby_slug": "psp"},
    UniversalPlatformSlug.PSVITA: {
        "id": 105,
        "name": "PS Vita",
        "moby_slug": "ps-vita",
    },
    UniversalPlatformSlug.PSX: {
        "id": 6,
        "name": "PlayStation",
        "moby_slug": "playstation",
    },
    UniversalPlatformSlug.PV1000: {
        "id": 125,
        "name": "Casio PV-1000",
        "moby_slug": "casio-pv-1000",
    },
    UniversalPlatformSlug.RCASTUDIO2: {
        "id": 113,
        "name": "RCA Studio II",
        "moby_slug": "rca-studio-ii",
    },
    UniversalPlatformSlug.RM380Z: {
        "id": 309,
        "name": "Research Machines 380Z",
        "moby_slug": "research-machines-380z",
    },
    UniversalPlatformSlug.ROKU: {"id": 196, "name": "Roku", "moby_slug": "roku"},
    UniversalPlatformSlug.SAMCOUPE: {
        "id": 120,
        "name": "SAM Coupé",
        "moby_slug": "sam-coupe",
    },
    UniversalPlatformSlug.SATURN: {
        "id": 23,
        "name": "SEGA Saturn",
        "moby_slug": "sega-saturn",
    },
    UniversalPlatformSlug.SCMP: {"id": 255, "name": "SC/MP", "moby_slug": "scmp"},
    UniversalPlatformSlug.SCV: {
        "id": 138,
        "name": "Epoch Super Cassette Vision",
        "moby_slug": "epoch-super-cassette-vision",
    },
    UniversalPlatformSlug.SD200: {
        "id": 267,
        "name": "SD-200/270/290",
        "moby_slug": "sd-200270290",
    },
    UniversalPlatformSlug.SEGA32X: {
        "id": 21,
        "name": "SEGA 32X",
        "moby_slug": "sega-32x",
    },
    UniversalPlatformSlug.SEGACD: {"id": 20, "name": "SEGA CD", "moby_slug": "sega-cd"},
    UniversalPlatformSlug.SERIESXS: {
        "id": 289,
        "name": "Xbox Series",
        "moby_slug": "xbox-series",
    },
    UniversalPlatformSlug.SFAM: {"id": 15, "name": "SNES", "moby_slug": "sfam"},
    UniversalPlatformSlug.SG1000: {
        "id": 114,
        "name": "SG-1000",
        "moby_slug": "sg-1000",
    },
    UniversalPlatformSlug.SIGNETICS2650: {
        "id": 278,
        "name": "Signetics 2650",
        "moby_slug": "signetics-2650",
    },
    UniversalPlatformSlug.SINCLAIRQL: {
        "id": 131,
        "name": "Sinclair QL",
        "moby_slug": "sinclair-ql",
    },
    UniversalPlatformSlug.SKVM: {"id": 259, "name": "SK-VM", "moby_slug": "sk-vm"},
    UniversalPlatformSlug.SMC777: {
        "id": 273,
        "name": "SMC-777",
        "moby_slug": "smc-777",
    },
    UniversalPlatformSlug.SMS: {
        "id": 26,
        "name": "SEGA Master System",
        "moby_slug": "sega-master-system",
    },
    UniversalPlatformSlug.SNES: {"id": 15, "name": "SNES", "moby_slug": "snes"},
    UniversalPlatformSlug.SOCRATES: {
        "id": 190,
        "name": "Socrates",
        "moby_slug": "socrates",
    },
    UniversalPlatformSlug.SOL20: {"id": 199, "name": "Sol-20", "moby_slug": "sol-20"},
    UniversalPlatformSlug.SORDM5: {
        "id": 134,
        "name": "Sord M5",
        "moby_slug": "sord-m5",
    },
    UniversalPlatformSlug.SPECTRAVIDEO: {
        "id": 85,
        "name": "Spectravideo",
        "moby_slug": "spectravideo",
    },
    UniversalPlatformSlug.SRI500: {
        "id": 242,
        "name": "SRI-500/1000",
        "moby_slug": "sri-5001000",
    },
    UniversalPlatformSlug.STADIA: {"id": 281, "name": "Stadia", "moby_slug": "stadia"},
    UniversalPlatformSlug.SUPERACAN: {
        "id": 110,
        "name": "Super A'can",
        "moby_slug": "super-acan",
    },
    UniversalPlatformSlug.SUPERGRAFX: {
        "id": 127,
        "name": "SuperGrafx",
        "moby_slug": "supergrafx",
    },
    UniversalPlatformSlug.SUPERVISION: {
        "id": 109,
        "name": "Supervision",
        "moby_slug": "supervision",
    },
    UniversalPlatformSlug.SUPERVISION8000: {
        "id": 296,
        "name": "Super Vision 8000",
        "moby_slug": "super-vision-8000",
    },
    UniversalPlatformSlug.SURESHOTHD: {
        "id": 287,
        "name": "Sure Shot HD",
        "moby_slug": "sure-shot-hd",
    },
    UniversalPlatformSlug.SWITCH: {
        "id": 203,
        "name": "Nintendo Switch",
        "moby_slug": "switch",
    },
    UniversalPlatformSlug.SWTPC6800: {
        "id": 228,
        "name": "SWTPC 6800",
        "moby_slug": "swtpc-6800",
    },
    UniversalPlatformSlug.SYMBIAN: {
        "id": 67,
        "name": "Symbian",
        "moby_slug": "symbian",
    },
    UniversalPlatformSlug.TADS: {"id": 171, "name": "TADS", "moby_slug": "tads"},
    UniversalPlatformSlug.TATUNGEINSTEIN: {
        "id": 150,
        "name": "Tatung Einstein",
        "moby_slug": "tatung-einstein",
    },
    UniversalPlatformSlug.TEKTRONIX4050: {
        "id": 223,
        "name": "Tektronix 4050",
        "moby_slug": "tektronix-4050",
    },
    UniversalPlatformSlug.TELESPIEL: {
        "id": 220,
        "name": "Tele-Spiel ES-2201",
        "moby_slug": "tele-spiel",
    },
    UniversalPlatformSlug.TELSTAR: {
        "id": 233,
        "name": "Telstar Arcade",
        "moby_slug": "telstar-arcade",
    },
    UniversalPlatformSlug.TERMINAL: {
        "id": 209,
        "name": "Terminal",
        "moby_slug": "terminal",
    },
    UniversalPlatformSlug.THOMSONMO: {
        "id": 147,
        "name": "Thomson MO",
        "moby_slug": "thomson-mo",
    },
    UniversalPlatformSlug.THOMSONTO: {
        "id": 130,
        "name": "Thomson TO",
        "moby_slug": "thomson-to",
    },
    UniversalPlatformSlug.TI99: {"id": 47, "name": "TI-99/4A", "moby_slug": "ti-99"},
    UniversalPlatformSlug.TIKI100: {
        "id": 263,
        "name": "Tiki 100",
        "moby_slug": "tiki-100",
    },
    UniversalPlatformSlug.TIM: {"id": 246, "name": "TIM", "moby_slug": "tim"},
    UniversalPlatformSlug.TIMEX2068: {
        "id": 173,
        "name": "Timex Sinclair 2068",
        "moby_slug": "timex-sinclair-2068",
    },
    UniversalPlatformSlug.TICALC: {
        "id": 239,
        "name": "TI Programmable Calculator",
        "moby_slug": "ti-programmable-calculator",
    },
    UniversalPlatformSlug.TIZEN: {"id": 206, "name": "Tizen", "moby_slug": "tizen"},
    UniversalPlatformSlug.TOMAHAWKF1: {
        "id": 256,
        "name": "Tomahawk F1",
        "moby_slug": "tomahawk-f1",
    },
    UniversalPlatformSlug.TRITON: {"id": 310, "name": "Triton", "moby_slug": "triton"},
    UniversalPlatformSlug.TRS80: {"id": 58, "name": "TRS-80", "moby_slug": "trs-80"},
    UniversalPlatformSlug.TRS80MC10: {
        "id": 193,
        "name": "TRS-80 MC-10",
        "moby_slug": "trs-80-mc-10",
    },
    UniversalPlatformSlug.TRS80MODEL100: {
        "id": 312,
        "name": "TRS-80 Model 100",
        "moby_slug": "trs-80-model-100",
    },
    UniversalPlatformSlug.TUTOR: {
        "id": 151,
        "name": "Tomy Tutor",
        "moby_slug": "tomy-tutor",
    },
    UniversalPlatformSlug.TVOS: {"id": 179, "name": "tvOS", "moby_slug": "tvos"},
    UniversalPlatformSlug.VECTREX: {
        "id": 37,
        "name": "Vectrex",
        "moby_slug": "vectrex",
    },
    UniversalPlatformSlug.VERSATILE: {
        "id": 299,
        "name": "Versatile",
        "moby_slug": "versatile",
    },
    UniversalPlatformSlug.VFLASH: {"id": 189, "name": "V.Flash", "moby_slug": "vflash"},
    UniversalPlatformSlug.VG5000: {
        "id": 133,
        "name": "Philips VG 5000",
        "moby_slug": "philips-vg-5000",
    },
    UniversalPlatformSlug.VIDEOBRAIN: {
        "id": 214,
        "name": "VideoBrain",
        "moby_slug": "videobrain",
    },
    UniversalPlatformSlug.VIDEOPACPLUS: {
        "id": 128,
        "name": "Videopac+ G7400",
        "moby_slug": "videopac-g7400",
    },
    UniversalPlatformSlug.VIRTUALBOY: {
        "id": 38,
        "name": "Virtual Boy",
        "moby_slug": "virtual-boy",
    },
    UniversalPlatformSlug.VIS: {"id": 164, "name": "VIS", "moby_slug": "vis"},
    UniversalPlatformSlug.VSMILE: {"id": 42, "name": "V.Smile", "moby_slug": "vsmile"},
    UniversalPlatformSlug.WANG2200: {
        "id": 217,
        "name": "Wang 2200",
        "moby_slug": "wang2200",
    },
    UniversalPlatformSlug.WATCHOS: {
        "id": 180,
        "name": "watchOS",
        "moby_slug": "watchos",
    },
    UniversalPlatformSlug.WEBOS: {"id": 100, "name": "webOS", "moby_slug": "webos"},
    UniversalPlatformSlug.WII: {"id": 82, "name": "Wii", "moby_slug": "wii"},
    UniversalPlatformSlug.WIIU: {"id": 132, "name": "Wii U", "moby_slug": "wii-u"},
    UniversalPlatformSlug.WIN: {"id": 3, "name": "Windows", "moby_slug": "windows"},
    UniversalPlatformSlug.WIN3X: {"id": 5, "name": "Windows 3.x", "moby_slug": "win3x"},
    UniversalPlatformSlug.WINDOWSAPPS: {
        "id": 140,
        "name": "Windows Apps",
        "moby_slug": "windows-apps",
    },
    UniversalPlatformSlug.WINDOWSMOBILE: {
        "id": 66,
        "name": "Windows Mobile",
        "moby_slug": "windowsmobile",
    },
    UniversalPlatformSlug.WINPHONE: {
        "id": 98,
        "name": "Windows Phone",
        "moby_slug": "windows-phone",
    },
    UniversalPlatformSlug.WIPI: {"id": 260, "name": "WIPI", "moby_slug": "wipi"},
    UniversalPlatformSlug.WSWAN: {
        "id": 48,
        "name": "WonderSwan",
        "moby_slug": "wonderswan",
    },
    UniversalPlatformSlug.WSWANC: {
        "id": 49,
        "name": "WonderSwan Color",
        "moby_slug": "wonderswan-color",
    },
    UniversalPlatformSlug.X1: {"id": 121, "name": "Sharp X1", "moby_slug": "sharp-x1"},
    UniversalPlatformSlug.X55: {
        "id": 283,
        "name": "Taito X-55",
        "moby_slug": "taito-x-55",
    },
    UniversalPlatformSlug.X68000: {
        "id": 106,
        "name": "Sharp X68000",
        "moby_slug": "sharp-x68000",
    },
    UniversalPlatformSlug.XAVIXPORT: {
        "id": 191,
        "name": "XaviXPORT",
        "moby_slug": "xavixport",
    },
    UniversalPlatformSlug.XBOX: {"id": 13, "name": "Xbox", "moby_slug": "xbox"},
    UniversalPlatformSlug.XBOX360: {
        "id": 69,
        "name": "Xbox 360",
        "moby_slug": "xbox360",
    },
    UniversalPlatformSlug.XBOXCLOUDGAMING: {
        "id": 293,
        "name": "Xbox Cloud Gaming",
        "moby_slug": "xboxcloudgaming",
    },
    UniversalPlatformSlug.XBOXONE: {
        "id": 142,
        "name": "Xbox One",
        "moby_slug": "xbox-one",
    },
    UniversalPlatformSlug.XEROXALTO: {
        "id": 254,
        "name": "Xerox Alto",
        "moby_slug": "xerox-alto",
    },
    UniversalPlatformSlug.Z80: {"id": 227, "name": "Zilog Z80", "moby_slug": "z80"},
    UniversalPlatformSlug.Z8000: {
        "id": 276,
        "name": "Zilog Z8000",
        "moby_slug": "zilog-z8000",
    },
    UniversalPlatformSlug.ZAURUS: {
        "id": 202,
        "name": "Sharp Zaurus",
        "moby_slug": "sharp-zaurus",
    },
    UniversalPlatformSlug.ZEEBO: {"id": 88, "name": "Zeebo", "moby_slug": "zeebo"},
    UniversalPlatformSlug.ZMACHINE: {
        "id": 169,
        "name": "Z-machine",
        "moby_slug": "z-machine",
    },
    UniversalPlatformSlug.ZODIAC: {"id": 68, "name": "Zodiac", "moby_slug": "zodiac"},
    UniversalPlatformSlug.ZUNE: {"id": 211, "name": "Zune", "moby_slug": "zune"},
    UniversalPlatformSlug.ZX80: {"id": 118, "name": "ZX80", "moby_slug": "zx80"},
    UniversalPlatformSlug.ZX81: {"id": 119, "name": "ZX81", "moby_slug": "zx81"},
    UniversalPlatformSlug.ZXS: {
        "id": 41,
        "name": "ZX Spectrum",
        "moby_slug": "zx-spectrum",
    },
    UniversalPlatformSlug.ZXSNEXT: {
        "id": 280,
        "name": "ZX Spectrum Next",
        "moby_slug": "zx-spectrum-next",
    },
}

MOBY_PLATFORM_SLUGS = SLUG_TO_MOBY_PLATFORM.keys()
# Reverse lookup
MOBY_ID_TO_MOBY_PLATFORM = {v["id"]: k for k, v in SLUG_TO_MOBY_PLATFORM.items()}
