import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import pydash
from adapters.services.mobygames import MobyGamesService
from adapters.services.mobygames_types import MobyGame
from config import MOBYGAMES_API_KEY
from unidecode import unidecode as uc

from .base_hander import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    BaseRom,
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


class MobyGamesRom(BaseRom):
    moby_id: int | None
    moby_metadata: NotRequired[MobyMetadata]


def extract_metadata_from_moby_rom(rom: MobyGame) -> MobyMetadata:
    return MobyMetadata(
        {
            "moby_score": str(rom.get("moby_score", "")),
            "genres": [genre["genre_name"] for genre in rom.get("genres", [])],
            "alternate_titles": [
                alt["title"] for alt in rom.get("alternate_titles", [])
            ],
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
        self.moby_service = MobyGamesService()

    async def _search_rom(
        self, search_term: str, platform_moby_id: int
    ) -> MobyGame | None:
        if not platform_moby_id:
            return None

        roms = await self.moby_service.list_games(
            platform_ids=[platform_moby_id],
            title=quote(uc(search_term), safe="/ "),
        )
        if not roms:
            return None

        # Find an exact match.
        search_term_casefold = search_term.casefold()
        for rom in roms:
            if (
                rom["title"].casefold() == search_term_casefold
                or self.normalize_search_term(rom["title"]) == search_term
            ):
                return rom

        return roms[0]

    def get_platform(self, slug: str) -> MobyGamesPlatform:
        platform = MOBYGAMES_PLATFORM_LIST.get(slug, None)

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

        normalized_search_term = self.normalize_search_term(search_term)
        res = await self._search_rom(normalized_search_term, platform_moby_id)

        # Moby API doesn't handle some special characters well
        if not res and (
            ": " in search_term or " - " in search_term or "/" in search_term
        ):
            if ":" in search_term:
                terms = [
                    s.strip() for s in search_term.split(":") if len(s.strip()) > 2
                ]
            elif " - " in search_term:
                terms = [
                    s.strip() for s in search_term.split(" - ") if len(s.strip()) > 2
                ]
            else:
                terms = [
                    s.strip() for s in search_term.split("/") if len(s.strip()) > 2
                ]

            for i in range(len(terms) - 1, -1, -1):
                res = await self._search_rom(terms[i], platform_moby_id)
                if res:
                    break

        if not res:
            return fallback_rom

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "summary": res.get("description", ""),
            "url_cover": pydash.get(res, "sample_cover.image", None),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return MobyGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, moby_id: int) -> MobyGamesRom:
        if not MOBY_API_ENABLED:
            return MobyGamesRom(moby_id=None)

        roms = await self.moby_service.list_games(game_id=moby_id)
        if not roms:
            return MobyGamesRom(moby_id=None)

        res = roms[0]
        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
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

        matched_roms = await self.moby_service.list_games(
            platform_ids=[platform_moby_id],
            title=quote(uc(search_term), safe="/ "),
        )

        return [
            MobyGamesRom(
                {  # type: ignore[misc]
                    k: v
                    for k, v in {
                        "moby_id": rom["game_id"],
                        "name": rom["title"],
                        "summary": rom.get("description", ""),
                        "url_cover": pydash.get(rom, "sample_cover.image", None),
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
    slug: str


MOBYGAMES_PLATFORM_LIST: dict[UniversalPlatformSlug, SlugToMobyId] = {
    UniversalPlatformSlug.APVS: {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
        "slug": "1292-advanced-programmable-video-system",
    },
    UniversalPlatformSlug._3DO: {"id": 35, "name": "3DO", "slug": "3do"},
    UniversalPlatformSlug.N3DS: {"id": 101, "name": "Nintendo 3DS", "slug": "3ds"},
    UniversalPlatformSlug.ABC_80: {"id": 318, "name": "ABC 80", "slug": "abc-80"},
    UniversalPlatformSlug.ACORN_ARCHIMEDES: {
        "id": 117,
        "name": "Acorn Archimedes",
        "slug": "acorn-32-bit",
    },
    UniversalPlatformSlug.ACORN_ELECTRON: {
        "id": 93,
        "name": "Electron",
        "slug": "electron",
    },
    UniversalPlatformSlug.ACPC: {"id": 60, "name": "Amstrad CPC", "slug": "cpc"},
    UniversalPlatformSlug.ADVENTURE_VISION: {
        "id": 210,
        "name": "Adventure Vision",
        "slug": "adventure-vision",
    },
    UniversalPlatformSlug.AIRCONSOLE: {
        "id": 305,
        "name": "AirConsole",
        "slug": "airconsole",
    },
    UniversalPlatformSlug.ALICE_3290: {
        "id": 194,
        "name": "Alice 32/90",
        "slug": "alice-3290",
    },
    UniversalPlatformSlug.ALTAIR_680: {
        "id": 265,
        "name": "Altair 680",
        "slug": "altair-680",
    },
    UniversalPlatformSlug.ALTAIR_8800: {
        "id": 222,
        "name": "Altair 8800",
        "slug": "altair-8800",
    },
    UniversalPlatformSlug.AMAZON_ALEXA: {
        "id": 237,
        "name": "Amazon Alexa",
        "slug": "amazon-alexa",
    },
    UniversalPlatformSlug.AMAZON_FIRE_TV: {
        "id": 159,
        "name": "Fire TV",
        "slug": "fire-os",
    },
    UniversalPlatformSlug.AMIGA: {"id": 19, "name": "Amiga", "slug": "amiga"},
    UniversalPlatformSlug.AMIGA_CD32: {
        "id": 56,
        "name": "Amiga CD32",
        "slug": "amiga-cd32",
    },
    UniversalPlatformSlug.AMSTRAD_PCW: {
        "id": 136,
        "name": "Amstrad PCW",
        "slug": "amstrad-pcw",
    },
    UniversalPlatformSlug.ANDROID: {"id": 91, "name": "Android", "slug": "android"},
    UniversalPlatformSlug.ANTSTREAM: {
        "id": 286,
        "name": "Antstream",
        "slug": "antstream",
    },
    UniversalPlatformSlug.APF: {
        "id": 213,
        "name": "APF MP1000/Imagination Machine",
        "slug": "apf",
    },
    UniversalPlatformSlug.APPLE: {"id": 245, "name": "Apple I", "slug": "apple-i"},
    UniversalPlatformSlug.APPLE_IIGS: {
        "id": 51,
        "name": "Apple IIGD",
        "slug": "apple2gs",
    },
    UniversalPlatformSlug.APPLEII: {"id": 31, "name": "Apple II", "slug": "apple2"},
    UniversalPlatformSlug.ARCADE: {"id": 143, "name": "Arcade", "slug": "arcade"},
    UniversalPlatformSlug.ARCADIA_2001: {
        "id": 162,
        "name": "Arcadia 2001",
        "slug": "arcadia-2001",
    },
    UniversalPlatformSlug.ARDUBOY: {"id": 215, "name": "Arduboy", "slug": "arduboy"},
    UniversalPlatformSlug.ASTRAL_2000: {
        "id": 241,
        "name": "Astral 2000",
        "slug": "astral-2000",
    },
    UniversalPlatformSlug.ASTROCADE: {
        "id": 160,
        "name": "Bally Astrocade",
        "slug": "bally-astrocade",
    },
    "atari-2600": {"id": 28, "name": "Atari 2600", "slug": "atari-2600"},
    "atari-5200": {"id": 33, "name": "Atari 5200", "slug": "atari-5200"},
    "atari-7800": {"id": 34, "name": "Atari 7800", "slug": "atari-7800"},
    "atari-8-bit": {"id": 39, "name": "Atari 8-bit", "slug": "atari-8-bit"},
    UniversalPlatformSlug.ATARI_ST: {"id": 24, "name": "Atari ST", "slug": "atari-st"},
    UniversalPlatformSlug.ATARI_VCS: {
        "id": 319,
        "name": "Atari VCS",
        "slug": "atari-vcs",
    },
    UniversalPlatformSlug.ATARI2600: {
        "id": 28,
        "name": "Atari 2600",
        "slug": "atari-2600",
    },
    UniversalPlatformSlug.ATARI5200: {
        "id": 33,
        "name": "Atari 5200",
        "slug": "atari-5200",
    },
    UniversalPlatformSlug.ATARI7800: {
        "id": 34,
        "name": "Atari 7800",
        "slug": "atari-7800",
    },
    UniversalPlatformSlug.ATARI8BIT: {
        "id": 39,
        "name": "Atari 8-bit",
        "slug": "atari-8-bit",
    },
    UniversalPlatformSlug.ATOM: {"id": 129, "name": "Atom", "slug": "atom"},
    UniversalPlatformSlug.BADA: {"id": 99, "name": "Bada", "slug": "bada"},
    UniversalPlatformSlug.BBCMICRO: {
        "id": 92,
        "name": "BBC Micro",
        "slug": "bbc-micro",
    },
    UniversalPlatformSlug.BEOS: {"id": 165, "name": "BeOS", "slug": "beos"},
    UniversalPlatformSlug.BLACKBERRY: {
        "id": 90,
        "name": "BlackBerry",
        "slug": "blackberry",
    },
    UniversalPlatformSlug.BLACKNUT: {"id": 290, "name": "Blacknut", "slug": "blacknut"},
    "blu-ray-disc-player": {
        "id": 168,
        "name": "Blu-ray Player",
        "slug": "blu-ray-disc-player",
    },
    UniversalPlatformSlug.BLU_RAY_PLAYER: {
        "id": 169,
        "name": "Blu-ray Player",
        "slug": "blu-ray-disc-player",
    },
    UniversalPlatformSlug.BREW: {"id": 63, "name": "BREW", "slug": "brew"},
    UniversalPlatformSlug.BROWSER: {"id": 84, "name": "Browser", "slug": "browser"},
    UniversalPlatformSlug.BUBBLE: {"id": 231, "name": "Bubble", "slug": "bubble"},
    UniversalPlatformSlug.C_PLUS_4: {
        "id": 115,
        "name": "Commodore Plus/4",
        "slug": "commodore-16-plus4",
    },
    UniversalPlatformSlug.C128: {"id": 61, "name": "Commodore 128", "slug": "c128"},
    UniversalPlatformSlug.C16: {
        "id": 115,
        "name": "Commodore 16",
        "slug": "commodore-16-plus4",
    },
    UniversalPlatformSlug.C64: {"id": 27, "name": "Commodore 64", "slug": "c64"},
    UniversalPlatformSlug.CAMPUTERS_LYNX: {
        "id": 154,
        "name": "Camputers Lynx",
        "slug": "camputers-lynx",
    },
    UniversalPlatformSlug.CASIO_LOOPY: {
        "id": 124,
        "name": "Casio Loopy",
        "slug": "casio-loopy",
    },
    UniversalPlatformSlug.CASIO_PROGRAMMABLE_CALCULATOR: {
        "id": 306,
        "name": "Casio Programmable Calculator",
        "slug": "casio-programmable-calculator",
    },
    UniversalPlatformSlug.CASIO_PV_1000: {
        "id": 125,
        "name": "Casio PV-1000",
        "slug": "casio-pv-1000",
    },
    UniversalPlatformSlug.CHAMPION_2711: {
        "id": 298,
        "name": "Champion 2711",
        "slug": "champion-2711",
    },
    UniversalPlatformSlug.CLICKSTART: {
        "id": 188,
        "name": "ClickStart",
        "slug": "clickstart",
    },
    UniversalPlatformSlug.COLECOADAM: {
        "id": 156,
        "name": "Coleco Adam",
        "slug": "colecoadam",
    },
    UniversalPlatformSlug.COLECOVISION: {
        "id": 29,
        "name": "ColecoVision",
        "slug": "colecovision",
    },
    UniversalPlatformSlug.COLOUR_GENIE: {
        "id": 197,
        "name": "Colour Genie",
        "slug": "colour-genie",
    },
    UniversalPlatformSlug.COMMODORE_CDTV: {"id": 83, "name": "CDTV", "slug": "cdtv"},
    UniversalPlatformSlug.COMPAL_80: {
        "id": 277,
        "name": "Compal 80",
        "slug": "compal-80",
    },
    UniversalPlatformSlug.COMPUCOLOR_I: {
        "id": 243,
        "name": "Compucolor I",
        "slug": "compucolor-i",
    },
    UniversalPlatformSlug.COMPUCOLOR_II: {
        "id": 198,
        "name": "Compucolor II",
        "slug": "compucolor-ii",
    },
    UniversalPlatformSlug.COMPUCORP_PROGRAMMABLE_CALCULATOR: {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
        "slug": "compucorp-programmable-calculator",
    },
    UniversalPlatformSlug.CPET: {"id": 77, "name": "Commodore PET/CBM", "slug": "pet"},
    UniversalPlatformSlug.CPM: {"id": 261, "name": "CP/M", "slug": "cpm"},
    UniversalPlatformSlug.CREATIVISION: {
        "id": 212,
        "name": "CreatiVision",
        "slug": "creativision",
    },
    UniversalPlatformSlug.CYBERVISION: {
        "id": 301,
        "name": "Cybervision",
        "slug": "cybervision",
    },
    UniversalPlatformSlug.DANGER_OS: {
        "id": 285,
        "name": "Danger OS",
        "slug": "danger-os",
    },
    UniversalPlatformSlug.DC: {"id": 8, "name": "Dreamcast", "slug": "dc"},
    UniversalPlatformSlug.DEDICATED_CONSOLE: {
        "id": 204,
        "name": "Dedicated console",
        "slug": "dedicated-console",
    },
    "dedicated-handheld": {
        "id": 205,
        "name": "Dedicated handheld",
        "slug": "dedicated-handheld",
    },
    UniversalPlatformSlug.DIDJ: {"id": 184, "name": "Didj", "slug": "didj"},
    UniversalPlatformSlug.DIGIBLAST: {
        "id": 187,
        "name": "digiBlast",
        "slug": "digiblast",
    },
    UniversalPlatformSlug.DOJA: {"id": 72, "name": "DoJa", "slug": "doja"},
    UniversalPlatformSlug.DOS: {"id": 2, "name": "DOS", "slug": "dos"},
    UniversalPlatformSlug.DRAGON_32_SLASH_64: {
        "id": 79,
        "name": "Dragon 32/64",
        "slug": "dragon-3264",
    },
    UniversalPlatformSlug.DVD_PLAYER: {
        "id": 166,
        "name": "DVD Player",
        "slug": "dvd-player",
    },
    UniversalPlatformSlug.ECD_MICROMIND: {
        "id": 269,
        "name": "ECD Micromind",
        "slug": "ecd-micromind",
    },
    UniversalPlatformSlug.ENTERPRISE: {
        "id": 161,
        "name": "Enterprise",
        "slug": "enterprise",
    },
    UniversalPlatformSlug.EPOCH_CASSETTE_VISION: {
        "id": 137,
        "name": "Epoch Cassette Vision",
        "slug": "epoch-cassette-vision",
    },
    UniversalPlatformSlug.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 139,
        "name": "Epoch Game Pocket Computer",
        "slug": "epoch-game-pocket-computer",
    },
    UniversalPlatformSlug.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 138,
        "name": "Epoch Super Cassette Vision",
        "slug": "epoch-super-cassette-vision",
    },
    UniversalPlatformSlug.EVERCADE: {"id": 284, "name": "Evercade", "slug": "evercade"},
    UniversalPlatformSlug.EXELVISION: {
        "id": 195,
        "name": "Exelvision",
        "slug": "exelvision",
    },
    UniversalPlatformSlug.EXEN: {"id": 70, "name": "ExEn", "slug": "exen"},
    UniversalPlatformSlug.EXIDY_SORCERER: {
        "id": 176,
        "name": "Exidy Sorcerer",
        "slug": "exidy-sorcerer",
    },
    UniversalPlatformSlug.FAIRCHILD_CHANNEL_F: {
        "id": 76,
        "name": "Channel F",
        "slug": "channel-f",
    },
    UniversalPlatformSlug.FAMICOM: {
        "id": 22,
        "name": "Family Computer",
        "slug": "famicom",
    },
    "fire-os": {"id": 159, "name": "Fire OS", "slug": "fire-os"},
    UniversalPlatformSlug.FM_7: {"id": 126, "name": "FM-7", "slug": "fm-7"},
    UniversalPlatformSlug.FM_TOWNS: {"id": 102, "name": "FM Towns", "slug": "fmtowns"},
    UniversalPlatformSlug.FRED_COSMAC: {
        "id": 216,
        "name": "COSMAC",
        "slug": "fred-cosmac",
    },
    UniversalPlatformSlug.FREEBOX: {"id": 268, "name": "Freebox", "slug": "freebox"},
    UniversalPlatformSlug.G_AND_W: {
        "id": 205,
        "name": "Dedicated handheld",
        "slug": "dedicated-handheld",
    },
    UniversalPlatformSlug.G_CLUSTER: {
        "id": 302,
        "name": "G-cluster",
        "slug": "g-cluster",
    },
    UniversalPlatformSlug.GALAKSIJA: {
        "id": 236,
        "name": "Galaksija",
        "slug": "galaksija",
    },
    UniversalPlatformSlug.GAME_DOT_COM: {
        "id": 50,
        "name": "Game.Com",
        "slug": "game-com",
    },
    UniversalPlatformSlug.GAME_WAVE: {
        "id": 104,
        "name": "Game Wave",
        "slug": "game-wave",
    },
    UniversalPlatformSlug.GAMEGEAR: {
        "id": 25,
        "name": "Game Gear",
        "slug": "game-gear",
    },
    UniversalPlatformSlug.GAMESTICK: {
        "id": 155,
        "name": "GameStick",
        "slug": "gamestick",
    },
    UniversalPlatformSlug.GB: {"id": 10, "name": "Game Boy", "slug": "gameboy"},
    UniversalPlatformSlug.GBA: {
        "id": 12,
        "name": "Game Boy Advance",
        "slug": "gameboy-advance",
    },
    UniversalPlatformSlug.GBC: {
        "id": 11,
        "name": "Game Boy Color",
        "slug": "gameboy-color",
    },
    UniversalPlatformSlug.GENESIS: {
        "id": 16,
        "name": "Genesis/Mega Drive",
        "slug": "genesis",
    },
    UniversalPlatformSlug.GIMINI: {"id": 251, "name": "GIMINI", "slug": "gimini"},
    UniversalPlatformSlug.GIZMONDO: {"id": 55, "name": "Gizmondo", "slug": "gizmondo"},
    UniversalPlatformSlug.GLOUD: {"id": 292, "name": "Gloud", "slug": "gloud"},
    UniversalPlatformSlug.GLULX: {"id": 172, "name": "Glulx", "slug": "glulx"},
    UniversalPlatformSlug.GNEX: {"id": 258, "name": "GNEX", "slug": "gnex"},
    UniversalPlatformSlug.GP2X: {"id": 122, "name": "GP2X", "slug": "gp2x"},
    UniversalPlatformSlug.GP2X_WIZ: {"id": 123, "name": "GP2X Wiz", "slug": "gp2x-wiz"},
    UniversalPlatformSlug.GP32: {"id": 108, "name": "GP32", "slug": "gp32"},
    UniversalPlatformSlug.GVM: {"id": 257, "name": "GVM", "slug": "gvm"},
    UniversalPlatformSlug.HD_DVD_PLAYER: {
        "id": 167,
        "name": "HD DVD Player",
        "slug": "hd-dvd-player",
    },
    UniversalPlatformSlug.HEATHKIT_H11: {
        "id": 248,
        "name": "Heathkit H11",
        "slug": "heathkit-h11",
    },
    UniversalPlatformSlug.HEATHZENITH: {
        "id": 262,
        "name": "Heath/Zenith H8/H89",
        "slug": "heathzenith",
    },
    UniversalPlatformSlug.HITACHI_S1: {
        "id": 274,
        "name": "Hitachi S1",
        "slug": "hitachi-s1",
    },
    UniversalPlatformSlug.HP_9800: {"id": 219, "name": "HP 9800", "slug": "hp-9800"},
    UniversalPlatformSlug.HP_PROGRAMMABLE_CALCULATOR: {
        "id": 234,
        "name": "HP Programmable Calculator",
        "slug": "hp-programmable-calculator",
    },
    UniversalPlatformSlug.HUGO: {"id": 170, "name": "Hugo", "slug": "hugo"},
    UniversalPlatformSlug.HYPERSCAN: {
        "id": 192,
        "name": "HyperScan",
        "slug": "hyperscan",
    },
    UniversalPlatformSlug.IBM_5100: {"id": 250, "name": "IBM 5100", "slug": "ibm-5100"},
    UniversalPlatformSlug.IDEAL_COMPUTER: {
        "id": 252,
        "name": "Ideal-Computer",
        "slug": "ideal-computer",
    },
    UniversalPlatformSlug.IIRCADE: {"id": 314, "name": "iiRcade", "slug": "iircade"},
    UniversalPlatformSlug.INTEL_8008: {
        "id": 224,
        "name": "Intel 8008",
        "slug": "intel-8008",
    },
    UniversalPlatformSlug.INTEL_8080: {
        "id": 225,
        "name": "Intel 8080",
        "slug": "intel-8080",
    },
    UniversalPlatformSlug.INTEL_8086: {
        "id": 317,
        "name": "Intel 8086 / 8088",
        "slug": "intel-8086",
    },
    UniversalPlatformSlug.INTELLIVISION: {
        "id": 30,
        "name": "Intellivision",
        "slug": "intellivision",
    },
    UniversalPlatformSlug.INTERACT_MODEL_ONE: {
        "id": 295,
        "name": "Interact Model One",
        "slug": "interact-model-one",
    },
    UniversalPlatformSlug.INTERTON_VIDEO_2000: {
        "id": 221,
        "name": "Interton Video 2000",
        "slug": "interton-video-2000",
    },
    UniversalPlatformSlug.IOS: {"id": 86, "name": "iOS", "slug": "iphone"},
    UniversalPlatformSlug.IPAD: {"id": 96, "name": "iPad", "slug": "ipad"},
    "iphone": {"id": 86, "name": "iPhone", "slug": "iphone"},
    UniversalPlatformSlug.IPOD_CLASSIC: {
        "id": 80,
        "name": "iPod Classic",
        "slug": "ipod-classic",
    },
    UniversalPlatformSlug.J2ME: {"id": 64, "name": "J2ME", "slug": "j2me"},
    UniversalPlatformSlug.JAGUAR: {"id": 17, "name": "Jaguar", "slug": "jaguar"},
    UniversalPlatformSlug.JOLT: {"id": 247, "name": "Jolt", "slug": "jolt"},
    UniversalPlatformSlug.JUPITER_ACE: {
        "id": 153,
        "name": "Jupiter Ace",
        "slug": "jupiter-ace",
    },
    UniversalPlatformSlug.KAIOS: {"id": 313, "name": "KaiOS", "slug": "kaios"},
    UniversalPlatformSlug.KIM_1: {"id": 226, "name": "KIM-1", "slug": "kim-1"},
    UniversalPlatformSlug.KINDLE: {
        "id": 145,
        "name": "Kindle Classic",
        "slug": "kindle",
    },
    UniversalPlatformSlug.LASER200: {
        "id": 264,
        "name": "Laser 200",
        "slug": "laser200",
    },
    UniversalPlatformSlug.LASERACTIVE: {
        "id": 163,
        "name": "LaserActive",
        "slug": "laseractive",
    },
    UniversalPlatformSlug.LEAPFROG_EXPLORER: {
        "id": 185,
        "name": "LeapFrog Explorer",
        "slug": "leapfrog-explorer",
    },
    UniversalPlatformSlug.LEAPSTER: {"id": 183, "name": "Leapster", "slug": "leapster"},
    UniversalPlatformSlug.LEAPSTER_EXPLORER_SLASH_LEADPAD_EXPLORER: {
        "id": 183,
        "name": "Leapster Explorer/LeapPad Explorer",
        "slug": "leapster",
    },
    UniversalPlatformSlug.LEAPTV: {"id": 186, "name": "LeapTV", "slug": "leaptv"},
    UniversalPlatformSlug.LINUX: {"id": 1, "name": "Linux", "slug": "linux"},
    UniversalPlatformSlug.LUNA: {"id": 297, "name": "Luna", "slug": "luna"},
    UniversalPlatformSlug.LYNX: {"id": 18, "name": "Lynx", "slug": "lynx"},
    UniversalPlatformSlug.MAC: {"id": 74, "name": "Macintosh", "slug": "macintosh"},
    UniversalPlatformSlug.MAEMO: {"id": 157, "name": "Maemo", "slug": "maemo"},
    UniversalPlatformSlug.MAINFRAME: {
        "id": 208,
        "name": "Mainframe",
        "slug": "mainframe",
    },
    UniversalPlatformSlug.MATSUSHITAPANASONIC_JR: {
        "id": 307,
        "name": "Matsushita/Panasonic JR",
        "slug": "matsushitapanasonic-jr",
    },
    UniversalPlatformSlug.MATTEL_AQUARIUS: {
        "id": 135,
        "name": "Mattel Aquarius",
        "slug": "mattel-aquarius",
    },
    UniversalPlatformSlug.MEEGO: {"id": 158, "name": "MeeGo", "slug": "meego"},
    UniversalPlatformSlug.MEMOTECH_MTX: {
        "id": 148,
        "name": "Memotech MTX",
        "slug": "memotech-mtx",
    },
    UniversalPlatformSlug.MERITUM: {"id": 311, "name": "Meritum", "slug": "meritum"},
    UniversalPlatformSlug.MICROBEE: {"id": 200, "name": "Microbee", "slug": "microbee"},
    UniversalPlatformSlug.MICROTAN_65: {
        "id": 232,
        "name": "Microtan 65",
        "slug": "microtan-65",
    },
    UniversalPlatformSlug.MICROVISION: {
        "id": 97,
        "name": "Microvision",
        "slug": "microvision",
    },
    UniversalPlatformSlug.MOBILE_CUSTOM: {
        "id": 315,
        "name": "Feature phone",
        "slug": "mobile-custom",
    },
    UniversalPlatformSlug.MOPHUN: {"id": 71, "name": "Mophun", "slug": "mophun"},
    UniversalPlatformSlug.MOS_TECHNOLOGY_6502: {
        "id": 240,
        "name": "MOS Technology 6502",
        "slug": "mos-technology-6502",
    },
    UniversalPlatformSlug.MOTOROLA_6800: {
        "id": 235,
        "name": "Motorola 6800",
        "slug": "motorola-6800",
    },
    UniversalPlatformSlug.MOTOROLA_68K: {
        "id": 275,
        "name": "Motorola 68k",
        "slug": "motorola-68k",
    },
    UniversalPlatformSlug.MRE: {"id": 229, "name": "MRE", "slug": "mre"},
    UniversalPlatformSlug.MSX: {"id": 57, "name": "MSX", "slug": "msx"},
    UniversalPlatformSlug.N64: {"id": 9, "name": "Nintendo 64", "slug": "n64"},
    UniversalPlatformSlug.NASCOM: {"id": 175, "name": "Nascom", "slug": "nascom"},
    UniversalPlatformSlug.NDS: {"id": 44, "name": "Nintendo DS", "slug": "nintendo-ds"},
    UniversalPlatformSlug.NEO_GEO_CD: {
        "id": 54,
        "name": "Neo Geo CD",
        "slug": "neo-geo-cd",
    },
    UniversalPlatformSlug.NEO_GEO_POCKET: {
        "id": 52,
        "name": "Neo Geo Pocket",
        "slug": "neo-geo-pocket",
    },
    UniversalPlatformSlug.NEO_GEO_POCKET_COLOR: {
        "id": 53,
        "name": "Neo Geo Pocket Color",
        "slug": "neo-geo-pocket-color",
    },
    UniversalPlatformSlug.NEO_GEO_X: {
        "id": 279,
        "name": "Neo Geo X",
        "slug": "neo-geo-x",
    },
    UniversalPlatformSlug.NEOGEOAES: {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    UniversalPlatformSlug.NEOGEOMVS: {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    UniversalPlatformSlug.NES: {"id": 22, "name": "NES", "slug": "nes"},
    UniversalPlatformSlug.NEW_NINTENDON3DS: {
        "id": 174,
        "name": "New Nintendo 3DS",
        "slug": "new-nintendo-3ds",
    },
    UniversalPlatformSlug.NEWBRAIN: {"id": 177, "name": "NewBrain", "slug": "newbrain"},
    UniversalPlatformSlug.NEWTON: {"id": 207, "name": "Newton", "slug": "newton"},
    UniversalPlatformSlug.NGAGE: {"id": 32, "name": "N-Gage", "slug": "ngage"},
    UniversalPlatformSlug.NGAGE2: {
        "id": 89,
        "name": "N-Gage (service)",
        "slug": "ngage2",
    },
    UniversalPlatformSlug.NGC: {"id": 14, "name": "GameCube", "slug": "gamecube"},
    UniversalPlatformSlug.NINTENDO_DSI: {
        "id": 87,
        "name": "Nintendo DSi",
        "slug": "nintendo-dsi",
    },
    UniversalPlatformSlug.NORTHSTAR: {
        "id": 266,
        "name": "North Star",
        "slug": "northstar",
    },
    UniversalPlatformSlug.NOVAL_760: {
        "id": 244,
        "name": "Noval 760",
        "slug": "noval-760",
    },
    UniversalPlatformSlug.NUON: {"id": 116, "name": "Nuon", "slug": "nuon"},
    UniversalPlatformSlug.OCULUS_GO: {
        "id": 218,
        "name": "Oculus Go",
        "slug": "oculus-go",
    },
    UniversalPlatformSlug.OCULUS_QUEST: {
        "id": 271,
        "name": "Quest",
        "slug": "oculus-quest",
    },
    UniversalPlatformSlug.ODYSSEY: {"id": 75, "name": "Odyssey", "slug": "odyssey"},
    UniversalPlatformSlug.ODYSSEY_2: {
        "id": 78,
        "name": "Odyssey 2",
        "slug": "odyssey-2",
    },
    UniversalPlatformSlug.ODYSSEY_2_SLASH_VIDEOPAC_G7000: {
        "id": 78,
        "name": "Odyssey 2/Videopac G7000",
        "slug": "odyssey-2",
    },
    UniversalPlatformSlug.OHIO_SCIENTIFIC: {
        "id": 178,
        "name": "Ohio Scientific",
        "slug": "ohio-scientific",
    },
    "onlive": {"id": 282, "name": "OnLive", "slug": "onlive"},
    UniversalPlatformSlug.ONLIVE_GAME_SYSTEM: {
        "id": 282,
        "name": "OnLive Game System",
        "slug": "onlive",
    },
    UniversalPlatformSlug.OOPARTS: {"id": 300, "name": "OOParts", "slug": "ooparts"},
    UniversalPlatformSlug.ORAO: {"id": 270, "name": "Orao", "slug": "orao"},
    UniversalPlatformSlug.ORIC: {"id": 111, "name": "Oric", "slug": "oric"},
    UniversalPlatformSlug.OS2: {"id": 146, "name": "OS/2", "slug": "os2"},
    UniversalPlatformSlug.OUYA: {"id": 144, "name": "Ouya", "slug": "ouya"},
    UniversalPlatformSlug.PALM_OS: {"id": 65, "name": "Palm OS", "slug": "palmos"},
    UniversalPlatformSlug.PANDORA: {"id": 308, "name": "Pandora", "slug": "pandora"},
    UniversalPlatformSlug.PC_6001: {"id": 149, "name": "PC-6001", "slug": "pc-6001"},
    UniversalPlatformSlug.PC_8000: {"id": 201, "name": "PC-8000", "slug": "pc-8000"},
    UniversalPlatformSlug.PC_8800_SERIES: {
        "id": 94,
        "name": "PC-8800 Series",
        "slug": "pc88",
    },
    UniversalPlatformSlug.PC_9800_SERIES: {
        "id": 95,
        "name": "PC-9800 Series",
        "slug": "pc98",
    },
    UniversalPlatformSlug.PC_BOOTER: {
        "id": 4,
        "name": "PC Booter",
        "slug": "pc-booter",
    },
    UniversalPlatformSlug.PC_FX: {"id": 59, "name": "PC-FX", "slug": "pc-fx"},
    UniversalPlatformSlug.PEBBLE: {"id": 304, "name": "Pebble", "slug": "pebble"},
    UniversalPlatformSlug.PHILIPS_CD_I: {"id": 73, "name": "CD-i", "slug": "cd-i"},
    UniversalPlatformSlug.PHILIPS_VG_5000: {
        "id": 133,
        "name": "Philips VG 5000",
        "slug": "philips-vg-5000",
    },
    UniversalPlatformSlug.PHOTOCD: {"id": 272, "name": "Photo CD", "slug": "photocd"},
    UniversalPlatformSlug.PICO: {"id": 316, "name": "PICO", "slug": "pico"},
    UniversalPlatformSlug.PIPPIN: {"id": 112, "name": "Pippin", "slug": "pippin"},
    UniversalPlatformSlug.PLAYDATE: {"id": 303, "name": "Playdate", "slug": "playdate"},
    UniversalPlatformSlug.PLAYDIA: {"id": 107, "name": "Playdia", "slug": "playdia"},
    UniversalPlatformSlug.PLAYSTATION_NOW: {
        "id": 294,
        "name": "PlayStation Now",
        "slug": "playstation-now",
    },
    UniversalPlatformSlug.PLEX_ARCADE: {
        "id": 291,
        "name": "Plex Arcade",
        "slug": "plex-arcade",
    },
    UniversalPlatformSlug.POKEMON_MINI: {
        "id": 152,
        "name": "Pokémon Mini",
        "slug": "pokemon-mini",
    },
    UniversalPlatformSlug.POKITTO: {"id": 230, "name": "Pokitto", "slug": "pokitto"},
    UniversalPlatformSlug.POLY_88: {"id": 249, "name": "Poly-88", "slug": "poly-88"},
    UniversalPlatformSlug.PS2: {
        "id": 7,
        "name": "PlayStation 2",
        "slug": "playstation-2",
    },
    UniversalPlatformSlug.PS3: {
        "id": 81,
        "name": "PlayStation 3",
        "slug": "playstation-3",
    },
    UniversalPlatformSlug.PS4: {
        "id": 141,
        "name": "PlayStation 4",
        "slug": "playstation-4",
    },
    UniversalPlatformSlug.PS5: {
        "id": 288,
        "name": "PlayStation 5",
        "slug": "playstation-5",
    },
    UniversalPlatformSlug.PSP: {"id": 46, "name": "PSP", "slug": "psp"},
    UniversalPlatformSlug.PSVITA: {"id": 105, "name": "PS Vita", "slug": "ps-vita"},
    UniversalPlatformSlug.PSX: {"id": 6, "name": "PlayStation", "slug": "playstation"},
    UniversalPlatformSlug.RCA_STUDIO_II: {
        "id": 113,
        "name": "RCA Studio II",
        "slug": "rca-studio-ii",
    },
    UniversalPlatformSlug.RESEARCH_MACHINES_380Z: {
        "id": 309,
        "name": "Research Machines 380Z",
        "slug": "research-machines-380z",
    },
    UniversalPlatformSlug.ROKU: {"id": 196, "name": "Roku", "slug": "roku"},
    UniversalPlatformSlug.SAM_COUPE: {
        "id": 120,
        "name": "SAM Coupé",
        "slug": "sam-coupe",
    },
    UniversalPlatformSlug.SATURN: {
        "id": 23,
        "name": "SEGA Saturn",
        "slug": "sega-saturn",
    },
    UniversalPlatformSlug.SCMP: {"id": 255, "name": "SC/MP", "slug": "scmp"},
    UniversalPlatformSlug.SD_200270290: {
        "id": 267,
        "name": "SD-200/270/290",
        "slug": "sd-200270290",
    },
    "sega-32x": {"id": 21, "name": "SEGA 32X", "slug": "sega-32x"},
    UniversalPlatformSlug.SEGA_PICO: {
        "id": 103,
        "name": "SEGA Pico",
        "slug": "sega-pico",
    },
    UniversalPlatformSlug.SEGA32: {"id": 21, "name": "SEGA 32X", "slug": "sega-32x"},
    UniversalPlatformSlug.SEGACD: {"id": 20, "name": "SEGA CD", "slug": "sega-cd"},
    UniversalPlatformSlug.SERIES_X_S: {
        "id": 289,
        "name": "Xbox Series X/S",
        "slug": "xbox-series",
    },
    UniversalPlatformSlug.SFAM: {"id": 15, "name": "Super Famicom", "slug": "snes"},
    UniversalPlatformSlug.SG1000: {"id": 114, "name": "SG-1000", "slug": "sg-1000"},
    UniversalPlatformSlug.SHARP_MZ_80B20002500: {
        "id": 182,
        "name": "Sharp MZ-80B/2000/2500",
        "slug": "sharp-mz-80b20002500",
    },
    UniversalPlatformSlug.SHARP_MZ_80K7008001500: {
        "id": 181,
        "name": "Sharp MZ-80K/700/800/1500",
        "slug": "sharp-mz-80k7008001500",
    },
    UniversalPlatformSlug.SHARP_X68000: {
        "id": 106,
        "name": "Sharp X68000",
        "slug": "sharp-x68000",
    },
    UniversalPlatformSlug.SHARP_ZAURUS: {
        "id": 202,
        "name": "Sharp Zaurus",
        "slug": "sharp-zaurus",
    },
    UniversalPlatformSlug.SIGNETICS_2650: {
        "id": 278,
        "name": "Signetics 2650",
        "slug": "signetics-2650",
    },
    UniversalPlatformSlug.SINCLAIR_QL: {
        "id": 131,
        "name": "Sinclair QL",
        "slug": "sinclair-ql",
    },
    UniversalPlatformSlug.SK_VM: {"id": 259, "name": "SK-VM", "slug": "sk-vm"},
    UniversalPlatformSlug.SMC_777: {"id": 273, "name": "SMC-777", "slug": "smc-777"},
    UniversalPlatformSlug.SMS: {
        "id": 26,
        "name": "SEGA Master System",
        "slug": "sega-master-system",
    },
    UniversalPlatformSlug.SNES: {"id": 15, "name": "SNES", "slug": "snes"},
    UniversalPlatformSlug.SOCRATES: {"id": 190, "name": "Socrates", "slug": "socrates"},
    UniversalPlatformSlug.SOL_20: {"id": 199, "name": "Sol-20", "slug": "sol-20"},
    UniversalPlatformSlug.SORD_M5: {"id": 134, "name": "Sord M5", "slug": "sord-m5"},
    UniversalPlatformSlug.SPECTRAVIDEO: {
        "id": 85,
        "name": "Spectravideo",
        "slug": "spectravideo",
    },
    UniversalPlatformSlug.SRI_5001000: {
        "id": 242,
        "name": "SRI-500/1000",
        "slug": "sri-5001000",
    },
    UniversalPlatformSlug.STADIA: {"id": 281, "name": "Stadia", "slug": "stadia"},
    UniversalPlatformSlug.SUPER_ACAN: {
        "id": 110,
        "name": "Super A'can",
        "slug": "super-acan",
    },
    UniversalPlatformSlug.SUPER_VISION_8000: {
        "id": 296,
        "name": "Super Vision 8000",
        "slug": "super-vision-8000",
    },
    UniversalPlatformSlug.SUPERGRAFX: {
        "id": 127,
        "name": "SuperGrafx",
        "slug": "supergrafx",
    },
    UniversalPlatformSlug.SUPERVISION: {
        "id": 109,
        "name": "Supervision",
        "slug": "supervision",
    },
    UniversalPlatformSlug.SURE_SHOT_HD: {
        "id": 287,
        "name": "Sure Shot HD",
        "slug": "sure-shot-hd",
    },
    UniversalPlatformSlug.SWITCH: {
        "id": 203,
        "name": "Nintendo Switch",
        "slug": "switch",
    },
    UniversalPlatformSlug.SWITCH_2: {
        "id": -1,
        "name": "Nintendo Switch 2",
        "slug": "switch-2",
    },
    UniversalPlatformSlug.SWTPC_6800: {
        "id": 228,
        "name": "SWTPC 6800",
        "slug": "swtpc-6800",
    },
    UniversalPlatformSlug.SYMBIAN: {"id": 67, "name": "Symbian", "slug": "symbian"},
    UniversalPlatformSlug.TADS: {"id": 171, "name": "TADS", "slug": "tads"},
    UniversalPlatformSlug.TAITO_X_55: {
        "id": 283,
        "name": "Taito X-55",
        "slug": "taito-x-55",
    },
    UniversalPlatformSlug.TATUNG_EINSTEIN: {
        "id": 150,
        "name": "Tatung Einstein",
        "slug": "tatung-einstein",
    },
    UniversalPlatformSlug.TEKTRONIX_4050: {
        "id": 223,
        "name": "Tektronix 4050",
        "slug": "tektronix-4050",
    },
    UniversalPlatformSlug.TELE_SPIEL: {
        "id": 220,
        "name": "Tele-Spiel ES-2201",
        "slug": "tele-spiel",
    },
    UniversalPlatformSlug.TELSTAR_ARCADE: {
        "id": 233,
        "name": "Telstar Arcade",
        "slug": "telstar-arcade",
    },
    UniversalPlatformSlug.TERMINAL: {"id": 209, "name": "Terminal", "slug": "terminal"},
    UniversalPlatformSlug.TG16: {
        "id": 40,
        "name": "TurboGrafx-16",
        "slug": "turbo-grafx",
    },
    "thomson-mo": {"id": 147, "name": "Thomson MO", "slug": "thomson-mo"},
    UniversalPlatformSlug.THOMSON_MO5: {
        "id": 147,
        "name": "Thomson MO5",
        "slug": "thomson-mo",
    },
    UniversalPlatformSlug.THOMSON_TO: {
        "id": 130,
        "name": "Thomson TO",
        "slug": "thomson-to",
    },
    UniversalPlatformSlug.TI_99: {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    UniversalPlatformSlug.TI_994A: {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    UniversalPlatformSlug.TI_PROGRAMMABLE_CALCULATOR: {
        "id": 239,
        "name": "TI Programmable Calculator",
        "slug": "ti-programmable-calculator",
    },
    UniversalPlatformSlug.TIKI_100: {"id": 263, "name": "Tiki 100", "slug": "tiki-100"},
    UniversalPlatformSlug.TIM: {"id": 246, "name": "TIM", "slug": "tim"},
    UniversalPlatformSlug.TIMEX_SINCLAIR_2068: {
        "id": 173,
        "name": "Timex Sinclair 2068",
        "slug": "timex-sinclair-2068",
    },
    UniversalPlatformSlug.TIZEN: {"id": 206, "name": "Tizen", "slug": "tizen"},
    UniversalPlatformSlug.TOMAHAWK_F1: {
        "id": 256,
        "name": "Tomahawk F1",
        "slug": "tomahawk-f1",
    },
    UniversalPlatformSlug.TOMY_TUTOR: {
        "id": 151,
        "name": "Tomy Tutor",
        "slug": "tomy-tutor",
    },
    UniversalPlatformSlug.TRITON: {"id": 310, "name": "Triton", "slug": "triton"},
    UniversalPlatformSlug.TRS_80: {"id": 58, "name": "TRS-80", "slug": "trs-80"},
    UniversalPlatformSlug.TRS_80_COLOR_COMPUTER: {
        "id": 62,
        "name": "TRS-80 Color Computer",
        "slug": "trs-80-coco",
    },
    UniversalPlatformSlug.TRS_80_MC_10: {
        "id": 193,
        "name": "TRS-80 MC-10",
        "slug": "trs-80-mc-10",
    },
    UniversalPlatformSlug.TRS_80_MODEL_100: {
        "id": 312,
        "name": "TRS-80 Model 100",
        "slug": "trs-80-model-100",
    },
    UniversalPlatformSlug.TURBOGRAFX_CD: {
        "id": 45,
        "name": "TurboGrafx CD",
        "slug": "turbografx-cd",
    },
    UniversalPlatformSlug.TVOS: {"id": 179, "name": "tvOS", "slug": "tvos"},
    UniversalPlatformSlug.VECTREX: {"id": 37, "name": "Vectrex", "slug": "vectrex"},
    UniversalPlatformSlug.VERSATILE: {
        "id": 299,
        "name": "Versatile",
        "slug": "versatile",
    },
    UniversalPlatformSlug.VFLASH: {"id": 189, "name": "V.Flash", "slug": "vflash"},
    UniversalPlatformSlug.VIC_20: {"id": 43, "name": "VIC-20", "slug": "vic-20"},
    UniversalPlatformSlug.VIDEOBRAIN: {
        "id": 214,
        "name": "VideoBrain",
        "slug": "videobrain",
    },
    UniversalPlatformSlug.VIDEOPAC_G7400: {
        "id": 128,
        "name": "Videopac+ G7400",
        "slug": "videopac-g7400",
    },
    "virtual-boy": {"id": 38, "name": "Virtual Boy", "slug": "virtual-boy"},
    UniversalPlatformSlug.VIRTUALBOY: {
        "id": 38,
        "name": "Virtual Boy",
        "slug": "virtual-boy",
    },
    UniversalPlatformSlug.VIS: {"id": 164, "name": "VIS", "slug": "vis"},
    UniversalPlatformSlug.VSMILE: {"id": 42, "name": "V.Smile", "slug": "vsmile"},
    UniversalPlatformSlug.WANG2200: {
        "id": 217,
        "name": "Wang 2200",
        "slug": "wang2200",
    },
    UniversalPlatformSlug.WATCHOS: {"id": 180, "name": "watchOS", "slug": "watchos"},
    UniversalPlatformSlug.WEBOS: {"id": 100, "name": "webOS", "slug": "webos"},
    UniversalPlatformSlug.WII: {"id": 82, "name": "Wii", "slug": "wii"},
    "wii-u": {"id": 132, "name": "Wii U", "slug": "wii-u"},
    UniversalPlatformSlug.WIIU: {"id": 132, "name": "Wii U", "slug": "wii-u"},
    UniversalPlatformSlug.WIN: {"id": 3, "name": "Windows", "slug": "windows"},
    UniversalPlatformSlug.WIN3X: {"id": 5, "name": "Windows 3.x", "slug": "win3x"},
    UniversalPlatformSlug.WINDOWS_APPS: {
        "id": 140,
        "name": "Windows Apps",
        "slug": "windows-apps",
    },
    UniversalPlatformSlug.WINDOWS_MOBILE: {
        "id": 66,
        "name": "Windows Mobile",
        "slug": "windowsmobile",
    },
    "windows-phone": {"id": 98, "name": "Windows Phone", "slug": "windows-phone"},
    "windowsmobile": {"id": 66, "name": "Windows Mobile", "slug": "windowsmobile"},
    UniversalPlatformSlug.WINPHONE: {
        "id": 98,
        "name": "Windows Phone",
        "slug": "windows-phone",
    },
    UniversalPlatformSlug.WIPI: {"id": 260, "name": "WIPI", "slug": "wipi"},
    UniversalPlatformSlug.WONDERSWAN: {
        "id": 48,
        "name": "WonderSwan",
        "slug": "wonderswan",
    },
    UniversalPlatformSlug.WONDERSWAN_COLOR: {
        "id": 49,
        "name": "WonderSwan Color",
        "slug": "wonderswan-color",
    },
    UniversalPlatformSlug.X1: {"id": 121, "name": "Sharp X1", "slug": "sharp-x1"},
    UniversalPlatformSlug.XAVIXPORT: {
        "id": 191,
        "name": "XaviXPORT",
        "slug": "xavixport",
    },
    UniversalPlatformSlug.XBOX: {"id": 13, "name": "Xbox", "slug": "xbox"},
    "xbox-one": {"id": 142, "name": "Xbox One", "slug": "xbox-one"},
    "xbox-series": {"id": 289, "name": "Xbox Series", "slug": "xbox-series"},
    UniversalPlatformSlug.XBOX360: {"id": 69, "name": "Xbox 360", "slug": "xbox360"},
    UniversalPlatformSlug.XBOXCLOUDGAMING: {
        "id": 293,
        "name": "Xbox Cloud Gaming",
        "slug": "xboxcloudgaming",
    },
    UniversalPlatformSlug.XBOXONE: {"id": 142, "name": "Xbox One", "slug": "xbox-one"},
    UniversalPlatformSlug.XEROX_ALTO: {
        "id": 254,
        "name": "Xerox Alto",
        "slug": "xerox-alto",
    },
    UniversalPlatformSlug.Z_MACHINE: {
        "id": 169,
        "name": "Z-machine",
        "slug": "z-machine",
    },
    UniversalPlatformSlug.Z80: {"id": 227, "name": "Zilog Z80", "slug": "z80"},
    UniversalPlatformSlug.ZEEBO: {"id": 88, "name": "Zeebo", "slug": "zeebo"},
    UniversalPlatformSlug.ZILOG_Z8000: {
        "id": 276,
        "name": "Zilog Z8000",
        "slug": "zilog-z8000",
    },
    UniversalPlatformSlug.ZODIAC: {"id": 68, "name": "Zodiac", "slug": "zodiac"},
    UniversalPlatformSlug.ZUNE: {"id": 211, "name": "Zune", "slug": "zune"},
    UniversalPlatformSlug.ZX_SPECTRUM: {
        "id": 41,
        "name": "ZX Spectrum",
        "slug": "zx-spectrum",
    },
    UniversalPlatformSlug.ZX_SPECTRUM_NEXT: {
        "id": 280,
        "name": "ZX Spectrum Next",
        "slug": "zx-spectrum-next",
    },
    UniversalPlatformSlug.ZX80: {"id": 118, "name": "ZX80", "slug": "zx80"},
    UniversalPlatformSlug.ZX81: {"id": 119, "name": "ZX81", "slug": "zx81"},
}

# Reverse lookup
MOBY_ID_TO_SLUG = {v["id"]: k for k, v in MOBYGAMES_PLATFORM_LIST.items()}


# These platforms are ignored due to lack of data:
# arb, casiofp, dai, hitachibasicmaster3, hposcilloscope, hpseries80

# Need the IDs for these platforms before we can add them:
# p2000, visionos
