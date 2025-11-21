import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import pydash
from unidecode import unidecode as uc

from adapters.services.mobygames import MobyGamesService
from adapters.services.mobygames_types import MobyGame
from config import MOBYGAMES_API_KEY
from logger.logger import log

from .base_handler import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    BaseRom,
    MetadataHandler,
)
from .base_handler import UniversalPlatformSlug as UPS

PS1_MOBY_ID: Final = 6
PS2_MOBY_ID: Final = 7
PSP_MOBY_ID: Final = 46
SWITCH_MOBY_ID: Final = 203
ARCADE_MOBY_IDS: Final = [143, 36]

# Regex to detect MobyGames ID tags in filenames like (moby-12345)
MOBYGAMES_TAG_REGEX = re.compile(r"\(moby-(\d+)\)", re.IGNORECASE)


class MobyGamesPlatform(TypedDict):
    slug: str
    moby_id: int | None
    moby_slug: NotRequired[str]
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
        self.min_similarity_score = 0.6

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(MOBYGAMES_API_KEY)

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self.moby_service.list_groups(limit=1)
        except Exception as e:
            log.error("Error checking MobyGames API: %s", e)
            return False

        return bool(response)

    @staticmethod
    def extract_mobygames_id_from_filename(fs_name: str) -> int | None:
        """Extract MobyGames ID from filename tag like (moby-12345)."""
        match = MOBYGAMES_TAG_REGEX.search(fs_name)
        if match:
            return int(match.group(1))
        return None

    async def _search_rom(
        self, search_term: str, platform_moby_id: int, split_game_name: bool = False
    ) -> MobyGame | None:
        if not platform_moby_id:
            return None

        roms = await self.moby_service.list_games(
            platform_ids=[platform_moby_id],
            title=quote(uc(search_term), safe="/ "),
        )
        if not roms:
            return None

        games_by_name: dict[str, MobyGame] = {}
        for game in roms:
            if (
                game["title"] not in games_by_name
                or game["game_id"] < games_by_name[game["title"]]["game_id"]
            ):
                games_by_name[game["title"]] = game

        best_match, best_score = self.find_best_match(
            search_term,
            list(games_by_name.keys()),
            self.min_similarity_score,
            split_game_name=split_game_name,
        )
        if best_match:
            log.debug(
                f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
            )
            return games_by_name[best_match]

        return None

    def get_platform(self, slug: str) -> MobyGamesPlatform:
        if slug not in MOBYGAMES_PLATFORM_LIST:
            return MobyGamesPlatform(moby_id=None, slug=slug)

        platform = MOBYGAMES_PLATFORM_LIST[UPS(slug)]

        return MobyGamesPlatform(
            moby_id=platform["id"],
            slug=slug,
            moby_slug=platform["slug"],
            name=platform["name"],
        )

    async def get_rom(self, fs_name: str, platform_moby_id: int) -> MobyGamesRom:
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return MobyGamesRom(moby_id=None)

        if not platform_moby_id:
            return MobyGamesRom(moby_id=None)

        # Check for MobyGames ID tag in filename first
        mobygames_id_from_tag = self.extract_mobygames_id_from_filename(fs_name)
        if mobygames_id_from_tag:
            log.debug(f"Found MobyGames ID tag in filename: {mobygames_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(mobygames_id_from_tag)
            if rom_by_id["moby_id"]:
                log.debug(
                    f"Successfully matched ROM by MobyGames ID tag: {fs_name} -> {mobygames_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"MobyGames ID {mobygames_id_from_tag} from filename tag not found in MobyGames"
                )

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

        normalized_search_term = self.normalize_search_term(
            search_term, remove_punctuation=False
        )
        res = await self._search_rom(
            self.SEARCH_TERM_NORMALIZER.sub(": ", normalized_search_term),
            platform_moby_id,
        )

        # Moby API doesn't handle some special characters well
        if not res:
            terms = re.split(self.SEARCH_TERM_SPLIT_PATTERN, search_term)
            res = await self._search_rom(
                terms[-1], platform_moby_id, split_game_name=True
            )

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
        if not self.is_enabled():
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
        if not self.is_enabled():
            return None

        rom = await self.get_rom_by_id(moby_id)
        return rom if rom["moby_id"] else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_moby_id: int | None
    ) -> list[MobyGamesRom]:
        if not self.is_enabled():
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


MOBYGAMES_PLATFORM_LIST: dict[UPS, SlugToMobyId] = {
    UPS.APVS: {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
        "slug": "1292-advanced-programmable-video-system",
    },
    UPS._3DO: {"id": 35, "name": "3DO", "slug": "3do"},
    UPS.N3DS: {"id": 101, "name": "Nintendo 3DS", "slug": "3ds"},
    UPS.ABC_80: {"id": 318, "name": "ABC 80", "slug": "abc-80"},
    UPS.ACORN_ARCHIMEDES: {
        "id": 117,
        "name": "Acorn Archimedes",
        "slug": "acorn-32-bit",
    },
    UPS.ACORN_ELECTRON: {
        "id": 93,
        "name": "Electron",
        "slug": "electron",
    },
    UPS.ACPC: {"id": 60, "name": "Amstrad CPC", "slug": "cpc"},
    UPS.ADVENTURE_VISION: {
        "id": 210,
        "name": "Adventure Vision",
        "slug": "adventure-vision",
    },
    UPS.AIRCONSOLE: {
        "id": 305,
        "name": "AirConsole",
        "slug": "airconsole",
    },
    UPS.ALICE_3290: {
        "id": 194,
        "name": "Alice 32/90",
        "slug": "alice-3290",
    },
    UPS.ALTAIR_680: {
        "id": 265,
        "name": "Altair 680",
        "slug": "altair-680",
    },
    UPS.ALTAIR_8800: {
        "id": 222,
        "name": "Altair 8800",
        "slug": "altair-8800",
    },
    UPS.AMAZON_ALEXA: {
        "id": 237,
        "name": "Amazon Alexa",
        "slug": "amazon-alexa",
    },
    UPS.AMAZON_FIRE_TV: {
        "id": 159,
        "name": "Fire TV",
        "slug": "fire-os",
    },
    UPS.AMIGA: {"id": 19, "name": "Amiga", "slug": "amiga"},
    UPS.AMIGA_CD32: {
        "id": 56,
        "name": "Amiga CD32",
        "slug": "amiga-cd32",
    },
    UPS.AMSTRAD_PCW: {
        "id": 136,
        "name": "Amstrad PCW",
        "slug": "amstrad-pcw",
    },
    UPS.ANDROID: {"id": 91, "name": "Android", "slug": "android"},
    UPS.ANTSTREAM: {
        "id": 286,
        "name": "Antstream",
        "slug": "antstream",
    },
    UPS.APF: {
        "id": 213,
        "name": "APF MP1000/Imagination Machine",
        "slug": "apf",
    },
    UPS.APPLE: {"id": 245, "name": "Apple I", "slug": "apple-i"},
    UPS.APPLE_IIGS: {
        "id": 51,
        "name": "Apple IIGD",
        "slug": "apple2gs",
    },
    UPS.APPLEII: {"id": 31, "name": "Apple II", "slug": "apple2"},
    UPS.ARCADE: {"id": 143, "name": "Arcade", "slug": "arcade"},
    UPS.ARCADIA_2001: {
        "id": 162,
        "name": "Arcadia 2001",
        "slug": "arcadia-2001",
    },
    UPS.ARDUBOY: {"id": 215, "name": "Arduboy", "slug": "arduboy"},
    UPS.ASTRAL_2000: {
        "id": 241,
        "name": "Astral 2000",
        "slug": "astral-2000",
    },
    UPS.ASTROCADE: {
        "id": 160,
        "name": "Bally Astrocade",
        "slug": "bally-astrocade",
    },
    UPS.ATARI_ST: {"id": 24, "name": "Atari ST", "slug": "atari-st"},
    UPS.ATARI_VCS: {
        "id": 319,
        "name": "Atari VCS",
        "slug": "atari-vcs",
    },
    UPS.ATARI2600: {
        "id": 28,
        "name": "Atari 2600",
        "slug": "atari-2600",
    },
    UPS.ATARI5200: {
        "id": 33,
        "name": "Atari 5200",
        "slug": "atari-5200",
    },
    UPS.ATARI7800: {
        "id": 34,
        "name": "Atari 7800",
        "slug": "atari-7800",
    },
    UPS.ATARI8BIT: {
        "id": 39,
        "name": "Atari 8-bit",
        "slug": "atari-8-bit",
    },
    UPS.ATOM: {"id": 129, "name": "Atom", "slug": "atom"},
    UPS.BADA: {"id": 99, "name": "Bada", "slug": "bada"},
    UPS.BBCMICRO: {
        "id": 92,
        "name": "BBC Micro",
        "slug": "bbc-micro",
    },
    UPS.BEOS: {"id": 165, "name": "BeOS", "slug": "beos"},
    UPS.BLACKBERRY: {
        "id": 90,
        "name": "BlackBerry",
        "slug": "blackberry",
    },
    UPS.BLACKNUT: {"id": 290, "name": "Blacknut", "slug": "blacknut"},
    UPS.BLU_RAY_PLAYER: {
        "id": 169,
        "name": "Blu-ray Player",
        "slug": "blu-ray-disc-player",
    },
    UPS.BREW: {"id": 63, "name": "BREW", "slug": "brew"},
    UPS.BROWSER: {"id": 84, "name": "Browser", "slug": "browser"},
    UPS.BUBBLE: {"id": 231, "name": "Bubble", "slug": "bubble"},
    UPS.C_PLUS_4: {
        "id": 115,
        "name": "Commodore Plus/4",
        "slug": "commodore-16-plus4",
    },
    UPS.C128: {"id": 61, "name": "Commodore 128", "slug": "c128"},
    UPS.C16: {
        "id": 115,
        "name": "Commodore 16",
        "slug": "commodore-16-plus4",
    },
    UPS.C64: {"id": 27, "name": "Commodore 64", "slug": "c64"},
    UPS.CAMPUTERS_LYNX: {
        "id": 154,
        "name": "Camputers Lynx",
        "slug": "camputers-lynx",
    },
    UPS.CASIO_LOOPY: {
        "id": 124,
        "name": "Casio Loopy",
        "slug": "casio-loopy",
    },
    UPS.CASIO_PROGRAMMABLE_CALCULATOR: {
        "id": 306,
        "name": "Casio Programmable Calculator",
        "slug": "casio-programmable-calculator",
    },
    UPS.CASIO_PV_1000: {
        "id": 125,
        "name": "Casio PV-1000",
        "slug": "casio-pv-1000",
    },
    UPS.CHAMPION_2711: {
        "id": 298,
        "name": "Champion 2711",
        "slug": "champion-2711",
    },
    UPS.CLICKSTART: {
        "id": 188,
        "name": "ClickStart",
        "slug": "clickstart",
    },
    UPS.COLECOADAM: {
        "id": 156,
        "name": "Coleco Adam",
        "slug": "colecoadam",
    },
    UPS.COLECOVISION: {
        "id": 29,
        "name": "ColecoVision",
        "slug": "colecovision",
    },
    UPS.COLOUR_GENIE: {
        "id": 197,
        "name": "Colour Genie",
        "slug": "colour-genie",
    },
    UPS.COMMODORE_CDTV: {"id": 83, "name": "CDTV", "slug": "cdtv"},
    UPS.COMPAL_80: {
        "id": 277,
        "name": "Compal 80",
        "slug": "compal-80",
    },
    UPS.COMPUCOLOR_I: {
        "id": 243,
        "name": "Compucolor I",
        "slug": "compucolor-i",
    },
    UPS.COMPUCOLOR_II: {
        "id": 198,
        "name": "Compucolor II",
        "slug": "compucolor-ii",
    },
    UPS.COMPUCORP_PROGRAMMABLE_CALCULATOR: {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
        "slug": "compucorp-programmable-calculator",
    },
    UPS.CPET: {"id": 77, "name": "Commodore PET/CBM", "slug": "pet"},
    UPS.CPM: {"id": 261, "name": "CP/M", "slug": "cpm"},
    UPS.CREATIVISION: {
        "id": 212,
        "name": "CreatiVision",
        "slug": "creativision",
    },
    UPS.CYBERVISION: {
        "id": 301,
        "name": "Cybervision",
        "slug": "cybervision",
    },
    UPS.DANGER_OS: {
        "id": 285,
        "name": "Danger OS",
        "slug": "danger-os",
    },
    UPS.DC: {"id": 8, "name": "Dreamcast", "slug": "dc"},
    UPS.DEDICATED_CONSOLE: {
        "id": 204,
        "name": "Dedicated console",
        "slug": "dedicated-console",
    },
    UPS.DEDICATED_HANDHELD: {
        "id": 205,
        "name": "Dedicated handheld",
        "slug": "dedicated-handheld",
    },
    UPS.DIDJ: {"id": 184, "name": "Didj", "slug": "didj"},
    UPS.DIGIBLAST: {
        "id": 187,
        "name": "digiBlast",
        "slug": "digiblast",
    },
    UPS.DOJA: {"id": 72, "name": "DoJa", "slug": "doja"},
    UPS.DOS: {"id": 2, "name": "DOS", "slug": "dos"},
    UPS.DRAGON_32_SLASH_64: {
        "id": 79,
        "name": "Dragon 32/64",
        "slug": "dragon-3264",
    },
    UPS.DVD_PLAYER: {
        "id": 166,
        "name": "DVD Player",
        "slug": "dvd-player",
    },
    UPS.ECD_MICROMIND: {
        "id": 269,
        "name": "ECD Micromind",
        "slug": "ecd-micromind",
    },
    UPS.ENTERPRISE: {
        "id": 161,
        "name": "Enterprise",
        "slug": "enterprise",
    },
    UPS.EPOCH_CASSETTE_VISION: {
        "id": 137,
        "name": "Epoch Cassette Vision",
        "slug": "epoch-cassette-vision",
    },
    UPS.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 139,
        "name": "Epoch Game Pocket Computer",
        "slug": "epoch-game-pocket-computer",
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 138,
        "name": "Epoch Super Cassette Vision",
        "slug": "epoch-super-cassette-vision",
    },
    UPS.EVERCADE: {"id": 284, "name": "Evercade", "slug": "evercade"},
    UPS.EXELVISION: {
        "id": 195,
        "name": "Exelvision",
        "slug": "exelvision",
    },
    UPS.EXEN: {"id": 70, "name": "ExEn", "slug": "exen"},
    UPS.EXIDY_SORCERER: {
        "id": 176,
        "name": "Exidy Sorcerer",
        "slug": "exidy-sorcerer",
    },
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 76,
        "name": "Channel F",
        "slug": "channel-f",
    },
    UPS.FAMICOM: {
        "id": 22,
        "name": "Family Computer",
        "slug": "famicom",
    },
    UPS.FM_7: {"id": 126, "name": "FM-7", "slug": "fm-7"},
    UPS.FM_TOWNS: {"id": 102, "name": "FM Towns", "slug": "fmtowns"},
    UPS.FRED_COSMAC: {
        "id": 216,
        "name": "COSMAC",
        "slug": "fred-cosmac",
    },
    UPS.FREEBOX: {"id": 268, "name": "Freebox", "slug": "freebox"},
    UPS.G_AND_W: {
        "id": 205,
        "name": "Dedicated handheld",
        "slug": "dedicated-handheld",
    },
    UPS.G_CLUSTER: {
        "id": 302,
        "name": "G-cluster",
        "slug": "g-cluster",
    },
    UPS.GALAKSIJA: {
        "id": 236,
        "name": "Galaksija",
        "slug": "galaksija",
    },
    UPS.GAME_DOT_COM: {
        "id": 50,
        "name": "Game.Com",
        "slug": "game-com",
    },
    UPS.GAME_WAVE: {
        "id": 104,
        "name": "Game Wave",
        "slug": "game-wave",
    },
    UPS.GAMEGEAR: {
        "id": 25,
        "name": "Game Gear",
        "slug": "game-gear",
    },
    UPS.GAMESTICK: {
        "id": 155,
        "name": "GameStick",
        "slug": "gamestick",
    },
    UPS.GB: {"id": 10, "name": "Game Boy", "slug": "gameboy"},
    UPS.GBA: {
        "id": 12,
        "name": "Game Boy Advance",
        "slug": "gameboy-advance",
    },
    UPS.GBC: {
        "id": 11,
        "name": "Game Boy Color",
        "slug": "gameboy-color",
    },
    UPS.GENESIS: {
        "id": 16,
        "name": "Genesis/Mega Drive",
        "slug": "genesis",
    },
    UPS.GIMINI: {"id": 251, "name": "GIMINI", "slug": "gimini"},
    UPS.GIZMONDO: {"id": 55, "name": "Gizmondo", "slug": "gizmondo"},
    UPS.GLOUD: {"id": 292, "name": "Gloud", "slug": "gloud"},
    UPS.GLULX: {"id": 172, "name": "Glulx", "slug": "glulx"},
    UPS.GNEX: {"id": 258, "name": "GNEX", "slug": "gnex"},
    UPS.GP2X: {"id": 122, "name": "GP2X", "slug": "gp2x"},
    UPS.GP2X_WIZ: {"id": 123, "name": "GP2X Wiz", "slug": "gp2x-wiz"},
    UPS.GP32: {"id": 108, "name": "GP32", "slug": "gp32"},
    UPS.GVM: {"id": 257, "name": "GVM", "slug": "gvm"},
    UPS.HD_DVD_PLAYER: {
        "id": 167,
        "name": "HD DVD Player",
        "slug": "hd-dvd-player",
    },
    UPS.HEATHKIT_H11: {
        "id": 248,
        "name": "Heathkit H11",
        "slug": "heathkit-h11",
    },
    UPS.HEATHZENITH: {
        "id": 262,
        "name": "Heath/Zenith H8/H89",
        "slug": "heathzenith",
    },
    UPS.HITACHI_S1: {
        "id": 274,
        "name": "Hitachi S1",
        "slug": "hitachi-s1",
    },
    UPS.HP_9800: {"id": 219, "name": "HP 9800", "slug": "hp-9800"},
    UPS.HP_PROGRAMMABLE_CALCULATOR: {
        "id": 234,
        "name": "HP Programmable Calculator",
        "slug": "hp-programmable-calculator",
    },
    UPS.HUGO: {"id": 170, "name": "Hugo", "slug": "hugo"},
    UPS.HYPERSCAN: {
        "id": 192,
        "name": "HyperScan",
        "slug": "hyperscan",
    },
    UPS.IBM_5100: {"id": 250, "name": "IBM 5100", "slug": "ibm-5100"},
    UPS.IDEAL_COMPUTER: {
        "id": 252,
        "name": "Ideal-Computer",
        "slug": "ideal-computer",
    },
    UPS.IIRCADE: {"id": 314, "name": "iiRcade", "slug": "iircade"},
    UPS.INTEL_8008: {
        "id": 224,
        "name": "Intel 8008",
        "slug": "intel-8008",
    },
    UPS.INTEL_8080: {
        "id": 225,
        "name": "Intel 8080",
        "slug": "intel-8080",
    },
    UPS.INTEL_8086: {
        "id": 317,
        "name": "Intel 8086 / 8088",
        "slug": "intel-8086",
    },
    UPS.INTELLIVISION: {
        "id": 30,
        "name": "Intellivision",
        "slug": "intellivision",
    },
    UPS.INTERACT_MODEL_ONE: {
        "id": 295,
        "name": "Interact Model One",
        "slug": "interact-model-one",
    },
    UPS.INTERTON_VIDEO_2000: {
        "id": 221,
        "name": "Interton Video 2000",
        "slug": "interton-video-2000",
    },
    UPS.IOS: {"id": 86, "name": "iOS", "slug": "iphone"},
    UPS.IPAD: {"id": 96, "name": "iPad", "slug": "ipad"},
    UPS.IPOD_CLASSIC: {
        "id": 80,
        "name": "iPod Classic",
        "slug": "ipod-classic",
    },
    UPS.J2ME: {"id": 64, "name": "J2ME", "slug": "j2me"},
    UPS.JAGUAR: {"id": 17, "name": "Jaguar", "slug": "jaguar"},
    UPS.JOLT: {"id": 247, "name": "Jolt", "slug": "jolt"},
    UPS.JUPITER_ACE: {
        "id": 153,
        "name": "Jupiter Ace",
        "slug": "jupiter-ace",
    },
    UPS.KAIOS: {"id": 313, "name": "KaiOS", "slug": "kaios"},
    UPS.KIM_1: {"id": 226, "name": "KIM-1", "slug": "kim-1"},
    UPS.KINDLE: {
        "id": 145,
        "name": "Kindle Classic",
        "slug": "kindle",
    },
    UPS.LASER200: {
        "id": 264,
        "name": "Laser 200",
        "slug": "laser200",
    },
    UPS.LASERACTIVE: {
        "id": 163,
        "name": "LaserActive",
        "slug": "laseractive",
    },
    UPS.LEAPFROG_EXPLORER: {
        "id": 185,
        "name": "LeapFrog Explorer",
        "slug": "leapfrog-explorer",
    },
    UPS.LEAPSTER: {"id": 183, "name": "Leapster", "slug": "leapster"},
    UPS.LEAPSTER_EXPLORER_SLASH_LEADPAD_EXPLORER: {
        "id": 183,
        "name": "Leapster Explorer/LeapPad Explorer",
        "slug": "leapster",
    },
    UPS.LEAPTV: {"id": 186, "name": "LeapTV", "slug": "leaptv"},
    UPS.LINUX: {"id": 1, "name": "Linux", "slug": "linux"},
    UPS.LUNA: {"id": 297, "name": "Luna", "slug": "luna"},
    UPS.LYNX: {"id": 18, "name": "Lynx", "slug": "lynx"},
    UPS.MAC: {"id": 74, "name": "Macintosh", "slug": "macintosh"},
    UPS.MAEMO: {"id": 157, "name": "Maemo", "slug": "maemo"},
    UPS.MAINFRAME: {
        "id": 208,
        "name": "Mainframe",
        "slug": "mainframe",
    },
    UPS.MATSUSHITAPANASONIC_JR: {
        "id": 307,
        "name": "Matsushita/Panasonic JR",
        "slug": "matsushitapanasonic-jr",
    },
    UPS.AQUARIUS: {
        "id": 135,
        "name": "Mattel Aquarius",
        "slug": "mattel-aquarius",
    },
    UPS.MEEGO: {"id": 158, "name": "MeeGo", "slug": "meego"},
    UPS.MEMOTECH_MTX: {
        "id": 148,
        "name": "Memotech MTX",
        "slug": "memotech-mtx",
    },
    UPS.MERITUM: {"id": 311, "name": "Meritum", "slug": "meritum"},
    UPS.MICROBEE: {"id": 200, "name": "Microbee", "slug": "microbee"},
    UPS.MICROTAN_65: {
        "id": 232,
        "name": "Microtan 65",
        "slug": "microtan-65",
    },
    UPS.MICROVISION: {
        "id": 97,
        "name": "Microvision",
        "slug": "microvision",
    },
    UPS.MOBILE_CUSTOM: {
        "id": 315,
        "name": "Feature phone",
        "slug": "mobile-custom",
    },
    UPS.MOPHUN: {"id": 71, "name": "Mophun", "slug": "mophun"},
    UPS.MOS_TECHNOLOGY_6502: {
        "id": 240,
        "name": "MOS Technology 6502",
        "slug": "mos-technology-6502",
    },
    UPS.MOTOROLA_6800: {
        "id": 235,
        "name": "Motorola 6800",
        "slug": "motorola-6800",
    },
    UPS.MOTOROLA_68K: {
        "id": 275,
        "name": "Motorola 68k",
        "slug": "motorola-68k",
    },
    UPS.MRE: {"id": 229, "name": "MRE", "slug": "mre"},
    UPS.MSX: {"id": 57, "name": "MSX", "slug": "msx"},
    UPS.N64: {"id": 9, "name": "Nintendo 64", "slug": "n64"},
    UPS.NASCOM: {"id": 175, "name": "Nascom", "slug": "nascom"},
    UPS.NDS: {"id": 44, "name": "Nintendo DS", "slug": "nintendo-ds"},
    UPS.NEO_GEO_CD: {
        "id": 54,
        "name": "Neo Geo CD",
        "slug": "neo-geo-cd",
    },
    UPS.NEO_GEO_POCKET: {
        "id": 52,
        "name": "Neo Geo Pocket",
        "slug": "neo-geo-pocket",
    },
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 53,
        "name": "Neo Geo Pocket Color",
        "slug": "neo-geo-pocket-color",
    },
    UPS.NEO_GEO_X: {
        "id": 279,
        "name": "Neo Geo X",
        "slug": "neo-geo-x",
    },
    UPS.NEOGEOAES: {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    UPS.NEOGEOMVS: {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    UPS.NES: {"id": 22, "name": "NES", "slug": "nes"},
    UPS.NEW_NINTENDON3DS: {
        "id": 174,
        "name": "New Nintendo 3DS",
        "slug": "new-nintendo-3ds",
    },
    UPS.NEWBRAIN: {"id": 177, "name": "NewBrain", "slug": "newbrain"},
    UPS.NEWTON: {"id": 207, "name": "Newton", "slug": "newton"},
    UPS.NGAGE: {"id": 32, "name": "N-Gage", "slug": "ngage"},
    UPS.NGAGE2: {
        "id": 89,
        "name": "N-Gage (service)",
        "slug": "ngage2",
    },
    UPS.NGC: {"id": 14, "name": "GameCube", "slug": "gamecube"},
    UPS.NINTENDO_DSI: {
        "id": 87,
        "name": "Nintendo DSi",
        "slug": "nintendo-dsi",
    },
    UPS.NORTHSTAR: {
        "id": 266,
        "name": "North Star",
        "slug": "northstar",
    },
    UPS.NOVAL_760: {
        "id": 244,
        "name": "Noval 760",
        "slug": "noval-760",
    },
    UPS.NUON: {"id": 116, "name": "Nuon", "slug": "nuon"},
    UPS.OCULUS_GO: {
        "id": 218,
        "name": "Oculus Go",
        "slug": "oculus-go",
    },
    UPS.OCULUS_QUEST: {
        "id": 271,
        "name": "Quest",
        "slug": "oculus-quest",
    },
    UPS.ODYSSEY: {"id": 75, "name": "Odyssey", "slug": "odyssey"},
    UPS.ODYSSEY_2: {
        "id": 78,
        "name": "Odyssey 2",
        "slug": "odyssey-2",
    },
    UPS.OHIO_SCIENTIFIC: {
        "id": 178,
        "name": "Ohio Scientific",
        "slug": "ohio-scientific",
    },
    UPS.ONLIVE_GAME_SYSTEM: {
        "id": 282,
        "name": "OnLive Game System",
        "slug": "onlive",
    },
    UPS.OOPARTS: {"id": 300, "name": "OOParts", "slug": "ooparts"},
    UPS.ORAO: {"id": 270, "name": "Orao", "slug": "orao"},
    UPS.ORIC: {"id": 111, "name": "Oric", "slug": "oric"},
    UPS.OS2: {"id": 146, "name": "OS/2", "slug": "os2"},
    UPS.OUYA: {"id": 144, "name": "Ouya", "slug": "ouya"},
    UPS.PALM_OS: {"id": 65, "name": "Palm OS", "slug": "palmos"},
    UPS.PANDORA: {"id": 308, "name": "Pandora", "slug": "pandora"},
    UPS.PC_6001: {"id": 149, "name": "PC-6001", "slug": "pc-6001"},
    UPS.PC_8000: {"id": 201, "name": "PC-8000", "slug": "pc-8000"},
    UPS.PC_8800_SERIES: {
        "id": 94,
        "name": "PC-8800 Series",
        "slug": "pc88",
    },
    UPS.PC_9800_SERIES: {
        "id": 95,
        "name": "PC-9800 Series",
        "slug": "pc98",
    },
    UPS.PC_BOOTER: {
        "id": 4,
        "name": "PC Booter",
        "slug": "pc-booter",
    },
    UPS.PC_FX: {"id": 59, "name": "PC-FX", "slug": "pc-fx"},
    UPS.PEBBLE: {"id": 304, "name": "Pebble", "slug": "pebble"},
    UPS.PHILIPS_CD_I: {"id": 73, "name": "CD-i", "slug": "cd-i"},
    UPS.PHILIPS_VG_5000: {
        "id": 133,
        "name": "Philips VG 5000",
        "slug": "philips-vg-5000",
    },
    UPS.PHOTOCD: {"id": 272, "name": "Photo CD", "slug": "photocd"},
    UPS.PICO: {"id": 316, "name": "PICO", "slug": "pico"},
    UPS.PIPPIN: {"id": 112, "name": "Pippin", "slug": "pippin"},
    UPS.PLAYDATE: {"id": 303, "name": "Playdate", "slug": "playdate"},
    UPS.PLAYDIA: {"id": 107, "name": "Playdia", "slug": "playdia"},
    UPS.PLAYSTATION_NOW: {
        "id": 294,
        "name": "PlayStation Now",
        "slug": "playstation-now",
    },
    UPS.PLEX_ARCADE: {
        "id": 291,
        "name": "Plex Arcade",
        "slug": "plex-arcade",
    },
    UPS.POKEMON_MINI: {
        "id": 152,
        "name": "Pokémon Mini",
        "slug": "pokemon-mini",
    },
    UPS.POKITTO: {"id": 230, "name": "Pokitto", "slug": "pokitto"},
    UPS.POLY_88: {"id": 249, "name": "Poly-88", "slug": "poly-88"},
    UPS.PS2: {
        "id": 7,
        "name": "PlayStation 2",
        "slug": "playstation-2",
    },
    UPS.PS3: {
        "id": 81,
        "name": "PlayStation 3",
        "slug": "playstation-3",
    },
    UPS.PS4: {
        "id": 141,
        "name": "PlayStation 4",
        "slug": "playstation-4",
    },
    UPS.PS5: {
        "id": 288,
        "name": "PlayStation 5",
        "slug": "playstation-5",
    },
    UPS.PSP: {"id": 46, "name": "PSP", "slug": "psp"},
    UPS.PSVITA: {"id": 105, "name": "PS Vita", "slug": "ps-vita"},
    UPS.PSX: {"id": 6, "name": "PlayStation", "slug": "playstation"},
    UPS.RCA_STUDIO_II: {
        "id": 113,
        "name": "RCA Studio II",
        "slug": "rca-studio-ii",
    },
    UPS.RESEARCH_MACHINES_380Z: {
        "id": 309,
        "name": "Research Machines 380Z",
        "slug": "research-machines-380z",
    },
    UPS.ROKU: {"id": 196, "name": "Roku", "slug": "roku"},
    UPS.SAM_COUPE: {
        "id": 120,
        "name": "SAM Coupé",
        "slug": "sam-coupe",
    },
    UPS.SATURN: {
        "id": 23,
        "name": "SEGA Saturn",
        "slug": "sega-saturn",
    },
    UPS.SCMP: {"id": 255, "name": "SC/MP", "slug": "scmp"},
    UPS.SD_200270290: {
        "id": 267,
        "name": "SD-200/270/290",
        "slug": "sd-200270290",
    },
    UPS.SEGA_PICO: {
        "id": 103,
        "name": "SEGA Pico",
        "slug": "sega-pico",
    },
    UPS.SEGA32: {"id": 21, "name": "SEGA 32X", "slug": "sega-32x"},
    UPS.SEGACD: {"id": 20, "name": "SEGA CD", "slug": "sega-cd"},
    UPS.SERIES_X_S: {
        "id": 289,
        "name": "Xbox Series X/S",
        "slug": "xbox-series",
    },
    UPS.SFAM: {"id": 15, "name": "Super Famicom", "slug": "snes"},
    UPS.SG1000: {"id": 114, "name": "SG-1000", "slug": "sg-1000"},
    UPS.SHARP_MZ_80B20002500: {
        "id": 182,
        "name": "Sharp MZ-80B/2000/2500",
        "slug": "sharp-mz-80b20002500",
    },
    UPS.SHARP_MZ_80K7008001500: {
        "id": 181,
        "name": "Sharp MZ-80K/700/800/1500",
        "slug": "sharp-mz-80k7008001500",
    },
    UPS.SHARP_X68000: {
        "id": 106,
        "name": "Sharp X68000",
        "slug": "sharp-x68000",
    },
    UPS.SHARP_ZAURUS: {
        "id": 202,
        "name": "Sharp Zaurus",
        "slug": "sharp-zaurus",
    },
    UPS.SIGNETICS_2650: {
        "id": 278,
        "name": "Signetics 2650",
        "slug": "signetics-2650",
    },
    UPS.SINCLAIR_QL: {
        "id": 131,
        "name": "Sinclair QL",
        "slug": "sinclair-ql",
    },
    UPS.SK_VM: {"id": 259, "name": "SK-VM", "slug": "sk-vm"},
    UPS.SMC_777: {"id": 273, "name": "SMC-777", "slug": "smc-777"},
    UPS.SMS: {
        "id": 26,
        "name": "SEGA Master System",
        "slug": "sega-master-system",
    },
    UPS.SNES: {"id": 15, "name": "SNES", "slug": "snes"},
    UPS.SOCRATES: {"id": 190, "name": "Socrates", "slug": "socrates"},
    UPS.SOL_20: {"id": 199, "name": "Sol-20", "slug": "sol-20"},
    UPS.SORD_M5: {"id": 134, "name": "Sord M5", "slug": "sord-m5"},
    UPS.SPECTRAVIDEO: {
        "id": 85,
        "name": "Spectravideo",
        "slug": "spectravideo",
    },
    UPS.SRI_5001000: {
        "id": 242,
        "name": "SRI-500/1000",
        "slug": "sri-5001000",
    },
    UPS.STADIA: {"id": 281, "name": "Stadia", "slug": "stadia"},
    UPS.SUPER_ACAN: {
        "id": 110,
        "name": "Super A'can",
        "slug": "super-acan",
    },
    UPS.SUPER_VISION_8000: {
        "id": 296,
        "name": "Super Vision 8000",
        "slug": "super-vision-8000",
    },
    UPS.SUPERGRAFX: {
        "id": 127,
        "name": "SuperGrafx",
        "slug": "supergrafx",
    },
    UPS.SUPERVISION: {
        "id": 109,
        "name": "Supervision",
        "slug": "supervision",
    },
    UPS.SURE_SHOT_HD: {
        "id": 287,
        "name": "Sure Shot HD",
        "slug": "sure-shot-hd",
    },
    UPS.SWITCH: {
        "id": 203,
        "name": "Nintendo Switch",
        "slug": "switch",
    },
    UPS.SWITCH_2: {
        "id": -1,
        "name": "Nintendo Switch 2",
        "slug": "switch-2",
    },
    UPS.SWTPC_6800: {
        "id": 228,
        "name": "SWTPC 6800",
        "slug": "swtpc-6800",
    },
    UPS.SYMBIAN: {"id": 67, "name": "Symbian", "slug": "symbian"},
    UPS.TADS: {"id": 171, "name": "TADS", "slug": "tads"},
    UPS.TAITO_X_55: {
        "id": 283,
        "name": "Taito X-55",
        "slug": "taito-x-55",
    },
    UPS.TATUNG_EINSTEIN: {
        "id": 150,
        "name": "Tatung Einstein",
        "slug": "tatung-einstein",
    },
    UPS.TEKTRONIX_4050: {
        "id": 223,
        "name": "Tektronix 4050",
        "slug": "tektronix-4050",
    },
    UPS.TELE_SPIEL: {
        "id": 220,
        "name": "Tele-Spiel ES-2201",
        "slug": "tele-spiel",
    },
    UPS.TELSTAR_ARCADE: {
        "id": 233,
        "name": "Telstar Arcade",
        "slug": "telstar-arcade",
    },
    UPS.TERMINAL: {"id": 209, "name": "Terminal", "slug": "terminal"},
    UPS.TG16: {
        "id": 40,
        "name": "TurboGrafx-16",
        "slug": "turbo-grafx",
    },
    UPS.THOMSON_MO5: {
        "id": 147,
        "name": "Thomson MO5",
        "slug": "thomson-mo",
    },
    UPS.THOMSON_TO: {
        "id": 130,
        "name": "Thomson TO",
        "slug": "thomson-to",
    },
    UPS.TI_99: {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    UPS.TI_994A: {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    UPS.TI_PROGRAMMABLE_CALCULATOR: {
        "id": 239,
        "name": "TI Programmable Calculator",
        "slug": "ti-programmable-calculator",
    },
    UPS.TIKI_100: {"id": 263, "name": "Tiki 100", "slug": "tiki-100"},
    UPS.TIM: {"id": 246, "name": "TIM", "slug": "tim"},
    UPS.TIMEX_SINCLAIR_2068: {
        "id": 173,
        "name": "Timex Sinclair 2068",
        "slug": "timex-sinclair-2068",
    },
    UPS.TIZEN: {"id": 206, "name": "Tizen", "slug": "tizen"},
    UPS.TOMAHAWK_F1: {
        "id": 256,
        "name": "Tomahawk F1",
        "slug": "tomahawk-f1",
    },
    UPS.TOMY_TUTOR: {
        "id": 151,
        "name": "Tomy Tutor",
        "slug": "tomy-tutor",
    },
    UPS.TRITON: {"id": 310, "name": "Triton", "slug": "triton"},
    UPS.TRS_80: {"id": 58, "name": "TRS-80", "slug": "trs-80"},
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 62,
        "name": "TRS-80 Color Computer",
        "slug": "trs-80-coco",
    },
    UPS.TRS_80_MC_10: {
        "id": 193,
        "name": "TRS-80 MC-10",
        "slug": "trs-80-mc-10",
    },
    UPS.TRS_80_MODEL_100: {
        "id": 312,
        "name": "TRS-80 Model 100",
        "slug": "trs-80-model-100",
    },
    UPS.TURBOGRAFX_CD: {
        "id": 45,
        "name": "TurboGrafx CD",
        "slug": "turbografx-cd",
    },
    UPS.TVOS: {"id": 179, "name": "tvOS", "slug": "tvos"},
    UPS.VECTREX: {"id": 37, "name": "Vectrex", "slug": "vectrex"},
    UPS.VERSATILE: {
        "id": 299,
        "name": "Versatile",
        "slug": "versatile",
    },
    UPS.VFLASH: {"id": 189, "name": "V.Flash", "slug": "vflash"},
    UPS.VIC_20: {"id": 43, "name": "VIC-20", "slug": "vic-20"},
    UPS.VIDEOBRAIN: {
        "id": 214,
        "name": "VideoBrain",
        "slug": "videobrain",
    },
    UPS.VIDEOPAC_G7400: {
        "id": 128,
        "name": "Videopac+ G7400",
        "slug": "videopac-g7400",
    },
    UPS.VIRTUALBOY: {
        "id": 38,
        "name": "Virtual Boy",
        "slug": "virtual-boy",
    },
    UPS.VIS: {"id": 164, "name": "VIS", "slug": "vis"},
    UPS.VSMILE: {"id": 42, "name": "V.Smile", "slug": "vsmile"},
    UPS.WANG2200: {
        "id": 217,
        "name": "Wang 2200",
        "slug": "wang2200",
    },
    UPS.WATCHOS: {"id": 180, "name": "watchOS", "slug": "watchos"},
    UPS.WEBOS: {"id": 100, "name": "webOS", "slug": "webos"},
    UPS.WII: {"id": 82, "name": "Wii", "slug": "wii"},
    UPS.WIIU: {"id": 132, "name": "Wii U", "slug": "wii-u"},
    UPS.WIN: {"id": 3, "name": "Windows", "slug": "windows"},
    UPS.WIN3X: {"id": 5, "name": "Windows 3.x", "slug": "win3x"},
    UPS.WINDOWS_APPS: {
        "id": 140,
        "name": "Windows Apps",
        "slug": "windows-apps",
    },
    UPS.WINDOWS_MOBILE: {
        "id": 66,
        "name": "Windows Mobile",
        "slug": "windowsmobile",
    },
    UPS.WINPHONE: {
        "id": 98,
        "name": "Windows Phone",
        "slug": "windows-phone",
    },
    UPS.WIPI: {"id": 260, "name": "WIPI", "slug": "wipi"},
    UPS.WONDERSWAN: {
        "id": 48,
        "name": "WonderSwan",
        "slug": "wonderswan",
    },
    UPS.WONDERSWAN_COLOR: {
        "id": 49,
        "name": "WonderSwan Color",
        "slug": "wonderswan-color",
    },
    UPS.X1: {"id": 121, "name": "Sharp X1", "slug": "sharp-x1"},
    UPS.XAVIXPORT: {
        "id": 191,
        "name": "XaviXPORT",
        "slug": "xavixport",
    },
    UPS.XBOX: {"id": 13, "name": "Xbox", "slug": "xbox"},
    UPS.XBOX360: {"id": 69, "name": "Xbox 360", "slug": "xbox360"},
    UPS.XBOXCLOUDGAMING: {
        "id": 293,
        "name": "Xbox Cloud Gaming",
        "slug": "xboxcloudgaming",
    },
    UPS.XBOXONE: {"id": 142, "name": "Xbox One", "slug": "xbox-one"},
    UPS.XEROX_ALTO: {
        "id": 254,
        "name": "Xerox Alto",
        "slug": "xerox-alto",
    },
    UPS.Z_MACHINE: {
        "id": 169,
        "name": "Z-machine",
        "slug": "z-machine",
    },
    UPS.Z80: {"id": 227, "name": "Zilog Z80", "slug": "z80"},
    UPS.ZEEBO: {"id": 88, "name": "Zeebo", "slug": "zeebo"},
    UPS.ZILOG_Z8000: {
        "id": 276,
        "name": "Zilog Z8000",
        "slug": "zilog-z8000",
    },
    UPS.ZODIAC: {"id": 68, "name": "Zodiac", "slug": "zodiac"},
    UPS.ZUNE: {"id": 211, "name": "Zune", "slug": "zune"},
    UPS.ZXS: {
        "id": 41,
        "name": "ZX Spectrum",
        "slug": "zx-spectrum",
    },
    UPS.ZX_SPECTRUM_NEXT: {
        "id": 280,
        "name": "ZX Spectrum Next",
        "slug": "zx-spectrum-next",
    },
    UPS.ZX80: {"id": 118, "name": "ZX80", "slug": "zx80"},
    UPS.ZX81: {"id": 119, "name": "ZX81", "slug": "zx81"},
}

# Reverse lookup
MOBY_ID_TO_SLUG = {v["id"]: k for k, v in MOBYGAMES_PLATFORM_LIST.items()}


# These platforms are ignored due to lack of data:
# arb, casiofp, dai, hitachibasicmaster3, hposcilloscope, hpseries80

# Need the IDs for these platforms before we can add them:
# p2000, visionos
