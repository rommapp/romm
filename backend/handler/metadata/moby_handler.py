import asyncio
import http
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
        self.platform_url = f"{self.BASE_URL}/platforms"
        self.games_url = f"{self.BASE_URL}/games"

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
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.UNAUTHORIZED:
                # Sometimes Mobygames returns 401 even with a valid API key
                log.error(err)
                return {}
            elif err.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
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
        except (httpx.HTTPStatusError, httpx.TimeoutException) as err:
            if (
                isinstance(err, httpx.HTTPStatusError)
                and err.response.status_code == http.HTTPStatus.UNAUTHORIZED
            ):
                # Sometimes Mobygames returns 401 even with a valid API key
                return {}
            # Log the error and return an empty dict if the request fails with a different code
            log.error(err)
            return {}

        return res.json()

    async def _search_rom(self, search_term: str, platform_moby_id: int) -> dict | None:
        if not platform_moby_id:
            return None

        search_term = uc(search_term)
        url = yarl.URL(self.games_url).with_query(
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
        platform = SLUG_TO_MOBY_ID.get(slug, None)

        if not platform:
            return MobyGamesPlatform(moby_id=None, slug=slug)

        return MobyGamesPlatform(
            moby_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, file_name: str, platform_moby_id: int) -> MobyGamesRom:
        from handler.filesystem import fs_rom_handler

        if not MOBY_API_ENABLED:
            return MobyGamesRom(moby_id=None)

        if not platform_moby_id:
            return MobyGamesRom(moby_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = MobyGamesRom(moby_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(file_name)
        if platform_moby_id == PS2_MOBY_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = MobyGamesRom(moby_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(file_name, re.IGNORECASE)
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
        match = SWITCH_TITLEDB_REGEX.search(file_name)
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
        match = SWITCH_PRODUCT_ID_REGEX.search(file_name)
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
            "slug": res["moby_url"].split("/")[-1],
            "summary": res.get("description", ""),
            "url_cover": pydash.get(res, "sample_cover.image", ""),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return MobyGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, moby_id: int) -> MobyGamesRom:
        if not MOBY_API_ENABLED:
            return MobyGamesRom(moby_id=None)

        url = yarl.URL(self.games_url).with_query(id=moby_id)
        roms = (await self._request(str(url))).get("games", [])
        res = pydash.get(roms, "[0]", None)

        if not res:
            return MobyGamesRom(moby_id=None)

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "slug": res["moby_url"].split("/")[-1],
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
        self, search_term: str, platform_moby_id: int
    ) -> list[MobyGamesRom]:
        if not MOBY_API_ENABLED:
            return []

        if not platform_moby_id:
            return []

        search_term = uc(search_term)
        url = yarl.URL(self.games_url).with_query(
            platform=[platform_moby_id], title=quote(search_term, safe="/ ")
        )
        matched_roms = (await self._request(str(url))).get("games", [])

        return [
            MobyGamesRom(  # type: ignore[misc]
                {
                    k: v
                    for k, v in {
                        "moby_id": rom["game_id"],
                        "name": rom["title"],
                        "slug": rom["moby_url"].split("/")[-1],
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


class SlugToMobyId(TypedDict):
    id: int
    name: str


SLUG_TO_MOBY_ID: dict[str, SlugToMobyId] = {
    "1292-advanced-programmable-video-system": {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
    },
    "3do": {"id": 35, "name": "3DO"},
    "abc-80": {"id": 318, "name": "ABC 80"},
    "apf": {"id": 213, "name": "APF MP1000/Imagination Machine"},
    "acorn-32-bit": {"id": 117, "name": "Acorn 32-bit"},
    "acorn-archimedes": {"id": 117, "name": "Acorn Archimedes"},  # IGDB
    "adventure-vision": {"id": 210, "name": "Adventure Vision"},
    "airconsole": {"id": 305, "name": "AirConsole"},
    "alice-3290": {"id": 194, "name": "Alice 32/90"},
    "altair-680": {"id": 265, "name": "Altair 680"},
    "altair-8800": {"id": 222, "name": "Altair 8800"},
    "amazon-alexa": {"id": 237, "name": "Amazon Alexa"},
    "amiga": {"id": 19, "name": "Amiga"},
    "amiga-cd32": {"id": 56, "name": "Amiga CD32"},
    "cpc": {"id": 60, "name": "Amstrad CPC"},
    "acpc": {"id": 60, "name": "Amstrad CPC"},  # IGDB
    "amstrad-pcw": {"id": 136, "name": "Amstrad PCW"},
    "android": {"id": 91, "name": "Android"},
    "antstream": {"id": 286, "name": "Antstream"},
    "apple-i": {"id": 245, "name": "Apple I"},
    "apple2": {"id": 31, "name": "Apple II"},
    "appleii": {"id": 31, "name": "Apple II"},  # IGDB
    "apple2gs": {"id": 51, "name": "Apple IIGD"},
    "apple-iigs": {"id": 51, "name": "Apple IIGD"},  # IGDB
    "arcade": {"id": 143, "name": "Arcade"},
    "arcadia-2001": {"id": 162, "name": "Arcadia 2001"},
    "arduboy": {"id": 215, "name": "Arduboy"},
    "astral-2000": {"id": 241, "name": "Astral 2000"},
    "atari-2600": {"id": 28, "name": "Atari 2600"},
    "atari2600": {"id": 28, "name": "Atari 2600"},  # IGDB
    "atari-5200": {"id": 33, "name": "Atari 5200"},
    "atari5200": {"id": 33, "name": "Atari 5200"},  # IGDB
    "atari-7800": {"id": 34, "name": "Atari 7800"},
    "atari7800": {"id": 34, "name": "Atari 7800"},  # IGDB
    "atari-8-bit": {"id": 39, "name": "Atari 8-bit"},
    "atari8bit": {"id": 39, "name": "Atari 8-bit"},  # IGDB
    "atari-st": {"id": 24, "name": "Atari ST"},
    "atari-vcs": {"id": 319, "name": "Atari VCS"},
    "atom": {"id": 129, "name": "Atom"},
    "bbc-micro": {"id": 92, "name": "BBC Micro"},
    "bbcmicro": {"id": 92, "name": "BBC Micro"},  # IGDB
    "brew": {"id": 63, "name": "BREW"},
    "bally-astrocade": {"id": 160, "name": "Bally Astrocade"},
    "astrocade": {"id": 160, "name": "Bally Astrocade"},  # IGDB
    "beos": {"id": 165, "name": "BeOS"},
    "blackberry": {"id": 90, "name": "BlackBerry"},
    "blacknut": {"id": 290, "name": "Blacknut"},
    "blu-ray-disc-player": {"id": 168, "name": "Blu-ray Player"},
    "blu-ray-player": {"id": 169, "name": "Blu-ray Player"},  # IGDB
    "browser": {"id": 84, "name": "Browser"},
    "bubble": {"id": 231, "name": "Bubble"},
    "cd-i": {"id": 73, "name": "CD-i"},
    "philips-cd-i": {"id": 73, "name": "CD-i"},  # IGDB
    "cdtv": {"id": 83, "name": "CDTV"},
    "commodore-cdtv": {"id": 83, "name": "CDTV"},  # IGDB
    "fred-cosmac": {"id": 216, "name": "COSMAC"},
    "camputers-lynx": {"id": 154, "name": "Camputers Lynx"},
    "cpm": {"id": 261, "name": "CP/M"},
    "casio-loopy": {"id": 124, "name": "Casio Loopy"},
    "casio-pv-1000": {"id": 125, "name": "Casio PV-1000"},
    "casio-programmable-calculator": {
        "id": 306,
        "name": "Casio Programmable Calculator",
    },
    "champion-2711": {"id": 298, "name": "Champion 2711"},
    "channel-f": {"id": 76, "name": "Channel F"},
    "fairchild-channel-f": {"id": 76, "name": "Channel F"},  # IGDB
    "clickstart": {"id": 188, "name": "ClickStart"},
    "colecoadam": {"id": 156, "name": "Coleco Adam"},
    "colecovision": {"id": 29, "name": "ColecoVision"},
    "colour-genie": {"id": 197, "name": "Colour Genie"},
    "c128": {"id": 61, "name": "Commodore 128"},
    "commodore-16-plus4": {"id": 115, "name": "Commodore 16, Plus/4"},
    "c-plus-4": {"id": 115, "name": "Commodore Plus/4"},  # IGDB
    "c16": {"id": 115, "name": "Commodore 16"},  # IGDB
    "c64": {"id": 27, "name": "Commodore 64"},
    "pet": {"id": 77, "name": "Commodore PET/CBM"},
    "cpet": {"id": 77, "name": "Commodore PET/CBM"},  # IGDB
    "compal-80": {"id": 277, "name": "Compal 80"},
    "compucolor-i": {"id": 243, "name": "Compucolor I"},
    "compucolor-ii": {"id": 198, "name": "Compucolor II"},
    "compucorp-programmable-calculator": {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
    },
    "creativision": {"id": 212, "name": "CreatiVision"},
    "cybervision": {"id": 301, "name": "Cybervision"},
    "dos": {"id": 2, "name": "DOS"},
    "dvd-player": {"id": 166, "name": "DVD Player"},
    "danger-os": {"id": 285, "name": "Danger OS"},
    "dedicated-console": {"id": 204, "name": "Dedicated console"},
    "dedicated-handheld": {"id": 205, "name": "Dedicated handheld"},
    "didj": {"id": 184, "name": "Didj"},
    "doja": {"id": 72, "name": "DoJa"},
    "dragon-3264": {"id": 79, "name": "Dragon 32/64"},
    "dragon-32-slash-64": {"id": 79, "name": "Dragon 32/64"},  # IGDB
    "dreamcast": {"id": 8, "name": "Dreamcast"},
    "dc": {"id": 8, "name": "Dreamcast"},  # IGDB
    "ecd-micromind": {"id": 269, "name": "ECD Micromind"},
    "electron": {"id": 93, "name": "Electron"},
    "acorn-electron": {"id": 93, "name": "Electron"},  # IGDB
    "enterprise": {"id": 161, "name": "Enterprise"},
    "epoch-cassette-vision": {"id": 137, "name": "Epoch Cassette Vision"},
    "epoch-game-pocket-computer": {"id": 139, "name": "Epoch Game Pocket Computer"},
    "epoch-super-cassette-vision": {"id": 138, "name": "Epoch Super Cassette Vision"},
    "evercade": {"id": 284, "name": "Evercade"},
    "exen": {"id": 70, "name": "ExEn"},
    "exelvision": {"id": 195, "name": "Exelvision"},
    "exidy-sorcerer": {"id": 176, "name": "Exidy Sorcerer"},
    "fmtowns": {"id": 102, "name": "FM Towns"},
    "fm-towns": {"id": 102, "name": "FM Towns"},  # IGDB
    "fm-7": {"id": 126, "name": "FM-7"},
    "mobile-custom": {"id": 315, "name": "Feature phone"},
    "fire-os": {"id": 159, "name": "Fire OS"},
    "amazon-fire-tv": {"id": 159, "name": "Fire TV"},
    "freebox": {"id": 268, "name": "Freebox"},
    "g-and-w": {"id": 205, "name": "Dedicated handheld"},  # IGDB (Game & Watch)
    "g-cluster": {"id": 302, "name": "G-cluster"},
    "gimini": {"id": 251, "name": "GIMINI"},
    "gnex": {"id": 258, "name": "GNEX"},
    "gp2x": {"id": 122, "name": "GP2X"},
    "gp2x-wiz": {"id": 123, "name": "GP2X Wiz"},
    "gp32": {"id": 108, "name": "GP32"},
    "gvm": {"id": 257, "name": "GVM"},
    "galaksija": {"id": 236, "name": "Galaksija"},
    "gameboy": {"id": 10, "name": "Game Boy"},
    "gb": {"id": 10, "name": "Game Boy"},  # IGDB
    "gameboy-advance": {"id": 12, "name": "Game Boy Advance"},
    "gba": {"id": 12, "name": "Game Boy Advance"},  # IGDB
    "gameboy-color": {"id": 11, "name": "Game Boy Color"},
    "gbc": {"id": 11, "name": "Game Boy Color"},  # IGDB
    "game-gear": {"id": 25, "name": "Game Gear"},
    "gamegear": {"id": 25, "name": "Game Gear"},  # IGDB
    "game-wave": {"id": 104, "name": "Game Wave"},
    "game-com": {"id": 50, "name": "Game.Com"},
    "game-dot-com": {"id": 50, "name": "Game.Com"},  # IGDB
    "gamecube": {"id": 14, "name": "GameCube"},
    "ngc": {"id": 14, "name": "GameCube"},  # IGDB
    "gamestick": {"id": 155, "name": "GameStick"},
    "genesis": {"id": 16, "name": "Genesis/Mega Drive"},
    "genesis-slash-megadrive": {"id": 16, "name": "Genesis/Mega Drive"},
    "gizmondo": {"id": 55, "name": "Gizmondo"},
    "gloud": {"id": 292, "name": "Gloud"},
    "glulx": {"id": 172, "name": "Glulx"},
    "hd-dvd-player": {"id": 167, "name": "HD DVD Player"},
    "hp-9800": {"id": 219, "name": "HP 9800"},
    "hp-programmable-calculator": {"id": 234, "name": "HP Programmable Calculator"},
    "heathzenith": {"id": 262, "name": "Heath/Zenith H8/H89"},
    "heathkit-h11": {"id": 248, "name": "Heathkit H11"},
    "hitachi-s1": {"id": 274, "name": "Hitachi S1"},
    "hugo": {"id": 170, "name": "Hugo"},
    "hyperscan": {"id": 192, "name": "HyperScan"},
    "ibm-5100": {"id": 250, "name": "IBM 5100"},
    "ideal-computer": {"id": 252, "name": "Ideal-Computer"},
    "intel-8008": {"id": 224, "name": "Intel 8008"},
    "intel-8080": {"id": 225, "name": "Intel 8080"},
    "intel-8086": {"id": 317, "name": "Intel 8086 / 8088"},
    "intellivision": {"id": 30, "name": "Intellivision"},
    "interact-model-one": {"id": 295, "name": "Interact Model One"},
    "interton-video-2000": {"id": 221, "name": "Interton Video 2000"},
    "j2me": {"id": 64, "name": "J2ME"},
    "jaguar": {"id": 17, "name": "Jaguar"},
    "jolt": {"id": 247, "name": "Jolt"},
    "jupiter-ace": {"id": 153, "name": "Jupiter Ace"},
    "kim-1": {"id": 226, "name": "KIM-1"},
    "kaios": {"id": 313, "name": "KaiOS"},
    "kindle": {"id": 145, "name": "Kindle Classic"},
    "laser200": {"id": 264, "name": "Laser 200"},
    "laseractive": {"id": 163, "name": "LaserActive"},
    "leapfrog-explorer": {"id": 185, "name": "LeapFrog Explorer"},
    "leapster-explorer-slash-leadpad-explorer": {
        "id": 186,
        "name": "Leapster Explorer/LeapPad Explorer",
    },
    "leaptv": {"id": 186, "name": "LeapTV"},
    "leapster": {"id": 183, "name": "Leapster"},
    "linux": {"id": 1, "name": "Linux"},
    "luna": {"id": 297, "name": "Luna"},
    "lynx": {"id": 18, "name": "Lynx"},
    "mos-technology-6502": {"id": 240, "name": "MOS Technology 6502"},
    "mre": {"id": 229, "name": "MRE"},
    "msx": {"id": 57, "name": "MSX"},
    "macintosh": {"id": 74, "name": "Macintosh"},
    "mac": {"id": 74, "name": "Macintosh"},  # IGDB
    "maemo": {"id": 157, "name": "Maemo"},
    "mainframe": {"id": 208, "name": "Mainframe"},
    "matsushitapanasonic-jr": {"id": 307, "name": "Matsushita/Panasonic JR"},
    "mattel-aquarius": {"id": 135, "name": "Mattel Aquarius"},
    "meego": {"id": 158, "name": "MeeGo"},
    "memotech-mtx": {"id": 148, "name": "Memotech MTX"},
    "meritum": {"id": 311, "name": "Meritum"},
    "microbee": {"id": 200, "name": "Microbee"},
    "microtan-65": {"id": 232, "name": "Microtan 65"},
    "microvision": {"id": 97, "name": "Microvision"},
    "microvision--1": {"id": 97, "name": "Microvision"},  # IGDB
    "mophun": {"id": 71, "name": "Mophun"},
    "motorola-6800": {"id": 235, "name": "Motorola 6800"},
    "motorola-68k": {"id": 275, "name": "Motorola 68k"},
    "ngage": {"id": 32, "name": "N-Gage"},
    "ngage2": {"id": 89, "name": "N-Gage (service)"},
    "nes": {"id": 22, "name": "NES"},
    "famicom": {"id": 22, "name": "NES"},
    "nascom": {"id": 175, "name": "Nascom"},
    "neo-geo": {"id": 36, "name": "Neo Geo"},
    "neogeoaes": {"id": 36, "name": "Neo Geo"},  # IGDB
    "neogeomvs": {"id": 36, "name": "Neo Geo"},  # IGDB
    "neo-geo-cd": {"id": 54, "name": "Neo Geo CD"},
    "neo-geo-pocket": {"id": 52, "name": "Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 53, "name": "Neo Geo Pocket Color"},
    "neo-geo-x": {"id": 279, "name": "Neo Geo X"},
    "new-nintendo-3ds": {"id": 174, "name": "New Nintendo 3DS"},
    "newbrain": {"id": 177, "name": "NewBrain"},
    "newton": {"id": 207, "name": "Newton"},
    "3ds": {"id": 101, "name": "Nintendo 3DS"},
    "n64": {"id": 9, "name": "Nintendo 64"},
    "nintendo-ds": {"id": 44, "name": "Nintendo DS"},
    "nds": {"id": 44, "name": "Nintendo DS"},  # IGDB
    "nintendo-dsi": {"id": 87, "name": "Nintendo DSi"},
    "switch": {"id": 203, "name": "Nintendo Switch"},
    "northstar": {"id": 266, "name": "North Star"},
    "noval-760": {"id": 244, "name": "Noval 760"},
    "nuon": {"id": 116, "name": "Nuon"},
    "ooparts": {"id": 300, "name": "OOParts"},
    "os2": {"id": 146, "name": "OS/2"},
    "oculus-go": {"id": 218, "name": "Oculus Go"},
    "odyssey": {"id": 75, "name": "Odyssey"},
    "odyssey--1": {"id": 75, "name": "Odyssey"},  # IGDB
    "odyssey-2": {"id": 78, "name": "Odyssey 2"},
    "odyssey-2-slash-videopac-g7000": {"id": 78, "name": "Odyssey 2/Videopac G7000"},
    "ohio-scientific": {"id": 178, "name": "Ohio Scientific"},
    "onlive": {"id": 282, "name": "OnLive"},
    "onlive-game-system": {"id": 282, "name": "OnLive Game System"},  # IGDB
    "orao": {"id": 270, "name": "Orao"},
    "oric": {"id": 111, "name": "Oric"},
    "ouya": {"id": 144, "name": "Ouya"},
    "pc-booter": {"id": 4, "name": "PC Booter"},
    "pc-6001": {"id": 149, "name": "PC-6001"},
    "pc-8000": {"id": 201, "name": "PC-8000"},
    "pc88": {"id": 94, "name": "PC-88"},
    "pc-8800-series": {"id": 94, "name": "PC-8800 Series"},  # IGDB
    "pc98": {"id": 95, "name": "PC-98"},
    "pc-9800-series": {"id": 95, "name": "PC-9800 Series"},  # IGDB
    "pc-fx": {"id": 59, "name": "PC-FX"},
    "pico": {"id": 316, "name": "PICO"},
    "ps-vita": {"id": 105, "name": "PS Vita"},
    "psvita": {"id": 105, "name": "PS Vita"},  # IGDB
    "psp": {"id": 46, "name": "PSP"},
    "palmos": {"id": 65, "name": "Palm OS"},
    "palm-os": {"id": 65, "name": "Palm OS"},  # IGDB
    "pandora": {"id": 308, "name": "Pandora"},
    "pebble": {"id": 304, "name": "Pebble"},
    "philips-vg-5000": {"id": 133, "name": "Philips VG 5000"},
    "photocd": {"id": 272, "name": "Photo CD"},
    "pippin": {"id": 112, "name": "Pippin"},
    "playstation": {"id": 6, "name": "PlayStation"},
    "ps": {"id": 6, "name": "PlayStation"},  # IGDB
    "ps2": {"id": 7, "name": "PlayStation 2"},
    "ps3": {"id": 81, "name": "PlayStation 3"},
    "playstation-4": {"id": 141, "name": "PlayStation 4"},
    "ps4--1": {"id": 141, "name": "PlayStation 4"},  # IGDB
    "playstation-5": {"id": 288, "name": "PlayStation 5"},
    "ps5": {"id": 288, "name": "PlayStation 5"},  # IGDB
    "playstation-now": {"id": 294, "name": "PlayStation Now"},
    "playdate": {"id": 303, "name": "Playdate"},
    "playdia": {"id": 107, "name": "Playdia"},
    "plex-arcade": {"id": 291, "name": "Plex Arcade"},
    "pokitto": {"id": 230, "name": "Pokitto"},
    "pokemon-mini": {"id": 152, "name": "Pokémon Mini"},
    "poly-88": {"id": 249, "name": "Poly-88"},
    "oculus-quest": {"id": 271, "name": "Quest"},
    "rca-studio-ii": {"id": 113, "name": "RCA Studio II"},
    "research-machines-380z": {"id": 309, "name": "Research Machines 380Z"},
    "roku": {"id": 196, "name": "Roku"},
    "sam-coupe": {"id": 120, "name": "SAM Coupé"},
    "scmp": {"id": 255, "name": "SC/MP"},
    "sd-200270290": {"id": 267, "name": "SD-200/270/290"},
    "sega-32x": {"id": 21, "name": "SEGA 32X"},
    "sega32": {"id": 21, "name": "SEGA 32X"},  # IGDB
    "sega-cd": {"id": 20, "name": "SEGA CD"},
    "segacd": {"id": 20, "name": "SEGA CD"},  # IGDB
    "sega-master-system": {"id": 26, "name": "SEGA Master System"},
    "sms": {"id": 26, "name": "SEGA Master System"},  # IGDB
    "sega-pico": {"id": 103, "name": "SEGA Pico"},
    "sega-saturn": {"id": 23, "name": "SEGA Saturn"},
    "saturn": {"id": 23, "name": "SEGA Saturn"},  # IGDB
    "sg-1000": {"id": 114, "name": "SG-1000"},
    "sk-vm": {"id": 259, "name": "SK-VM"},
    "smc-777": {"id": 273, "name": "SMC-777"},
    "snes": {"id": 15, "name": "SNES"},
    "sfam": {"id": 15, "name": "SNES"},
    "sri-5001000": {"id": 242, "name": "SRI-500/1000"},
    "swtpc-6800": {"id": 228, "name": "SWTPC 6800"},
    "sharp-mz-80b20002500": {"id": 182, "name": "Sharp MZ-80B/2000/2500"},
    "sharp-mz-80k7008001500": {"id": 181, "name": "Sharp MZ-80K/700/800/1500"},
    "sharp-x1": {"id": 121, "name": "Sharp X1"},
    "x1": {"id": 121, "name": "Sharp X1"},  # IGDB
    "sharp-x68000": {"id": 106, "name": "Sharp X68000"},
    "sharp-zaurus": {"id": 202, "name": "Sharp Zaurus"},
    "signetics-2650": {"id": 278, "name": "Signetics 2650"},
    "sinclair-ql": {"id": 131, "name": "Sinclair QL"},
    "socrates": {"id": 190, "name": "Socrates"},
    "sol-20": {"id": 199, "name": "Sol-20"},
    "sord-m5": {"id": 134, "name": "Sord M5"},
    "spectravideo": {"id": 85, "name": "Spectravideo"},
    "stadia": {"id": 281, "name": "Stadia"},
    "super-acan": {"id": 110, "name": "Super A'can"},
    "super-vision-8000": {"id": 296, "name": "Super Vision 8000"},
    "supergrafx": {"id": 127, "name": "SuperGrafx"},
    "supervision": {"id": 109, "name": "Supervision"},
    "sure-shot-hd": {"id": 287, "name": "Sure Shot HD"},
    "symbian": {"id": 67, "name": "Symbian"},
    "tads": {"id": 171, "name": "TADS"},
    "ti-programmable-calculator": {"id": 239, "name": "TI Programmable Calculator"},
    "ti-994a": {"id": 47, "name": "TI-99/4A"},
    "ti-99": {"id": 47, "name": "TI-99/4A"},  # IGDB
    "tim": {"id": 246, "name": "TIM"},
    "trs-80": {"id": 58, "name": "TRS-80"},
    "trs-80-coco": {"id": 62, "name": "TRS-80 Color Computer"},
    "trs-80-color-computer": {"id": 62, "name": "TRS-80 Color Computer"},  # IGDB
    "trs-80-mc-10": {"id": 193, "name": "TRS-80 MC-10"},
    "trs-80-model-100": {"id": 312, "name": "TRS-80 Model 100"},
    "taito-x-55": {"id": 283, "name": "Taito X-55"},
    "tatung-einstein": {"id": 150, "name": "Tatung Einstein"},
    "tektronix-4050": {"id": 223, "name": "Tektronix 4050"},
    "tele-spiel": {"id": 220, "name": "Tele-Spiel ES-2201"},
    "telstar-arcade": {"id": 233, "name": "Telstar Arcade"},
    "terminal": {"id": 209, "name": "Terminal"},
    "thomson-mo": {"id": 147, "name": "Thomson MO"},
    "thomson-mo5": {"id": 147, "name": "Thomson MO5"},
    "thomson-to": {"id": 130, "name": "Thomson TO"},
    "tiki-100": {"id": 263, "name": "Tiki 100"},
    "timex-sinclair-2068": {"id": 173, "name": "Timex Sinclair 2068"},
    "tizen": {"id": 206, "name": "Tizen"},
    "tomahawk-f1": {"id": 256, "name": "Tomahawk F1"},
    "tomy-tutor": {"id": 151, "name": "Tomy Tutor"},
    "triton": {"id": 310, "name": "Triton"},
    "turbografx-cd": {"id": 45, "name": "TurboGrafx CD"},
    "turbografx-16-slash-pc-engine-cd": {"id": 45, "name": "TurboGrafx CD"},
    "turbo-grafx": {"id": 40, "name": "TurboGrafx-16"},
    "turbografx16--1": {"id": 40, "name": "TurboGrafx-16"},  # IGDB
    "vflash": {"id": 189, "name": "V.Flash"},
    "vsmile": {"id": 42, "name": "V.Smile"},
    "vic-20": {"id": 43, "name": "VIC-20"},
    "vis": {"id": 164, "name": "VIS"},
    "vectrex": {"id": 37, "name": "Vectrex"},
    "versatile": {"id": 299, "name": "Versatile"},
    "videobrain": {"id": 214, "name": "VideoBrain"},
    "videopac-g7400": {"id": 128, "name": "Videopac+ G7400"},
    "virtual-boy": {"id": 38, "name": "Virtual Boy"},
    "virtualboy": {"id": 38, "name": "Virtual Boy"},
    "wipi": {"id": 260, "name": "WIPI"},
    "wang2200": {"id": 217, "name": "Wang 2200"},
    "wii": {"id": 82, "name": "Wii"},
    "wii-u": {"id": 132, "name": "Wii U"},
    "wiiu": {"id": 132, "name": "Wii U"},
    "windows": {"id": 3, "name": "Windows"},
    "win": {"id": 3, "name": "Windows"},  # IGDB
    "win3x": {"id": 5, "name": "Windows 3.x"},
    "windows-apps": {"id": 140, "name": "Windows Apps"},
    "windowsmobile": {"id": 66, "name": "Windows Mobile"},
    "windows-mobile": {"id": 66, "name": "Windows Mobile"},  # IGDB
    "windows-phone": {"id": 98, "name": "Windows Phone"},
    "winphone": {"id": 98, "name": "Windows Phone"},  # IGDB
    "wonderswan": {"id": 48, "name": "WonderSwan"},
    "wonderswan-color": {"id": 49, "name": "WonderSwan Color"},
    "xavixport": {"id": 191, "name": "XaviXPORT"},
    "xbox": {"id": 13, "name": "Xbox"},
    "xbox360": {"id": 69, "name": "Xbox 360"},
    "xboxcloudgaming": {"id": 293, "name": "Xbox Cloud Gaming"},
    "xbox-one": {"id": 142, "name": "Xbox One"},
    "xboxone": {"id": 142, "name": "Xbox One"},
    "xbox-series": {"id": 289, "name": "Xbox Series"},
    "series-x": {"id": 289, "name": "Xbox Series X"},  # IGDB
    "xerox-alto": {"id": 254, "name": "Xerox Alto"},
    "z-machine": {"id": 169, "name": "Z-machine"},
    "zx-spectrum": {"id": 41, "name": "ZX Spectrum"},
    "zx-spectrum-next": {"id": 280, "name": "ZX Spectrum Next"},
    "zx80": {"id": 118, "name": "ZX80"},
    "zx81": {"id": 119, "name": "ZX81"},
    "sinclair-zx81": {"id": 119, "name": "ZX81"},  # IGDB
    "zeebo": {"id": 88, "name": "Zeebo"},
    "z80": {"id": 227, "name": "Zilog Z80"},
    "zilog-z8000": {"id": 276, "name": "Zilog Z8000"},
    "zodiac": {"id": 68, "name": "Zodiac"},
    "zune": {"id": 211, "name": "Zune"},
    "bada": {"id": 99, "name": "bada"},
    "digiblast": {"id": 187, "name": "digiBlast"},
    "ipad": {"id": 96, "name": "iPad"},
    "iphone": {"id": 86, "name": "iPhone"},
    "ios": {"id": 86, "name": "iOS"},
    "ipod-classic": {"id": 80, "name": "iPod Classic"},
    "iircade": {"id": 314, "name": "iiRcade"},
    "tvos": {"id": 179, "name": "tvOS"},
    "watchos": {"id": 180, "name": "watchOS"},
    "webos": {"id": 100, "name": "webOS"},
}

# Reverse lookup
MOBY_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_MOBY_ID.items()}
