import base64
import re
from datetime import datetime
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import pydash
from adapters.services.screenscraper import ScreenScraperService
from adapters.services.screenscraper_types import SSGame, SSGameDate
from config import SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
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


class SSRom(BaseRom):
    ss_id: int | None
    ss_metadata: NotRequired[SSMetadata]


def build_ss_rom(game: SSGame) -> SSRom:
    name_preferred_regions = ["us", "wor", "ss", "eu", "jp"]
    res_name = ""
    for region in name_preferred_regions:
        res_name = next(
            (
                name["text"]
                for name in game.get("noms", [])
                if name.get("region") == region
            ),
            "",
        )
        if res_name:
            break

    res_summary = next(
        (
            synopsis["text"]
            for synopsis in game.get("synopsis", [])
            if synopsis.get("langue") == "en"
        ),
        "",
    )

    cover_preferred_regions = ["us", "wor", "ss", "eu", "jp"]
    url_cover = ""
    for region in cover_preferred_regions:
        url_cover = next(
            (
                media["url"]
                for media in game.get("medias", [])
                if media.get("region") == region
                and media.get("type") == "box-2D"
                and media.get("parent") == "jeu"
            ),
            "",
        )
        if url_cover:
            break

    manual_preferred_regions = ["us", "wor", "ss", "eu", "jp"]
    url_manual: str = ""
    for region in manual_preferred_regions:
        url_manual = next(
            (
                media["url"]
                for media in game.get("medias", [])
                if media.get("region") == region
                and media.get("type") == "manuel"
                and media.get("parent") == "jeu"
                and media.get("format") == "pdf"
            ),
            "",
        )
        if url_manual:
            break

    ss_id = int(game["id"]) if game.get("id") is not None else None
    rom: SSRom = {
        "ss_id": ss_id,
        "name": res_name.replace(" : ", ": "),  # Normalize colons
        "summary": res_summary,
        "url_cover": url_cover,
        "url_manual": url_manual,
        "url_screenshots": [],
        "ss_metadata": extract_metadata_from_ss_rom(game),
    }

    return SSRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]


def extract_metadata_from_ss_rom(rom: SSGame) -> SSMetadata:
    def _normalize_score(score: str) -> str:
        """Normalize the score to be between 0 and 10 because for some reason Screenscraper likes to rate over 20."""
        try:
            return str(int(score) / 2)
        except (ValueError, TypeError):
            return ""

    def _get_lowest_date(dates: list[SSGameDate]) -> int | None:
        lowest_date = min(dates, default=None, key=lambda v: v.get("text", ""))
        if not lowest_date:
            return None

        try:
            return int(datetime.strptime(lowest_date["text"], "%Y-%m-%d").timestamp())
        except ValueError:
            try:
                return int(datetime.strptime(lowest_date["text"], "%Y").timestamp())
            except ValueError:
                return None

    def _get_genres(rom: SSGame) -> list[str]:
        return [
            genre_name["text"]
            for genre in rom.get("genres", [])
            for genre_name in genre.get("noms", [])
            if genre_name.get("langue") == "en"
        ]

    def _get_franchises(rom: SSGame) -> list[str]:
        preferred_languages = ["en", "fr"]
        for lang in preferred_languages:
            franchises = [
                franchise_name["text"]
                for franchise in rom.get("familles", [])
                for franchise_name in franchise.get("noms", [])
                if franchise_name.get("langue") == lang
            ]
            if franchises:
                return franchises
        return []

    def _get_game_modes(rom: SSGame) -> list[str]:
        preferred_languages = ["en", "fr"]
        for lang in preferred_languages:
            modes = [
                mode_name["text"]
                for mode in rom.get("modes", [])
                for mode_name in mode.get("noms", [])
                if mode_name.get("langue") == lang
            ]
            if modes:
                return modes
        return []

    return SSMetadata(
        {
            "ss_score": _normalize_score(rom.get("note", {}).get("text", "")),
            "alternative_names": [name["text"] for name in rom.get("noms", [])],
            "companies": pydash.compact(
                [
                    rom.get("editeur", {}).get("text"),
                    rom.get("developpeur", {}).get("text"),
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
        self.ss_service = ScreenScraperService()

    async def _search_rom(self, search_term: str, platform_ss_id: int) -> SSGame | None:
        if not platform_ss_id:
            return None

        def is_exact_match(rom: SSGame, search_term: str) -> bool:
            rom_names = [name.get("text", "").lower() for name in rom.get("noms", [])]

            return any(
                (
                    rom_name.lower() == search_term.lower()
                    or self.normalize_search_term(rom_name) == search_term
                )
                for rom_name in rom_names
            )

        roms = await self.ss_service.search_games(
            term=quote(uc(search_term), safe="/ "),
            system_id=platform_ss_id,
        )

        for rom in roms:
            if is_exact_match(rom, search_term):
                return rom

        return roms[0] if roms else None

    def get_platform(self, slug: str) -> SSPlatform:
        platform = SCREENSAVER_PLATFORM_LIST.get(slug, None)

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

        ## SS API requires punctuation to match
        normalized_search_term = self.normalize_search_term(
            search_term, remove_punctuation=False
        )
        res = await self._search_rom(normalized_search_term, platform_ss_id)

        # SS API doesn't handle some special characters well
        if not res and (
            ": " in search_term or " - " in search_term or "/" in search_term
        ):
            if ": " in search_term:
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
                res = await self._search_rom(terms[i], platform_ss_id)
                if res:
                    break

        if not res or not res.get("id"):
            return fallback_rom

        return build_ss_rom(res)

    async def get_rom_by_id(self, ss_id: int) -> SSRom:
        if not SS_API_ENABLED:
            return SSRom(ss_id=None)

        res = await self.ss_service.get_game_info(game_id=ss_id)
        if not res:
            return SSRom(ss_id=None)

        return build_ss_rom(res)

    async def get_matched_rom_by_id(self, ss_id: int) -> SSRom | None:
        if not SS_API_ENABLED:
            return None

        rom = await self.get_rom_by_id(ss_id)
        return rom if rom.get("ss_id", "") else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_ss_id: int | None
    ) -> list[SSRom]:
        if not SS_API_ENABLED:
            return []

        if not platform_ss_id:
            return []

        matched_roms = await self.ss_service.search_games(
            term=quote(uc(search_term), safe="/ "),
            system_id=platform_ss_id,
        )

        def _is_ss_region(rom: SSGame) -> bool:
            return any(name.get("region") == "ss" for name in rom.get("noms", []))

        return [
            build_ss_rom(rom)
            for rom in matched_roms
            if _is_ss_region(rom) and rom.get("id")
        ]


class SlugToSSId(TypedDict):
    id: int
    name: str


SCREENSAVER_PLATFORM_LIST: dict[UniversalPlatformSlug, SlugToSSId] = {
    UniversalPlatformSlug._3DO: {"id": 29, "name": "3DO"},
    UniversalPlatformSlug.AMIGA: {"id": 64, "name": "Amiga"},
    UniversalPlatformSlug.AMIGA_CD32: {"id": 134, "name": "Amiga CD"},
    UniversalPlatformSlug.ACPC: {"id": 60, "name": "CPC"},
    UniversalPlatformSlug.ADVENTURE_VISION: {
        "id": 78,
        "name": "Entex Adventure Vision",
    },
    UniversalPlatformSlug.AMSTRAD_GX4000: {"id": 87, "name": "Amstrad GX4000"},
    UniversalPlatformSlug.ANDROID: {"id": 63, "name": "Android"},
    UniversalPlatformSlug.APPLEII: {"id": 86, "name": "Apple II"},
    UniversalPlatformSlug.APPLE_IIGS: {"id": 51, "name": "Apple IIGS"},
    UniversalPlatformSlug.ARCADIA_2001: {"id": 94, "name": "Arcadia 2001"},
    UniversalPlatformSlug.ARDUBOY: {"id": 263, "name": "Arduboy"},
    UniversalPlatformSlug.ATARI2600: {"id": 26, "name": "Atari 2600"},
    UniversalPlatformSlug.ATARI5200: {"id": 40, "name": "Atari 5200"},
    UniversalPlatformSlug.ATARI7800: {"id": 41, "name": "Atari 7800"},
    UniversalPlatformSlug.ATARI8BIT: {"id": 43, "name": "Atari 8bit"},
    UniversalPlatformSlug.ATARI_ST: {"id": 42, "name": "Atari ST"},
    UniversalPlatformSlug.ATOM: {"id": 36, "name": "Atom"},
    UniversalPlatformSlug.BBCMICRO: {"id": 37, "name": "BBC Micro"},
    UniversalPlatformSlug.ASTROCADE: {"id": 44, "name": "Astrocade"},
    UniversalPlatformSlug.PHILIPS_CD_I: {"id": 133, "name": "CD-i"},
    UniversalPlatformSlug.COMMODORE_CDTV: {"id": 129, "name": "Amiga CDTV"},
    UniversalPlatformSlug.CAMPUTERS_LYNX: {"id": 88, "name": "Camputers Lynx"},
    UniversalPlatformSlug.CASIO_LOOPY: {"id": 98, "name": "Loopy"},
    UniversalPlatformSlug.CASIO_PV_1000: {"id": 74, "name": "PV-1000"},
    UniversalPlatformSlug.FAIRCHILD_CHANNEL_F: {"id": 80, "name": "Channel F"},
    UniversalPlatformSlug.COLECOADAM: {"id": 89, "name": "Coleco Adam"},
    UniversalPlatformSlug.COLECOVISION: {"id": 48, "name": "Colecovision"},
    UniversalPlatformSlug.COLOUR_GENIE: {"id": 92, "name": "EG2000 Colour Genie"},
    UniversalPlatformSlug.C128: {"id": 66, "name": "Commodore 64"},
    UniversalPlatformSlug.C_PLUS_4: {"id": 99, "name": "Plus/4"},
    UniversalPlatformSlug.C16: {"id": 99, "name": "Plus/4"},
    UniversalPlatformSlug.C64: {"id": 66, "name": "Commodore 64"},
    UniversalPlatformSlug.CPET: {"id": 240, "name": "PET"},
    UniversalPlatformSlug.CREATIVISION: {"id": 241, "name": "CreatiVision"},
    UniversalPlatformSlug.DOS: {"id": 135, "name": "PC Dos"},
    UniversalPlatformSlug.DRAGON_32_SLASH_64: {"id": 91, "name": "Dragon 32/64"},
    UniversalPlatformSlug.DC: {"id": 23, "name": "Dreamcast"},
    UniversalPlatformSlug.ACORN_ELECTRON: {"id": 85, "name": "Electron"},
    UniversalPlatformSlug.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 95,
        "name": "Game Pocket Computer",
    },
    UniversalPlatformSlug.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 67,
        "name": "Super Cassette Vision",
    },
    UniversalPlatformSlug.EXELVISION: {"id": 96, "name": "EXL 100"},
    UniversalPlatformSlug.EXIDY_SORCERER: {"id": 165, "name": "Exidy"},
    UniversalPlatformSlug.FM_TOWNS: {"id": 253, "name": "FM Towns"},
    UniversalPlatformSlug.FM_7: {"id": 97, "name": "FM-7"},
    UniversalPlatformSlug.G_AND_W: {"id": 52, "name": "Game & Watch"},
    UniversalPlatformSlug.GP32: {"id": 101, "name": "GP32"},
    UniversalPlatformSlug.GB: {"id": 9, "name": "Game Boy"},
    UniversalPlatformSlug.GBA: {"id": 12, "name": "Game Boy Advance"},
    UniversalPlatformSlug.GBC: {"id": 10, "name": "Game Boy Color"},
    UniversalPlatformSlug.GAMEGEAR: {"id": 21, "name": "Game Gear"},
    UniversalPlatformSlug.GAME_DOT_COM: {"id": 121, "name": "Game.com"},
    UniversalPlatformSlug.NGC: {"id": 13, "name": "GameCube"},
    UniversalPlatformSlug.GENESIS: {"id": 1, "name": "Megadrive"},
    UniversalPlatformSlug.HARTUNG: {"id": 103, "name": "Game Master"},
    UniversalPlatformSlug.INTELLIVISION: {"id": 115, "name": "Intellivision"},
    UniversalPlatformSlug.JAGUAR: {"id": 27, "name": "Jaguar"},
    UniversalPlatformSlug.JUPITER_ACE: {"id": 126, "name": "Jupiter Ace"},
    UniversalPlatformSlug.LINUX: {"id": 145, "name": "Linux"},
    UniversalPlatformSlug.LYNX: {"id": 28, "name": "Lynx"},
    UniversalPlatformSlug.MSX: {"id": 113, "name": "MSX"},
    UniversalPlatformSlug.MSX_TURBO: {"id": 118, "name": "MSX Turbo R"},
    UniversalPlatformSlug.MAC: {"id": 146, "name": "Mac OS"},
    UniversalPlatformSlug.NGAGE: {"id": 30, "name": "N-Gage"},
    UniversalPlatformSlug.NES: {"id": 3, "name": "NES"},
    UniversalPlatformSlug.FDS: {"id": 106, "name": "Famicom"},
    UniversalPlatformSlug.NEOGEOAES: {"id": 142, "name": "Neo-Geo"},
    UniversalPlatformSlug.NEOGEOMVS: {"id": 68, "name": "Neo-Geo MVS"},
    UniversalPlatformSlug.NEO_GEO_CD: {"id": 70, "name": "Neo-Geo CD"},
    UniversalPlatformSlug.NEO_GEO_POCKET: {"id": 25, "name": "Neo-Geo Pocket"},
    UniversalPlatformSlug.NEO_GEO_POCKET_COLOR: {
        "id": 82,
        "name": "Neo-Geo Pocket Color",
    },
    UniversalPlatformSlug.N3DS: {"id": 17, "name": "Nintendo 3DS"},
    UniversalPlatformSlug.N64: {"id": 14, "name": "Nintendo 64"},
    UniversalPlatformSlug.NDS: {"id": 15, "name": "Nintendo DS"},
    UniversalPlatformSlug.NINTENDO_DSI: {"id": 15, "name": "Nintendo DS"},
    UniversalPlatformSlug.SWITCH: {"id": 225, "name": "Switch"},
    UniversalPlatformSlug.ODYSSEY_2: {"id": 104, "name": "Videopac G7000"},
    UniversalPlatformSlug.ODYSSEY_2_SLASH_VIDEOPAC_G7000: {
        "id": 104,
        "name": "Videopac G7000",
    },
    UniversalPlatformSlug.ORIC: {"id": 131, "name": "Oric 1 / Atmos"},
    UniversalPlatformSlug.PC_8800_SERIES: {"id": 221, "name": "NEC PC-8801"},
    UniversalPlatformSlug.PC_9800_SERIES: {"id": 208, "name": "NEC PC-9801"},
    UniversalPlatformSlug.PC_FX: {"id": 72, "name": "PC-FX"},
    UniversalPlatformSlug.PICO: {"id": 234, "name": "Pico-8"},
    UniversalPlatformSlug.PSVITA: {"id": 62, "name": "PS Vita"},
    UniversalPlatformSlug.PSP: {"id": 61, "name": "PSP"},
    UniversalPlatformSlug.PALM_OS: {"id": 219, "name": "Palm OS"},
    UniversalPlatformSlug.PHILIPS_VG_5000: {"id": 261, "name": "Philips VG 5000"},
    UniversalPlatformSlug.PSX: {"id": 57, "name": "Playstation"},
    UniversalPlatformSlug.PS2: {"id": 58, "name": "Playstation 2"},
    UniversalPlatformSlug.PS3: {"id": 59, "name": "Playstation 3"},
    UniversalPlatformSlug.PS4: {"id": 60, "name": "Playstation 4"},
    UniversalPlatformSlug.PS5: {"id": 284, "name": "Playstation 5"},
    UniversalPlatformSlug.POKEMON_MINI: {"id": 211, "name": "Pokémon mini"},
    UniversalPlatformSlug.SAM_COUPE: {"id": 213, "name": "MGT SAM Coupé"},
    UniversalPlatformSlug.SEGA32: {"id": 19, "name": "Megadrive 32X"},
    UniversalPlatformSlug.SEGACD: {"id": 20, "name": "Mega-CD"},
    UniversalPlatformSlug.SMS: {"id": 2, "name": "Master System"},
    UniversalPlatformSlug.SEGA_PICO: {"id": 250, "name": "Sega Pico"},
    UniversalPlatformSlug.SATURN: {"id": 22, "name": "Saturn"},
    UniversalPlatformSlug.SG1000: {"id": 109, "name": "SG-1000"},
    UniversalPlatformSlug.SNES: {"id": 4, "name": "Super Nintendo"},
    UniversalPlatformSlug.X1: {"id": 220, "name": "Sharp X1"},
    UniversalPlatformSlug.SHARP_X68000: {"id": 79, "name": "Sharp X68000"},
    UniversalPlatformSlug.SPECTRAVIDEO: {"id": 218, "name": "Spectravideo"},
    UniversalPlatformSlug.SUFAMI_TURBO: {"id": 108, "name": "Sufami Turbo"},
    UniversalPlatformSlug.SUPER_ACAN: {"id": 100, "name": "Super A'can"},
    UniversalPlatformSlug.SUPERGRAFX: {"id": 105, "name": "PC Engine SuperGrafx"},
    UniversalPlatformSlug.SUPERVISION: {"id": 207, "name": "Watara Supervision"},
    UniversalPlatformSlug.TI_99: {"id": 205, "name": "TI-99/4A"},
    UniversalPlatformSlug.TRS_80_COLOR_COMPUTER: {
        "id": 144,
        "name": "TRS-80 Color Computer",
    },
    UniversalPlatformSlug.TAITO_X_55: {"id": 112, "name": "Type X"},
    "thomson-mo": {"id": 141, "name": "Thomson MO/TO"},
    UniversalPlatformSlug.THOMSON_MO5: {"id": 141, "name": "Thomson MO/TO"},
    UniversalPlatformSlug.THOMSON_TO: {"id": 141, "name": "Thomson MO/TO"},
    UniversalPlatformSlug.TURBOGRAFX_CD: {"id": 114, "name": "PC Engine CD-Rom"},
    UniversalPlatformSlug.TG16: {"id": 31, "name": "PC Engine"},
    UniversalPlatformSlug.UZEBOX: {"id": 216, "name": "UzeBox"},
    UniversalPlatformSlug.VSMILE: {"id": 120, "name": "V.Smile"},
    UniversalPlatformSlug.VIC_20: {"id": 73, "name": "Vic-20"},
    UniversalPlatformSlug.VECTREX: {"id": 102, "name": "Vectrex"},
    UniversalPlatformSlug.VIDEOPAC_G7400: {"id": 104, "name": "Videopac G7000"},
    "virtual-boy": {"id": 11, "name": "Virtual Boy"},
    UniversalPlatformSlug.VIRTUALBOY: {"id": 11, "name": "Virtual Boy"},
    UniversalPlatformSlug.WII: {"id": 16, "name": "Wii"},
    "wii-u": {"id": 18, "name": "Wii U"},
    UniversalPlatformSlug.WIIU: {"id": 18, "name": "Wii U"},
    UniversalPlatformSlug.WIN: {"id": 138, "name": "PC Windows"},
    UniversalPlatformSlug.WIN3X: {"id": 136, "name": "PC Win3.xx"},
    UniversalPlatformSlug.WONDERSWAN: {"id": 45, "name": "WonderSwan"},
    UniversalPlatformSlug.WONDERSWAN_COLOR: {"id": 46, "name": "WonderSwan Color"},
    UniversalPlatformSlug.XBOX: {"id": 32, "name": "Xbox"},
    UniversalPlatformSlug.XBOX360: {"id": 33, "name": "Xbox 360"},
    "xbox-one": {"id": 34, "name": "Xbox One"},
    UniversalPlatformSlug.XBOXONE: {"id": 34, "name": "Xbox One"},
    UniversalPlatformSlug.Z_MACHINE: {"id": 215, "name": "Z-Machine"},
    UniversalPlatformSlug.ZX_SPECTRUM: {"id": 76, "name": "ZX Spectrum"},
    UniversalPlatformSlug.ZX81: {"id": 77, "name": "ZX81"},
}

# Reverse lookup
SS_ID_TO_SLUG = {v["id"]: k for k, v in SCREENSAVER_PLATFORM_LIST.items()}
