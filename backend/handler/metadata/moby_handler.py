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
        platform = SLUG_TO_MOBY_PLATFORM.get(slug, None)

        if not platform:
            return MobyGamesPlatform(moby_id=None, slug=slug)

        return MobyGamesPlatform(
            moby_id=platform["id"],
            slug=slug,
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


SLUG_TO_MOBY_PLATFORM: dict[str, SlugToMobyPlatform] = {
    "1292apvs": {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
        "moby_slug": "1292-advanced-programmable-video-system",
    },
    "3do": {"id": 35, "name": "3DO", "moby_slug": "3do"},
    "abc80": {"id": 318, "name": "ABC 80", "moby_slug": "abc-80"},
    "apf": {"id": 213, "name": "APF MP1000/Imagination Machine", "moby_slug": "apf"},
    "acornarchimedes": {
        "id": 117,
        "name": "Acorn Archimedes",
        "moby_slug": "acornarchimedes",
    },
    "advision": {
        "id": 210,
        "name": "Adventure Vision",
        "moby_slug": "adventure-vision",
    },
    "airconsole": {"id": 305, "name": "AirConsole", "moby_slug": "airconsole"},
    "alice3290": {"id": 194, "name": "Alice 32/90", "moby_slug": "alice-3290"},
    "altair680": {"id": 265, "name": "Altair 680", "moby_slug": "altair-680"},
    "altair8800": {"id": 222, "name": "Altair 8800", "moby_slug": "altair-8800"},
    "amazonalexa": {"id": 237, "name": "Amazon Alexa", "moby_slug": "amazonalexa"},
    "amiga": {"id": 19, "name": "Amiga", "moby_slug": "amiga"},
    "amigacd32": {"id": 56, "name": "Amiga CD32", "moby_slug": "amiga-cd32"},
    "amstradcpc": {"id": 60, "name": "Amstrad CPC", "moby_slug": "amstradcpc"},
    "amstradpcw": {"id": 136, "name": "Amstrad PCW", "moby_slug": "amstrad-pcw"},
    "android": {"id": 91, "name": "Android", "moby_slug": "android"},
    "antstream": {"id": 286, "name": "Antstream", "moby_slug": "antstream"},
    "apple": {"id": 245, "name": "Apple I", "moby_slug": "apple-i"},
    "apple2": {"id": 31, "name": "Apple II", "moby_slug": "apple2"},
    "apple2gs": {"id": 51, "name": "Apple IIGS", "moby_slug": "apple2gs"},
    "arcade": {"id": 143, "name": "Arcade", "moby_slug": "arcade"},
    "arcadia": {"id": 162, "name": "Arcadia 2001", "moby_slug": "arcadia-2001"},
    "arduboy": {"id": 215, "name": "Arduboy", "moby_slug": "arduboy"},
    "astral2000": {"id": 241, "name": "Astral 2000", "moby_slug": "astral-2000"},
    "atari2600": {"id": 28, "name": "Atari 2600", "moby_slug": "atari-2600"},
    "atari5200": {"id": 33, "name": "Atari 5200", "moby_slug": "atari-5200"},
    "atari7800": {"id": 34, "name": "Atari 7800", "moby_slug": "atari-7800"},
    "atari8bit": {"id": 39, "name": "Atari 8-bit", "moby_slug": "atari8bit"},
    "atarist": {"id": 24, "name": "Atari ST", "moby_slug": "atari-st"},
    "atarivcs": {"id": 319, "name": "Atari VCS", "moby_slug": "atari-vcs"},
    "atom": {"id": 129, "name": "Atom", "moby_slug": "atom"},
    "bbcmicro": {"id": 92, "name": "BBC Micro", "moby_slug": "bbc-micro"},
    "brew": {"id": 63, "name": "BREW", "moby_slug": "brew"},
    "astrocade": {
        "id": 160,
        "name": "Bally Astrocade",
        "moby_slug": "bally-astrocade",
    },
    "beos": {"id": 165, "name": "BeOS", "moby_slug": "beos"},
    "blackberry": {"id": 90, "name": "BlackBerry", "moby_slug": "blackberry"},
    "blacknut": {"id": 290, "name": "Blacknut", "moby_slug": "blacknut"},
    "bluray": {
        "id": 168,
        "name": "Blu-ray Player",
        "moby_slug": "blu-ray-disc-player",
    },
    "browser": {"id": 84, "name": "Browser", "moby_slug": "browser"},
    "bubble": {"id": 231, "name": "Bubble", "moby_slug": "bubble"},
    "cdi": {"id": 73, "name": "CD-i", "moby_slug": "cd-i"},
    "cdtv": {"id": 83, "name": "CDTV", "moby_slug": "cdtv"},
    "cosmac": {"id": 216, "name": "COSMAC", "moby_slug": "fred-cosmac"},
    "camplynx": {
        "id": 154,
        "name": "Camputers Lynx",
        "moby_slug": "camputers-lynx",
    },
    "cpm": {"id": 261, "name": "CP/M", "moby_slug": "cpm"},
    "loopy": {"id": 124, "name": "Casio Loopy", "moby_slug": "casio-loopy"},
    "pv1000": {"id": 125, "name": "Casio PV-1000", "moby_slug": "casio-pv-1000"},
    "casiopc": {
        "id": 306,
        "name": "Casio Programmable Calculator",
        "moby_slug": "casio-programmable-calculator",
    },
    "champion2711": {"id": 298, "name": "Champion 2711", "moby_slug": "champion-2711"},
    "channelf": {"id": 76, "name": "Channel F", "moby_slug": "channel-f"},
    "clickstart": {"id": 188, "name": "ClickStart", "moby_slug": "clickstart"},
    "colecoadam": {"id": 156, "name": "Coleco Adam", "moby_slug": "colecoadam"},
    "colecovision": {"id": 29, "name": "ColecoVision", "moby_slug": "colecovision"},
    "colourgenie": {"id": 197, "name": "Colour Genie", "moby_slug": "colour-genie"},
    "c128": {"id": 61, "name": "Commodore 128", "moby_slug": "c128"},
    "c16plus4": {
        "id": 115,
        "name": "Commodore 16, Plus/4",
        "moby_slug": "commodore-16-plus4",
    },
    "cplus4": {
        "id": 115,
        "name": "Commodore Plus/4",
        "moby_slug": "c-plus-4",
    },
    "c16": {"id": 115, "name": "Commodore 16", "moby_slug": "c16"},
    "c64": {"id": 27, "name": "Commodore 64", "moby_slug": "c64"},
    "pet": {"id": 77, "name": "Commodore PET/CBM", "moby_slug": "pet"},
    "cpet": {"id": 77, "name": "Commodore PET/CBM", "moby_slug": "cpet"},
    "compucolor": {"id": 243, "name": "Compucolor I", "moby_slug": "compucolor-i"},
    "compucolor2": {"id": 198, "name": "Compucolor II", "moby_slug": "compucolor-ii"},
    "compucorppc": {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
        "moby_slug": "compucorp-programmable-calculator",
    },
    "creativision": {"id": 212, "name": "CreatiVision", "moby_slug": "creativision"},
    "cybervision": {"id": 301, "name": "Cybervision", "moby_slug": "cybervision"},
    "dos": {"id": 2, "name": "DOS", "moby_slug": "dos"},
    "dvd": {"id": 166, "name": "DVD Player", "moby_slug": "dvd-player"},
    "dangeros": {"id": 285, "name": "Danger OS", "moby_slug": "danger-os"},
    "dedicatedconsole": {
        "id": 204,
        "name": "Dedicated console",
        "moby_slug": "dedicated-console",
    },
    "dedicatedhandheld": {
        "id": 205,
        "name": "Dedicated handheld",
        "moby_slug": "dedicated-handheld",
    },
    "didj": {"id": 184, "name": "Didj", "moby_slug": "didj"},
    "doja": {"id": 72, "name": "DoJa", "moby_slug": "doja"},
    "dragon32": {"id": 79, "name": "Dragon 32/64", "moby_slug": "dragon-3264"},
    "dreamcast": {"id": 8, "name": "Dreamcast", "moby_slug": "dreamcast"},
    "micromind": {"id": 269, "name": "ECD Micromind", "moby_slug": "ecd-micromind"},
    "acornelectron": {"id": 93, "name": "Electron", "moby_slug": "electron"},
    "enterprise": {"id": 161, "name": "Enterprise", "moby_slug": "enterprise"},
    "ecv": {
        "id": 137,
        "name": "Epoch Cassette Vision",
        "moby_slug": "epoch-cassette-vision",
    },
    "egpc": {
        "id": 139,
        "name": "Epoch Game Pocket Computer",
        "moby_slug": "epoch-game-pocket-computer",
    },
    "scv": {
        "id": 138,
        "name": "Epoch Super Cassette Vision",
        "moby_slug": "epoch-super-cassette-vision",
    },
    "evercade": {"id": 284, "name": "Evercade", "moby_slug": "evercade"},
    "exen": {"id": 70, "name": "ExEn", "moby_slug": "exen"},
    "exelvision": {"id": 195, "name": "Exelvision", "moby_slug": "exelvision"},
    "exidysorcerer": {
        "id": 176,
        "name": "Exidy Sorcerer",
        "moby_slug": "exidy-sorcerer",
    },
    "fmtowns": {"id": 102, "name": "FM Towns", "moby_slug": "fmtowns"},
    "fm7": {"id": 126, "name": "FM-7", "moby_slug": "fm-7"},
    "mobile": {"id": 315, "name": "Feature phone", "moby_slug": "mobile-custom"},
    "fireos": {"id": 159, "name": "Fire OS", "moby_slug": "fire-os"},
    "amazonfiretv": {"id": 159, "name": "Fire TV", "moby_slug": "amazonfiretv"},
    "freebox": {"id": 268, "name": "Freebox", "moby_slug": "freebox"},
    "gameandwatch": {
        "id": 205,
        "name": "Dedicated handheld",
        "moby_slug": "g-and-w",
    },
    "gcluster": {"id": 302, "name": "G-cluster", "moby_slug": "g-cluster"},
    "gimini": {"id": 251, "name": "GIMINI", "moby_slug": "gimini"},
    "gnex": {"id": 258, "name": "GNEX", "moby_slug": "gnex"},
    "gp2x": {"id": 122, "name": "GP2X", "moby_slug": "gp2x"},
    "gp2xwiz": {"id": 123, "name": "GP2X Wiz", "moby_slug": "gp2x-wiz"},
    "gp32": {"id": 108, "name": "GP32", "moby_slug": "gp32"},
    "gvm": {"id": 257, "name": "GVM", "moby_slug": "gvm"},
    "galaksija": {"id": 236, "name": "Galaksija", "moby_slug": "galaksija"},
    "gb": {"id": 10, "name": "Game Boy", "moby_slug": "gameboy"},
    "gba": {
        "id": 12,
        "name": "Game Boy Advance",
        "moby_slug": "gameboy-advance",
    },
    "gbc": {"id": 11, "name": "Game Boy Color", "moby_slug": "gameboy-color"},
    "gamegear": {"id": 25, "name": "Game Gear", "moby_slug": "game-gear"},
    "gamewave": {"id": 104, "name": "Game Wave", "moby_slug": "game-wave"},
    "gamecom": {"id": 50, "name": "Game.Com", "moby_slug": "game-com"},
    "ngc": {"id": 14, "name": "GameCube", "moby_slug": "gamecube"},
    "gamestick": {"id": 155, "name": "GameStick", "moby_slug": "gamestick"},
    "megadrive": {"id": 16, "name": "Genesis/Mega Drive", "moby_slug": "genesis"},
    "gizmondo": {"id": 55, "name": "Gizmondo", "moby_slug": "gizmondo"},
    "gloud": {"id": 292, "name": "Gloud", "moby_slug": "gloud"},
    "glulx": {"id": 172, "name": "Glulx", "moby_slug": "glulx"},
    "hddvd": {"id": 167, "name": "HD DVD Player", "moby_slug": "hd-dvd-player"},
    "hp9800": {"id": 219, "name": "HP 9800", "moby_slug": "hp-9800"},
    "hppc": {
        "id": 234,
        "name": "HP Programmable Calculator",
        "moby_slug": "hp-programmable-calculator",
    },
    "heathzenith": {
        "id": 262,
        "name": "Heath/Zenith H8/H89",
        "moby_slug": "heathzenith",
    },
    "heathkith11": {"id": 248, "name": "Heathkit H11", "moby_slug": "heathkit-h11"},
    "hitachis1": {"id": 274, "name": "Hitachi S1", "moby_slug": "hitachi-s1"},
    "hugo": {"id": 170, "name": "Hugo", "moby_slug": "hugo"},
    "hyperscan": {"id": 192, "name": "HyperScan", "moby_slug": "hyperscan"},
    "ibm5100": {"id": 250, "name": "IBM 5100", "moby_slug": "ibm-5100"},
    "idealcomputer": {
        "id": 252,
        "name": "Ideal-Computer",
        "moby_slug": "ideal-computer",
    },
    "intel8008": {"id": 224, "name": "Intel 8008", "moby_slug": "intel-8008"},
    "intel8080": {"id": 225, "name": "Intel 8080", "moby_slug": "intel-8080"},
    "intel8086": {"id": 317, "name": "Intel 8086 / 8088", "moby_slug": "intel-8086"},
    "intellivision": {"id": 30, "name": "Intellivision", "moby_slug": "intellivision"},
    "interactm1": {
        "id": 295,
        "name": "Interact Model One",
        "moby_slug": "interact-model-one",
    },
    "intertonv2000": {
        "id": 221,
        "name": "Interton Video 2000",
        "moby_slug": "interton-video-2000",
    },
    "j2me": {"id": 64, "name": "J2ME", "moby_slug": "j2me"},
    "jaguar": {"id": 17, "name": "Jaguar", "moby_slug": "jaguar"},
    "jolt": {"id": 247, "name": "Jolt", "moby_slug": "jolt"},
    "jupiterace": {"id": 153, "name": "Jupiter Ace", "moby_slug": "jupiter-ace"},
    "kim1": {"id": 226, "name": "KIM-1", "moby_slug": "kim-1"},
    "kaios": {"id": 313, "name": "KaiOS", "moby_slug": "kaios"},
    "kindle": {"id": 145, "name": "Kindle Classic", "moby_slug": "kindle"},
    "laser200": {"id": 264, "name": "Laser 200", "moby_slug": "laser200"},
    "laseractive": {"id": 163, "name": "LaserActive", "moby_slug": "laseractive"},
    "leapster": {"id": 183, "name": "Leapster", "moby_slug": "leapster"},
    "leapsterexplorer": {
        "id": 185,
        "name": "LeapFrog Explorer",
        "moby_slug": "leapfrog-explorer",
    },
    "leaptv": {
        "id": 186,
        "name": "LeapTV",
        "moby_slug": "leaptv",
    },
    "linux": {"id": 1, "name": "Linux", "moby_slug": "linux"},
    "luna": {"id": 297, "name": "Luna", "moby_slug": "luna"},
    "lynx": {"id": 18, "name": "Lynx", "moby_slug": "lynx"},
    "mos6502": {
        "id": 240,
        "name": "MOS Technology 6502",
        "moby_slug": "mos-technology-6502",
    },
    "mre": {"id": 229, "name": "MRE", "moby_slug": "mre"},
    "msx": {"id": 57, "name": "MSX", "moby_slug": "msx"},
    "mac": {"id": 74, "name": "Macintosh", "moby_slug": "macintosh"},
    "maemo": {"id": 157, "name": "Maemo", "moby_slug": "maemo"},
    "mainframe": {"id": 208, "name": "Mainframe", "moby_slug": "mainframe"},
    "matsushitapanasonicjr": {
        "id": 307,
        "name": "Matsushita/Panasonic JR",
        "moby_slug": "matsushitapanasonic-jr",
    },
    "aquarius": {
        "id": 135,
        "name": "Mattel Aquarius",
        "moby_slug": "mattel-aquarius",
    },
    "meego": {"id": 158, "name": "MeeGo", "moby_slug": "meego"},
    "memotechmtx": {"id": 148, "name": "Memotech MTX", "moby_slug": "memotech-mtx"},
    "meritum": {"id": 311, "name": "Meritum", "moby_slug": "meritum"},
    "microbee": {"id": 200, "name": "Microbee", "moby_slug": "microbee"},
    "microtan65": {"id": 232, "name": "Microtan 65", "moby_slug": "microtan-65"},
    "microvision": {"id": 97, "name": "Microvision", "moby_slug": "microvision"},
    "mophun": {"id": 71, "name": "Mophun", "moby_slug": "mophun"},
    "motorola6800": {"id": 235, "name": "Motorola 6800", "moby_slug": "motorola-6800"},
    "motorola68k": {"id": 275, "name": "Motorola 68k", "moby_slug": "motorola-68k"},
    "ngage": {"id": 32, "name": "N-Gage", "moby_slug": "ngage"},
    "ngage2": {"id": 89, "name": "N-Gage (service)", "moby_slug": "ngage2"},
    "nes": {"id": 22, "name": "NES", "moby_slug": "nes"},
    "famicom": {"id": 22, "name": "NES", "moby_slug": "famicom"},
    "nascom": {"id": 175, "name": "Nascom", "moby_slug": "nascom"},
    "neogeoaes": {"id": 36, "name": "Neo Geo", "moby_slug": "neo-geo"},
    "neogeomvs": {"id": 36, "name": "Neo Geo", "moby_slug": "neo-geo"},
    "neogeocd": {"id": 54, "name": "Neo Geo CD", "moby_slug": "neo-geo-cd"},
    "ngp": {
        "id": 52,
        "name": "Neo Geo Pocket",
        "moby_slug": "neo-geo-pocket",
    },
    "ngpc": {
        "id": 53,
        "name": "Neo Geo Pocket Color",
        "moby_slug": "neo-geo-pocket-color",
    },
    "neogeox": {"id": 279, "name": "Neo Geo X", "moby_slug": "neo-geo-x"},
    "new3ds": {
        "id": 174,
        "name": "New Nintendo 3DS",
        "moby_slug": "new-nintendo-3ds",
    },
    "newbrain": {"id": 177, "name": "NewBrain", "moby_slug": "newbrain"},
    "newton": {"id": 207, "name": "Newton", "moby_slug": "newton"},
    "3ds": {"id": 101, "name": "Nintendo 3DS", "moby_slug": "3ds"},
    "n64": {"id": 9, "name": "Nintendo 64", "moby_slug": "n64"},
    "nds": {"id": 44, "name": "Nintendo DS", "moby_slug": "nintendo-ds"},
    "dsi": {"id": 87, "name": "Nintendo DSi", "moby_slug": "nintendo-dsi"},
    "switch": {"id": 203, "name": "Nintendo Switch", "moby_slug": "switch"},
    "northstar": {"id": 266, "name": "North Star", "moby_slug": "northstar"},
    "noval760": {"id": 244, "name": "Noval 760", "moby_slug": "noval-760"},
    "nuon": {"id": 116, "name": "Nuon", "moby_slug": "nuon"},
    "ooparts": {"id": 300, "name": "OOParts", "moby_slug": "ooparts"},
    "os2": {"id": 146, "name": "OS/2", "moby_slug": "os2"},
    "oculusgo": {"id": 218, "name": "Oculus Go", "moby_slug": "oculus-go"},
    "oculusquest": {"id": 271, "name": "Quest", "moby_slug": "oculus-quest"},
    "odyssey": {"id": 75, "name": "Odyssey", "moby_slug": "odyssey"},
    "odyssey2": {"id": 78, "name": "Odyssey 2", "moby_slug": "odyssey-2"},
    "ohiosci": {
        "id": 178,
        "name": "Ohio Scientific",
        "moby_slug": "ohio-scientific",
    },
    "onlive": {"id": 282, "name": "OnLive", "moby_slug": "onlive"},
    "orao": {"id": 270, "name": "Orao", "moby_slug": "orao"},
    "oric": {"id": 111, "name": "Oric", "moby_slug": "oric"},
    "ouya": {"id": 144, "name": "Ouya", "moby_slug": "ouya"},
    "pcbooter": {"id": 4, "name": "PC Booter", "moby_slug": "pc-booter"},
    "pc60": {"id": 149, "name": "PC-6001", "moby_slug": "pc-6001"},
    "pc8000": {"id": 201, "name": "PC-8000", "moby_slug": "pc-8000"},
    "pc88": {"id": 94, "name": "PC-88", "moby_slug": "pc88"},
    "pc98": {"id": 95, "name": "PC-98", "moby_slug": "pc98"},
    "pcfx": {"id": 59, "name": "PC-FX", "moby_slug": "pc-fx"},
    "psvita": {"id": 105, "name": "PS Vita", "moby_slug": "ps-vita"},
    "psp": {"id": 46, "name": "PSP", "moby_slug": "psp"},
    "palmos": {"id": 65, "name": "Palm OS", "moby_slug": "palmos"},
    "pandora": {"id": 308, "name": "Pandora", "moby_slug": "pandora"},
    "pebble": {"id": 304, "name": "Pebble", "moby_slug": "pebble"},
    "vg5000": {
        "id": 133,
        "name": "Philips VG 5000",
        "moby_slug": "philips-vg-5000",
    },
    "photocd": {"id": 272, "name": "Photo CD", "moby_slug": "photocd"},
    "pippin": {"id": 112, "name": "Pippin", "moby_slug": "pippin"},
    "psx": {"id": 6, "name": "PlayStation", "moby_slug": "playstation"},
    "ps2": {"id": 7, "name": "PlayStation 2", "moby_slug": "ps2"},
    "ps3": {"id": 81, "name": "PlayStation 3", "moby_slug": "ps3"},
    "ps4": {"id": 141, "name": "PlayStation 4", "moby_slug": "playstation-4"},
    "ps5": {"id": 288, "name": "PlayStation 5", "moby_slug": "playstation-5"},
    "psnow": {
        "id": 294,
        "name": "PlayStation Now",
        "moby_slug": "playstation-now",
    },
    "playdate": {"id": 303, "name": "Playdate", "moby_slug": "playdate"},
    "playdia": {"id": 107, "name": "Playdia", "moby_slug": "playdia"},
    "plexarcade": {"id": 291, "name": "Plex Arcade", "moby_slug": "plex-arcade"},
    "pokitto": {"id": 230, "name": "Pokitto", "moby_slug": "pokitto"},
    "pokemini": {"id": 152, "name": "Pokémon Mini", "moby_slug": "pokemon-mini"},
    "poly88": {"id": 249, "name": "Poly-88", "moby_slug": "poly-88"},
    "rcastudio2": {"id": 113, "name": "RCA Studio II", "moby_slug": "rca-studio-ii"},
    "rm380z": {
        "id": 309,
        "name": "Research Machines 380Z",
        "moby_slug": "research-machines-380z",
    },
    "roku": {"id": 196, "name": "Roku", "moby_slug": "roku"},
    "samcoupe": {"id": 120, "name": "SAM Coupé", "moby_slug": "sam-coupe"},
    "scmp": {"id": 255, "name": "SC/MP", "moby_slug": "scmp"},
    "sd200": {"id": 267, "name": "SD-200/270/290", "moby_slug": "sd-200270290"},
    "sega32x": {"id": 21, "name": "SEGA 32X", "moby_slug": "sega-32x"},
    "segacd": {"id": 20, "name": "SEGA CD", "moby_slug": "sega-cd"},
    "sms": {
        "id": 26,
        "name": "SEGA Master System",
        "moby_slug": "sega-master-system",
    },
    "pico": {"id": 103, "name": "SEGA Pico", "moby_slug": "sega-pico"},
    "saturn": {"id": 23, "name": "SEGA Saturn", "moby_slug": "sega-saturn"},
    "sg1000": {"id": 114, "name": "SG-1000", "moby_slug": "sg-1000"},
    "skvm": {"id": 259, "name": "SK-VM", "moby_slug": "sk-vm"},
    "smc777": {"id": 273, "name": "SMC-777", "moby_slug": "smc-777"},
    "snes": {"id": 15, "name": "SNES", "moby_slug": "snes"},
    "sfam": {"id": 15, "name": "SNES", "moby_slug": "sfam"},
    "sri500": {"id": 242, "name": "SRI-500/1000", "moby_slug": "sri-5001000"},
    "swtpc6800": {"id": 228, "name": "SWTPC 6800", "moby_slug": "swtpc-6800"},
    "x1": {"id": 121, "name": "Sharp X1", "moby_slug": "sharp-x1"},
    "x68000": {"id": 106, "name": "Sharp X68000", "moby_slug": "sharp-x68000"},
    "zaurus": {"id": 202, "name": "Sharp Zaurus", "moby_slug": "sharp-zaurus"},
    "signetics2650": {
        "id": 278,
        "name": "Signetics 2650",
        "moby_slug": "signetics-2650",
    },
    "sinclairql": {"id": 131, "name": "Sinclair QL", "moby_slug": "sinclair-ql"},
    "socrates": {"id": 190, "name": "Socrates", "moby_slug": "socrates"},
    "sol20": {"id": 199, "name": "Sol-20", "moby_slug": "sol-20"},
    "sordm5": {"id": 134, "name": "Sord M5", "moby_slug": "sord-m5"},
    "spectravideo": {"id": 85, "name": "Spectravideo", "moby_slug": "spectravideo"},
    "stadia": {"id": 281, "name": "Stadia", "moby_slug": "stadia"},
    "superacan": {"id": 110, "name": "Super A'can", "moby_slug": "super-acan"},
    "supervision8000": {
        "id": 296,
        "name": "Super Vision 8000",
        "moby_slug": "super-vision-8000",
    },
    "supergrafx": {"id": 127, "name": "SuperGrafx", "moby_slug": "supergrafx"},
    "supervision": {"id": 109, "name": "Supervision", "moby_slug": "supervision"},
    "sureshothd": {"id": 287, "name": "Sure Shot HD", "moby_slug": "sure-shot-hd"},
    "symbian": {"id": 67, "name": "Symbian", "moby_slug": "symbian"},
    "tads": {"id": 171, "name": "TADS", "moby_slug": "tads"},
    "tipc": {
        "id": 239,
        "name": "TI Programmable Calculator",
        "moby_slug": "ti-programmable-calculator",
    },
    "ti99": {"id": 47, "name": "TI-99/4A", "moby_slug": "ti-99"},
    "tim": {"id": 246, "name": "TIM", "moby_slug": "tim"},
    "trs80": {"id": 58, "name": "TRS-80", "moby_slug": "trs-80"},
    "coco": {
        "id": 62,
        "name": "TRS-80 Color Computer",
        "moby_slug": "trs-80-coco",
    },
    "trs80mc10": {"id": 193, "name": "TRS-80 MC-10", "moby_slug": "trs-80-mc-10"},
    "trs80model100": {
        "id": 312,
        "name": "TRS-80 Model 100",
        "moby_slug": "trs-80-model-100",
    },
    "x55": {"id": 283, "name": "Taito X-55", "moby_slug": "taito-x-55"},
    "tatungeinstein": {
        "id": 150,
        "name": "Tatung Einstein",
        "moby_slug": "tatung-einstein",
    },
    "tektronix4050": {
        "id": 223,
        "name": "Tektronix 4050",
        "moby_slug": "tektronix-4050",
    },
    "telespiel": {"id": 220, "name": "Tele-Spiel ES-2201", "moby_slug": "tele-spiel"},
    "telstar-arcade": {
        "id": 233,
        "name": "Telstar Arcade",
        "moby_slug": "telstar-arcade",
    },
    "terminal": {"id": 209, "name": "Terminal", "moby_slug": "terminal"},
    "thomsonmo": {"id": 147, "name": "Thomson MO", "moby_slug": "thomson-mo"},
    "thomsonto": {"id": 130, "name": "Thomson TO", "moby_slug": "thomson-to"},
    "tiki100": {"id": 263, "name": "Tiki 100", "moby_slug": "tiki-100"},
    "timex2068": {
        "id": 173,
        "name": "Timex Sinclair 2068",
        "moby_slug": "timex-sinclair-2068",
    },
    "tizen": {"id": 206, "name": "Tizen", "moby_slug": "tizen"},
    "tomahawk-f1": {"id": 256, "name": "Tomahawk F1", "moby_slug": "tomahawk-f1"},
    "tutor": {"id": 151, "name": "Tomy Tutor", "moby_slug": "tomy-tutor"},
    "triton": {"id": 310, "name": "Triton", "moby_slug": "triton"},
    "pcenginecd": {"id": 45, "name": "TurboGrafx CD", "moby_slug": "turbografx-cd"},
    "pcengine": {"id": 40, "name": "TurboGrafx-16", "moby_slug": "turbo-grafx"},
    "vflash": {"id": 189, "name": "V.Flash", "moby_slug": "vflash"},
    "vsmile": {"id": 42, "name": "V.Smile", "moby_slug": "vsmile"},
    "c20": {"id": 43, "name": "VIC-20", "moby_slug": "vic-20"},
    "vis": {"id": 164, "name": "VIS", "moby_slug": "vis"},
    "vectrex": {"id": 37, "name": "Vectrex", "moby_slug": "vectrex"},
    "versatile": {"id": 299, "name": "Versatile", "moby_slug": "versatile"},
    "videobrain": {"id": 214, "name": "VideoBrain", "moby_slug": "videobrain"},
    "videopacplus": {
        "id": 128,
        "name": "Videopac+ G7400",
        "moby_slug": "videopac-g7400",
    },
    "virtualboy": {"id": 38, "name": "Virtual Boy", "moby_slug": "virtual-boy"},
    "wipi": {"id": 260, "name": "WIPI", "moby_slug": "wipi"},
    "wang2200": {"id": 217, "name": "Wang 2200", "moby_slug": "wang2200"},
    "wii": {"id": 82, "name": "Wii", "moby_slug": "wii"},
    "wiiu": {"id": 132, "name": "Wii U", "moby_slug": "wii-u"},
    "win": {"id": 3, "name": "Windows", "moby_slug": "windows"},
    "win3x": {"id": 5, "name": "Windows 3.x", "moby_slug": "win3x"},
    "windowsapps": {"id": 140, "name": "Windows Apps", "moby_slug": "windows-apps"},
    "windowsmobile": {"id": 66, "name": "Windows Mobile", "moby_slug": "windowsmobile"},
    "winphone": {"id": 98, "name": "Windows Phone", "moby_slug": "windows-phone"},
    "wswan": {"id": 48, "name": "WonderSwan", "moby_slug": "wonderswan"},
    "wswanc": {
        "id": 49,
        "name": "WonderSwan Color",
        "moby_slug": "wonderswan-color",
    },
    "xavixport": {"id": 191, "name": "XaviXPORT", "moby_slug": "xavixport"},
    "xbox": {"id": 13, "name": "Xbox", "moby_slug": "xbox"},
    "xbox360": {"id": 69, "name": "Xbox 360", "moby_slug": "xbox360"},
    "xboxcloudgaming": {
        "id": 293,
        "name": "Xbox Cloud Gaming",
        "moby_slug": "xboxcloudgaming",
    },
    "xboxone": {"id": 142, "name": "Xbox One", "moby_slug": "xbox-one"},
    "seriesxs": {"id": 289, "name": "Xbox Series", "moby_slug": "xbox-series"},
    "xerox-alto": {"id": 254, "name": "Xerox Alto", "moby_slug": "xerox-alto"},
    "zmachine": {"id": 169, "name": "Z-machine", "moby_slug": "z-machine"},
    "zxs": {"id": 41, "name": "ZX Spectrum", "moby_slug": "zx-spectrum"},
    "zxsnext": {
        "id": 280,
        "name": "ZX Spectrum Next",
        "moby_slug": "zx-spectrum-next",
    },
    "zx80": {"id": 118, "name": "ZX80", "moby_slug": "zx80"},
    "zx81": {"id": 119, "name": "ZX81", "moby_slug": "zx81"},
    "zeebo": {"id": 88, "name": "Zeebo", "moby_slug": "zeebo"},
    "z80": {"id": 227, "name": "Zilog Z80", "moby_slug": "z80"},
    "z8000": {"id": 276, "name": "Zilog Z8000", "moby_slug": "zilog-z8000"},
    "zodiac": {"id": 68, "name": "Zodiac", "moby_slug": "zodiac"},
    "zune": {"id": 211, "name": "Zune", "moby_slug": "zune"},
    "bada": {"id": 99, "name": "bada", "moby_slug": "bada"},
    "digiblast": {"id": 187, "name": "digiBlast", "moby_slug": "digiblast"},
    "ipad": {"id": 96, "name": "iPad", "moby_slug": "ipad"},
    "iphone": {"id": 86, "name": "iPhone", "moby_slug": "iphone"},
    "ios": {"id": 86, "name": "iOS", "moby_slug": "ios"},
    "ipod": {"id": 80, "name": "iPod Classic", "moby_slug": "ipod-classic"},
    "iircade": {"id": 314, "name": "iiRcade", "moby_slug": "iircade"},
    "tvos": {"id": 179, "name": "tvOS", "moby_slug": "tvos"},
    "watchos": {"id": 180, "name": "watchOS", "moby_slug": "watchos"},
    "webos": {"id": 100, "name": "webOS", "moby_slug": "webos"},
}

# Reverse lookup
MOBY_ID_TO_MOBY_PLATFORM = {v["id"]: k for k, v in SLUG_TO_MOBY_PLATFORM.items()}
