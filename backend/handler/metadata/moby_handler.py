import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

from adapters.services.mobygames import MobyGamesService
from adapters.services.mobygames_types import MobyGame
from config import MOBYGAMES_API_KEY
from unidecode import unidecode as uc

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
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
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

        search_term = uc(search_term)
        roms = await self.moby_service.list_games(
            platform_ids=[platform_moby_id],
            title=quote(search_term, safe="/ "),
        )
        if not roms:
            return None

        # Find an exact match.
        search_term_casefold = search_term.casefold()
        search_term_normalized = self._normalize_exact_match(search_term)
        for rom in roms:
            if (
                rom["title"].casefold() == search_term_casefold
                or self._normalize_exact_match(rom["title"]) == search_term_normalized
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
            "summary": res.get("description", ""),
            "url_cover": res.get("sample_cover", {}).get("image", ""),
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
            "url_cover": res.get("sample_cover", {}).get("image", None),
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
        matched_roms = await self.moby_service.list_games(
            platform_ids=[platform_moby_id],
            title=quote(search_term, safe="/ "),
        )

        return [
            MobyGamesRom(
                {  # type: ignore[misc]
                    k: v
                    for k, v in {
                        "moby_id": rom["game_id"],
                        "name": rom["title"],
                        "summary": rom.get("description", ""),
                        "url_cover": rom.get("sample_cover", {}).get("image", ""),
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
    slug: NotRequired[str]


MOBYGAMES_PLATFORM_LIST: dict[str, SlugToMobyId] = {
    "1292-advanced-programmable-video-system": {
        "id": 253,
        "name": "1292 Advanced Programmable Video System",
        "slug": "1292-advanced-programmable-video-system",
    },
    "3do": {"id": 35, "name": "3DO", "slug": "3do"},
    "3ds": {"id": 101, "name": "Nintendo 3DS", "slug": "3ds"},
    "abc-80": {"id": 318, "name": "ABC 80", "slug": "abc-80"},
    "acorn-archimedes": {"id": 117, "name": "Acorn Archimedes", "slug": "acorn-32-bit"},
    "acorn-electron": {"id": 93, "name": "Electron", "slug": "electron"},
    "acpc": {"id": 60, "name": "Amstrad CPC", "slug": "cpc"},
    "adventure-vision": {
        "id": 210,
        "name": "Adventure Vision",
        "slug": "adventure-vision",
    },
    "airconsole": {"id": 305, "name": "AirConsole", "slug": "airconsole"},
    "alice-3290": {"id": 194, "name": "Alice 32/90", "slug": "alice-3290"},
    "altair-680": {"id": 265, "name": "Altair 680", "slug": "altair-680"},
    "altair-8800": {"id": 222, "name": "Altair 8800", "slug": "altair-8800"},
    "amazon-alexa": {"id": 237, "name": "Amazon Alexa", "slug": "amazon-alexa"},
    "amazon-fire-tv": {"id": 159, "name": "Fire TV", "slug": "fire-os"},
    "amiga": {"id": 19, "name": "Amiga", "slug": "amiga"},
    "amiga-cd32": {"id": 56, "name": "Amiga CD32", "slug": "amiga-cd32"},
    "amstrad-pcw": {"id": 136, "name": "Amstrad PCW", "slug": "amstrad-pcw"},
    "android": {"id": 91, "name": "Android", "slug": "android"},
    "antstream": {"id": 286, "name": "Antstream", "slug": "antstream"},
    "apf": {"id": 213, "name": "APF MP1000/Imagination Machine", "slug": "apf"},
    "apple": {"id": 245, "name": "Apple I", "slug": "apple-i"},
    "apple-i": {"id": 245, "name": "Apple I", "slug": "apple-i"},
    "apple-iigs": {"id": 51, "name": "Apple IIGD", "slug": "apple2gs"},
    "apple2": {"id": 31, "name": "Apple II", "slug": "apple2"},
    "apple2gs": {"id": 51, "name": "Apple IIGD", "slug": "apple2gs"},
    "appleii": {"id": 31, "name": "Apple II", "slug": "apple2"},
    "arcade": {"id": 143, "name": "Arcade", "slug": "arcade"},
    "arcadia-2001": {"id": 162, "name": "Arcadia 2001", "slug": "arcadia-2001"},
    "arduboy": {"id": 215, "name": "Arduboy", "slug": "arduboy"},
    "astral-2000": {"id": 241, "name": "Astral 2000", "slug": "astral-2000"},
    "astrocade": {"id": 160, "name": "Bally Astrocade", "slug": "bally-astrocade"},
    "atari-2600": {"id": 28, "name": "Atari 2600", "slug": "atari-2600"},
    "atari-5200": {"id": 33, "name": "Atari 5200", "slug": "atari-5200"},
    "atari-7800": {"id": 34, "name": "Atari 7800", "slug": "atari-7800"},
    "atari-8-bit": {"id": 39, "name": "Atari 8-bit", "slug": "atari-8-bit"},
    "atari-st": {"id": 24, "name": "Atari ST", "slug": "atari-st"},
    "atari-vcs": {"id": 319, "name": "Atari VCS", "slug": "atari-vcs"},
    "atari2600": {"id": 28, "name": "Atari 2600", "slug": "atari-2600"},
    "atari5200": {"id": 33, "name": "Atari 5200", "slug": "atari-5200"},
    "atari7800": {"id": 34, "name": "Atari 7800", "slug": "atari-7800"},
    "atari8bit": {"id": 39, "name": "Atari 8-bit", "slug": "atari-8-bit"},
    "atom": {"id": 129, "name": "Atom", "slug": "atom"},
    "bada": {"id": 99, "name": "Bada", "slug": "bada"},
    "bally-astrocade": {
        "id": 160,
        "name": "Bally Astrocade",
        "slug": "bally-astrocade",
    },
    "bbc-micro": {"id": 92, "name": "BBC Micro", "slug": "bbc-micro"},
    "bbcmicro": {"id": 92, "name": "BBC Micro", "slug": "bbc-micro"},
    "beos": {"id": 165, "name": "BeOS", "slug": "beos"},
    "blackberry": {"id": 90, "name": "BlackBerry", "slug": "blackberry"},
    "blacknut": {"id": 290, "name": "Blacknut", "slug": "blacknut"},
    "blu-ray-disc-player": {
        "id": 168,
        "name": "Blu-ray Player",
        "slug": "blu-ray-disc-player",
    },
    "blu-ray-player": {
        "id": 169,
        "name": "Blu-ray Player",
        "slug": "blu-ray-disc-player",
    },
    "brew": {"id": 63, "name": "BREW", "slug": "brew"},
    "browser": {"id": 84, "name": "Browser", "slug": "browser"},
    "bubble": {"id": 231, "name": "Bubble", "slug": "bubble"},
    "c-plus-4": {
        "id": 115,
        "name": "Commodore Plus/4",
        "slug": "commodore-16-plus4",
    },
    "c128": {"id": 61, "name": "Commodore 128", "slug": "c128"},
    "c16": {"id": 115, "name": "Commodore 16", "slug": "commodore-16-plus4"},
    "c64": {"id": 27, "name": "Commodore 64", "slug": "c64"},
    "camputers-lynx": {"id": 154, "name": "Camputers Lynx", "slug": "camputers-lynx"},
    "casio-loopy": {"id": 124, "name": "Casio Loopy", "slug": "casio-loopy"},
    "casio-programmable-calculator": {
        "id": 306,
        "name": "Casio Programmable Calculator",
        "slug": "casio-programmable-calculator",
    },
    "casio-pv-1000": {"id": 125, "name": "Casio PV-1000", "slug": "casio-pv-1000"},
    "cd-i": {"id": 73, "name": "CD-i", "slug": "cd-i"},
    "cdtv": {"id": 83, "name": "CDTV", "slug": "cdtv"},
    "champion-2711": {"id": 298, "name": "Champion 2711", "slug": "champion-2711"},
    "channel-f": {"id": 76, "name": "Channel F", "slug": "channel-f"},
    "clickstart": {"id": 188, "name": "ClickStart", "slug": "clickstart"},
    "colecoadam": {"id": 156, "name": "Coleco Adam", "slug": "colecoadam"},
    "colecovision": {"id": 29, "name": "ColecoVision", "slug": "colecovision"},
    "colour-genie": {"id": 197, "name": "Colour Genie", "slug": "colour-genie"},
    "commodore-16-plus4": {
        "id": 115,
        "name": "Commodore 16, Plus/4",
        "slug": "commodore-16-plus4",
    },
    "commodore-cdtv": {"id": 83, "name": "CDTV", "slug": "cdtv"},
    "compal-80": {"id": 277, "name": "Compal 80", "slug": "compal-80"},
    "compucolor-i": {"id": 243, "name": "Compucolor I", "slug": "compucolor-i"},
    "compucolor-ii": {"id": 198, "name": "Compucolor II", "slug": "compucolor-ii"},
    "compucorp-programmable-calculator": {
        "id": 238,
        "name": "Compucorp Programmable Calculator",
        "slug": "compucorp-programmable-calculator",
    },
    "cpet": {"id": 77, "name": "Commodore PET/CBM", "slug": "pet"},
    "cpm": {"id": 261, "name": "CP/M", "slug": "cpm"},
    "creativision": {"id": 212, "name": "CreatiVision", "slug": "creativision"},
    "cybervision": {"id": 301, "name": "Cybervision", "slug": "cybervision"},
    "danger-os": {"id": 285, "name": "Danger OS", "slug": "danger-os"},
    "dc": {"id": 8, "name": "Dreamcast", "slug": "dc"},
    "dedicated-console": {
        "id": 204,
        "name": "Dedicated console",
        "slug": "dedicated-console",
    },
    "dedicated-handheld": {
        "id": 205,
        "name": "Dedicated handheld",
        "slug": "dedicated-handheld",
    },
    "didj": {"id": 184, "name": "Didj", "slug": "didj"},
    "digiblast": {"id": 187, "name": "digiBlast", "slug": "digiblast"},
    "doja": {"id": 72, "name": "DoJa", "slug": "doja"},
    "dos": {"id": 2, "name": "DOS", "slug": "dos"},
    "dragon-32-slash-64": {"id": 79, "name": "Dragon 32/64", "slug": "dragon-3264"},
    "dragon-3264": {"id": 79, "name": "Dragon 32/64", "slug": "dragon-3264"},
    "dreamcast": {"id": 8, "name": "Dreamcast", "slug": "dc"},
    "dvd-player": {"id": 166, "name": "DVD Player", "slug": "dvd-player"},
    "ecd-micromind": {"id": 269, "name": "ECD Micromind", "slug": "ecd-micromind"},
    "electron": {"id": 93, "name": "Electron", "slug": "electron"},
    "enterprise": {"id": 161, "name": "Enterprise", "slug": "enterprise"},
    "epoch-cassette-vision": {
        "id": 137,
        "name": "Epoch Cassette Vision",
        "slug": "epoch-cassette-vision",
    },
    "epoch-game-pocket-computer": {
        "id": 139,
        "name": "Epoch Game Pocket Computer",
        "slug": "epoch-game-pocket-computer",
    },
    "epoch-super-cassette-vision": {
        "id": 138,
        "name": "Epoch Super Cassette Vision",
        "slug": "epoch-super-cassette-vision",
    },
    "evercade": {"id": 284, "name": "Evercade", "slug": "evercade"},
    "exelvision": {"id": 195, "name": "Exelvision", "slug": "exelvision"},
    "exen": {"id": 70, "name": "ExEn", "slug": "exen"},
    "exidy-sorcerer": {"id": 176, "name": "Exidy Sorcerer", "slug": "exidy-sorcerer"},
    "fairchild-channel-f": {"id": 76, "name": "Channel F", "slug": "channel-f"},
    "famicom": {"id": 22, "name": "Family Computer", "slug": "famicom"},
    "fire-os": {"id": 159, "name": "Fire OS", "slug": "fire-os"},
    "fm-7": {"id": 126, "name": "FM-7", "slug": "fm-7"},
    "fm-towns": {"id": 102, "name": "FM Towns", "slug": "fmtowns"},
    "fmtowns": {"id": 102, "name": "FM Towns", "slug": "fmtowns"},
    "fred-cosmac": {"id": 216, "name": "COSMAC", "slug": "fred-cosmac"},
    "freebox": {"id": 268, "name": "Freebox", "slug": "freebox"},
    "g-and-w": {"id": 205, "name": "Dedicated handheld", "slug": "dedicated-handheld"},
    "g-cluster": {"id": 302, "name": "G-cluster", "slug": "g-cluster"},
    "galaksija": {"id": 236, "name": "Galaksija", "slug": "galaksija"},
    "game-com": {"id": 50, "name": "Game.Com", "slug": "game-com"},
    "game-dot-com": {"id": 50, "name": "Game.Com", "slug": "game-com"},
    "game-gear": {"id": 25, "name": "Game Gear", "slug": "game-gear"},
    "game-wave": {"id": 104, "name": "Game Wave", "slug": "game-wave"},
    "gameboy": {"id": 10, "name": "Game Boy", "slug": "gameboy"},
    "gameboy-advance": {
        "id": 12,
        "name": "Game Boy Advance",
        "slug": "gameboy-advance",
    },
    "gameboy-color": {"id": 11, "name": "Game Boy Color", "slug": "gameboy-color"},
    "gamecube": {"id": 14, "name": "GameCube", "slug": "gamecube"},
    "gamegear": {"id": 25, "name": "Game Gear", "slug": "game-gear"},
    "gamestick": {"id": 155, "name": "GameStick", "slug": "gamestick"},
    "gb": {"id": 10, "name": "Game Boy", "slug": "gameboy"},
    "gba": {"id": 12, "name": "Game Boy Advance", "slug": "gameboy-advance"},
    "gbc": {"id": 11, "name": "Game Boy Color", "slug": "gameboy-color"},
    "genesis": {"id": 16, "name": "Genesis/Mega Drive", "slug": "genesis"},
    "genesis-slash-megadrive": {
        "id": 16,
        "name": "Genesis/Mega Drive",
        "slug": "genesis",
    },
    "gimini": {"id": 251, "name": "GIMINI", "slug": "gimini"},
    "gizmondo": {"id": 55, "name": "Gizmondo", "slug": "gizmondo"},
    "gloud": {"id": 292, "name": "Gloud", "slug": "gloud"},
    "glulx": {"id": 172, "name": "Glulx", "slug": "glulx"},
    "gnex": {"id": 258, "name": "GNEX", "slug": "gnex"},
    "gp2x": {"id": 122, "name": "GP2X", "slug": "gp2x"},
    "gp2x-wiz": {"id": 123, "name": "GP2X Wiz", "slug": "gp2x-wiz"},
    "gp32": {"id": 108, "name": "GP32", "slug": "gp32"},
    "gvm": {"id": 257, "name": "GVM", "slug": "gvm"},
    "hd-dvd-player": {"id": 167, "name": "HD DVD Player", "slug": "hd-dvd-player"},
    "heathkit-h11": {"id": 248, "name": "Heathkit H11", "slug": "heathkit-h11"},
    "heathzenith": {"id": 262, "name": "Heath/Zenith H8/H89", "slug": "heathzenith"},
    "hitachi-s1": {"id": 274, "name": "Hitachi S1", "slug": "hitachi-s1"},
    "hp-9800": {"id": 219, "name": "HP 9800", "slug": "hp-9800"},
    "hp-programmable-calculator": {
        "id": 234,
        "name": "HP Programmable Calculator",
        "slug": "hp-programmable-calculator",
    },
    "hugo": {"id": 170, "name": "Hugo", "slug": "hugo"},
    "hyperscan": {"id": 192, "name": "HyperScan", "slug": "hyperscan"},
    "ibm-5100": {"id": 250, "name": "IBM 5100", "slug": "ibm-5100"},
    "ideal-computer": {"id": 252, "name": "Ideal-Computer", "slug": "ideal-computer"},
    "iircade": {"id": 314, "name": "iiRcade", "slug": "iircade"},
    "intel-8008": {"id": 224, "name": "Intel 8008", "slug": "intel-8008"},
    "intel-8080": {"id": 225, "name": "Intel 8080", "slug": "intel-8080"},
    "intel-8086": {"id": 317, "name": "Intel 8086 / 8088", "slug": "intel-8086"},
    "intellivision": {"id": 30, "name": "Intellivision", "slug": "intellivision"},
    "interact-model-one": {
        "id": 295,
        "name": "Interact Model One",
        "slug": "interact-model-one",
    },
    "interton-video-2000": {
        "id": 221,
        "name": "Interton Video 2000",
        "slug": "interton-video-2000",
    },
    "ios": {"id": 86, "name": "iOS", "slug": "iphone"},
    "ipad": {"id": 96, "name": "iPad", "slug": "ipad"},
    "iphone": {"id": 86, "name": "iPhone", "slug": "iphone"},
    "ipod-classic": {"id": 80, "name": "iPod Classic", "slug": "ipod-classic"},
    "j2me": {"id": 64, "name": "J2ME", "slug": "j2me"},
    "jaguar": {"id": 17, "name": "Jaguar", "slug": "jaguar"},
    "jolt": {"id": 247, "name": "Jolt", "slug": "jolt"},
    "jupiter-ace": {"id": 153, "name": "Jupiter Ace", "slug": "jupiter-ace"},
    "kaios": {"id": 313, "name": "KaiOS", "slug": "kaios"},
    "kim-1": {"id": 226, "name": "KIM-1", "slug": "kim-1"},
    "kindle": {"id": 145, "name": "Kindle Classic", "slug": "kindle"},
    "laser200": {"id": 264, "name": "Laser 200", "slug": "laser200"},
    "laseractive": {"id": 163, "name": "LaserActive", "slug": "laseractive"},
    "leapfrog-explorer": {
        "id": 185,
        "name": "LeapFrog Explorer",
        "slug": "leapfrog-explorer",
    },
    "leapster": {"id": 183, "name": "Leapster", "slug": "leapster"},
    "leapster-explorer-slash-leadpad-explorer": {
        "id": 183,
        "name": "Leapster Explorer/LeapPad Explorer",
        "slug": "leapster",
    },
    "leaptv": {"id": 186, "name": "LeapTV", "slug": "leaptv"},
    "linux": {"id": 1, "name": "Linux", "slug": "linux"},
    "luna": {"id": 297, "name": "Luna", "slug": "luna"},
    "lynx": {"id": 18, "name": "Lynx", "slug": "lynx"},
    "mac": {"id": 74, "name": "Macintosh", "slug": "macintosh"},
    "macintosh": {"id": 74, "name": "Macintosh", "slug": "macintosh"},
    "maemo": {"id": 157, "name": "Maemo", "slug": "maemo"},
    "mainframe": {"id": 208, "name": "Mainframe", "slug": "mainframe"},
    "matsushitapanasonic-jr": {
        "id": 307,
        "name": "Matsushita/Panasonic JR",
        "slug": "matsushitapanasonic-jr",
    },
    "mattel-aquarius": {
        "id": 135,
        "name": "Mattel Aquarius",
        "slug": "mattel-aquarius",
    },
    "meego": {"id": 158, "name": "MeeGo", "slug": "meego"},
    "memotech-mtx": {"id": 148, "name": "Memotech MTX", "slug": "memotech-mtx"},
    "meritum": {"id": 311, "name": "Meritum", "slug": "meritum"},
    "microbee": {"id": 200, "name": "Microbee", "slug": "microbee"},
    "microtan-65": {"id": 232, "name": "Microtan 65", "slug": "microtan-65"},
    "microvision": {"id": 97, "name": "Microvision", "slug": "microvision"},
    "microvision--1": {"id": 97, "name": "Microvision", "slug": "microvision"},
    "mobile-custom": {"id": 315, "name": "Feature phone", "slug": "mobile-custom"},
    "mophun": {"id": 71, "name": "Mophun", "slug": "mophun"},
    "mos-technology-6502": {
        "id": 240,
        "name": "MOS Technology 6502",
        "slug": "mos-technology-6502",
    },
    "motorola-6800": {"id": 235, "name": "Motorola 6800", "slug": "motorola-6800"},
    "motorola-68k": {"id": 275, "name": "Motorola 68k", "slug": "motorola-68k"},
    "mre": {"id": 229, "name": "MRE", "slug": "mre"},
    "msx": {"id": 57, "name": "MSX", "slug": "msx"},
    "n64": {"id": 9, "name": "Nintendo 64", "slug": "n64"},
    "nascom": {"id": 175, "name": "Nascom", "slug": "nascom"},
    "nds": {"id": 44, "name": "Nintendo DS", "slug": "nintendo-ds"},
    "neo-geo": {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    "neo-geo-cd": {"id": 54, "name": "Neo Geo CD", "slug": "neo-geo-cd"},
    "neo-geo-pocket": {"id": 52, "name": "Neo Geo Pocket", "slug": "neo-geo-pocket"},
    "neo-geo-pocket-color": {
        "id": 53,
        "name": "Neo Geo Pocket Color",
        "slug": "neo-geo-pocket-color",
    },
    "neo-geo-x": {"id": 279, "name": "Neo Geo X", "slug": "neo-geo-x"},
    "neogeoaes": {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    "neogeomvs": {"id": 36, "name": "Neo Geo", "slug": "neo-geo"},
    "nes": {"id": 22, "name": "NES", "slug": "nes"},
    "new-nintendo-3ds": {
        "id": 174,
        "name": "New Nintendo 3DS",
        "slug": "new-nintendo-3ds",
    },
    "newbrain": {"id": 177, "name": "NewBrain", "slug": "newbrain"},
    "newton": {"id": 207, "name": "Newton", "slug": "newton"},
    "ngage": {"id": 32, "name": "N-Gage", "slug": "ngage"},
    "ngage2": {"id": 89, "name": "N-Gage (service)", "slug": "ngage2"},
    "ngc": {"id": 14, "name": "GameCube", "slug": "gamecube"},
    "nintendo-ds": {"id": 44, "name": "Nintendo DS", "slug": "nintendo-ds"},
    "nintendo-dsi": {"id": 87, "name": "Nintendo DSi", "slug": "nintendo-dsi"},
    "northstar": {"id": 266, "name": "North Star", "slug": "northstar"},
    "noval-760": {"id": 244, "name": "Noval 760", "slug": "noval-760"},
    "nuon": {"id": 116, "name": "Nuon", "slug": "nuon"},
    "oculus-go": {"id": 218, "name": "Oculus Go", "slug": "oculus-go"},
    "oculus-quest": {"id": 271, "name": "Quest", "slug": "oculus-quest"},
    "odyssey": {"id": 75, "name": "Odyssey", "slug": "odyssey"},
    "odyssey--1": {"id": 75, "name": "Odyssey", "slug": "odyssey"},
    "odyssey-2": {"id": 78, "name": "Odyssey 2", "slug": "odyssey-2"},
    "odyssey-2-slash-videopac-g7000": {
        "id": 78,
        "name": "Odyssey 2/Videopac G7000",
        "slug": "odyssey-2",
    },
    "ohio-scientific": {
        "id": 178,
        "name": "Ohio Scientific",
        "slug": "ohio-scientific",
    },
    "onlive": {"id": 282, "name": "OnLive", "slug": "onlive"},
    "onlive-game-system": {"id": 282, "name": "OnLive Game System", "slug": "onlive"},
    "ooparts": {"id": 300, "name": "OOParts", "slug": "ooparts"},
    "orao": {"id": 270, "name": "Orao", "slug": "orao"},
    "oric": {"id": 111, "name": "Oric", "slug": "oric"},
    "os2": {"id": 146, "name": "OS/2", "slug": "os2"},
    "ouya": {"id": 144, "name": "Ouya", "slug": "ouya"},
    "palm-os": {"id": 65, "name": "Palm OS", "slug": "palmos"},
    "palmos": {"id": 65, "name": "Palm OS", "slug": "palmos"},
    "pandora": {"id": 308, "name": "Pandora", "slug": "pandora"},
    "pc-6001": {"id": 149, "name": "PC-6001", "slug": "pc-6001"},
    "pc-8000": {"id": 201, "name": "PC-8000", "slug": "pc-8000"},
    "pc-8800-series": {"id": 94, "name": "PC-8800 Series", "slug": "pc88"},
    "pc-9800-series": {"id": 95, "name": "PC-9800 Series", "slug": "pc98"},
    "pc-booter": {"id": 4, "name": "PC Booter", "slug": "pc-booter"},
    "pc-fx": {"id": 59, "name": "PC-FX", "slug": "pc-fx"},
    "pc88": {"id": 94, "name": "PC-88", "slug": "pc88"},
    "pc98": {"id": 95, "name": "PC-98", "slug": "pc98"},
    "pebble": {"id": 304, "name": "Pebble", "slug": "pebble"},
    "pet": {"id": 77, "name": "Commodore PET/CBM", "slug": "pet"},
    "philips-cd-i": {"id": 73, "name": "CD-i", "slug": "cd-i"},
    "philips-vg-5000": {
        "id": 133,
        "name": "Philips VG 5000",
        "slug": "philips-vg-5000",
    },
    "photocd": {"id": 272, "name": "Photo CD", "slug": "photocd"},
    "pico": {"id": 316, "name": "PICO", "slug": "pico"},
    "pippin": {"id": 112, "name": "Pippin", "slug": "pippin"},
    "playdate": {"id": 303, "name": "Playdate", "slug": "playdate"},
    "playdia": {"id": 107, "name": "Playdia", "slug": "playdia"},
    "playstation": {"id": 6, "name": "PlayStation", "slug": "playstation"},
    "playstation-4": {"id": 141, "name": "PlayStation 4", "slug": "playstation-4"},
    "playstation-5": {"id": 288, "name": "PlayStation 5", "slug": "playstation-5"},
    "playstation-now": {
        "id": 294,
        "name": "PlayStation Now",
        "slug": "playstation-now",
    },
    "plex-arcade": {"id": 291, "name": "Plex Arcade", "slug": "plex-arcade"},
    "pokemon-mini": {"id": 152, "name": "Pokémon Mini", "slug": "pokemon-mini"},
    "pokitto": {"id": 230, "name": "Pokitto", "slug": "pokitto"},
    "poly-88": {"id": 249, "name": "Poly-88", "slug": "poly-88"},
    "ps": {"id": 6, "name": "PlayStation", "slug": "playstation"},
    "ps-vita": {"id": 105, "name": "PS Vita", "slug": "ps-vita"},
    "ps2": {"id": 7, "name": "PlayStation 2", "slug": "playstation-2"},
    "ps3": {"id": 81, "name": "PlayStation 3", "slug": "playstation-3"},
    "ps4--1": {"id": 141, "name": "PlayStation 4", "slug": "playstation-4"},
    "ps5": {"id": 288, "name": "PlayStation 5", "slug": "playstation-5"},
    "psp": {"id": 46, "name": "PSP", "slug": "psp"},
    "psvita": {"id": 105, "name": "PS Vita", "slug": "ps-vita"},
    "rca-studio-ii": {"id": 113, "name": "RCA Studio II", "slug": "rca-studio-ii"},
    "research-machines-380z": {
        "id": 309,
        "name": "Research Machines 380Z",
        "slug": "research-machines-380z",
    },
    "roku": {"id": 196, "name": "Roku", "slug": "roku"},
    "sam-coupe": {"id": 120, "name": "SAM Coupé", "slug": "sam-coupe"},
    "saturn": {"id": 23, "name": "SEGA Saturn", "slug": "sega-saturn"},
    "scmp": {"id": 255, "name": "SC/MP", "slug": "scmp"},
    "sd-200270290": {"id": 267, "name": "SD-200/270/290", "slug": "sd-200270290"},
    "sega-32x": {"id": 21, "name": "SEGA 32X", "slug": "sega-32x"},
    "sega-cd": {"id": 20, "name": "SEGA CD", "slug": "sega-cd"},
    "sega-master-system": {
        "id": 26,
        "name": "SEGA Master System",
        "slug": "sega-master-system",
    },
    "sega-pico": {"id": 103, "name": "SEGA Pico", "slug": "sega-pico"},
    "sega-saturn": {"id": 23, "name": "SEGA Saturn", "slug": "sega-saturn"},
    "sega32": {"id": 21, "name": "SEGA 32X", "slug": "sega-32x"},
    "segacd": {"id": 20, "name": "SEGA CD", "slug": "sega-cd"},
    "series-x-s": {"id": 289, "name": "Xbox Series X/S", "slug": "xbox-series"},
    "sfam": {"id": 15, "name": "Super Famicom", "slug": "snes"},
    "sg-1000": {"id": 114, "name": "SG-1000", "slug": "sg-1000"},
    "sharp-mz-80b20002500": {
        "id": 182,
        "name": "Sharp MZ-80B/2000/2500",
        "slug": "sharp-mz-80b20002500",
    },
    "sharp-mz-80k7008001500": {
        "id": 181,
        "name": "Sharp MZ-80K/700/800/1500",
        "slug": "sharp-mz-80k7008001500",
    },
    "sharp-x1": {"id": 121, "name": "Sharp X1", "slug": "sharp-x1"},
    "sharp-x68000": {"id": 106, "name": "Sharp X68000", "slug": "sharp-x68000"},
    "sharp-zaurus": {"id": 202, "name": "Sharp Zaurus", "slug": "sharp-zaurus"},
    "signetics-2650": {"id": 278, "name": "Signetics 2650", "slug": "signetics-2650"},
    "sinclair-ql": {"id": 131, "name": "Sinclair QL", "slug": "sinclair-ql"},
    "sinclair-zx81": {"id": 119, "name": "ZX81", "slug": "zx81"},
    "sk-vm": {"id": 259, "name": "SK-VM", "slug": "sk-vm"},
    "smc-777": {"id": 273, "name": "SMC-777", "slug": "smc-777"},
    "sms": {"id": 26, "name": "SEGA Master System", "slug": "sega-master-system"},
    "snes": {"id": 15, "name": "SNES", "slug": "snes"},
    "socrates": {"id": 190, "name": "Socrates", "slug": "socrates"},
    "sol-20": {"id": 199, "name": "Sol-20", "slug": "sol-20"},
    "sord-m5": {"id": 134, "name": "Sord M5", "slug": "sord-m5"},
    "spectravideo": {"id": 85, "name": "Spectravideo", "slug": "spectravideo"},
    "sri-5001000": {"id": 242, "name": "SRI-500/1000", "slug": "sri-5001000"},
    "stadia": {"id": 281, "name": "Stadia", "slug": "stadia"},
    "super-acan": {"id": 110, "name": "Super A'can", "slug": "super-acan"},
    "super-vision-8000": {
        "id": 296,
        "name": "Super Vision 8000",
        "slug": "super-vision-8000",
    },
    "supergrafx": {"id": 127, "name": "SuperGrafx", "slug": "supergrafx"},
    "supervision": {"id": 109, "name": "Supervision", "slug": "supervision"},
    "sure-shot-hd": {"id": 287, "name": "Sure Shot HD", "slug": "sure-shot-hd"},
    "switch": {"id": 203, "name": "Nintendo Switch", "slug": "switch"},
    "switch2": {"id": -1, "name": "Nintendo Switch 2", "slug": "switch-2"},
    "swtpc-6800": {"id": 228, "name": "SWTPC 6800", "slug": "swtpc-6800"},
    "symbian": {"id": 67, "name": "Symbian", "slug": "symbian"},
    "tads": {"id": 171, "name": "TADS", "slug": "tads"},
    "taito-x-55": {"id": 283, "name": "Taito X-55", "slug": "taito-x-55"},
    "tatung-einstein": {
        "id": 150,
        "name": "Tatung Einstein",
        "slug": "tatung-einstein",
    },
    "tektronix-4050": {"id": 223, "name": "Tektronix 4050", "slug": "tektronix-4050"},
    "tele-spiel": {"id": 220, "name": "Tele-Spiel ES-2201", "slug": "tele-spiel"},
    "telstar-arcade": {"id": 233, "name": "Telstar Arcade", "slug": "telstar-arcade"},
    "terminal": {"id": 209, "name": "Terminal", "slug": "terminal"},
    "thomson-mo": {"id": 147, "name": "Thomson MO", "slug": "thomson-mo"},
    "thomson-mo5": {"id": 147, "name": "Thomson MO5", "slug": "thomson-mo"},
    "thomson-to": {"id": 130, "name": "Thomson TO", "slug": "thomson-to"},
    "ti-99": {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    "ti-994a": {"id": 47, "name": "TI-99/4A", "slug": "ti-994a"},
    "ti-programmable-calculator": {
        "id": 239,
        "name": "TI Programmable Calculator",
        "slug": "ti-programmable-calculator",
    },
    "tiki-100": {"id": 263, "name": "Tiki 100", "slug": "tiki-100"},
    "tim": {"id": 246, "name": "TIM", "slug": "tim"},
    "timex-sinclair-2068": {
        "id": 173,
        "name": "Timex Sinclair 2068",
        "slug": "timex-sinclair-2068",
    },
    "tizen": {"id": 206, "name": "Tizen", "slug": "tizen"},
    "tomahawk-f1": {"id": 256, "name": "Tomahawk F1", "slug": "tomahawk-f1"},
    "tomy-tutor": {"id": 151, "name": "Tomy Tutor", "slug": "tomy-tutor"},
    "triton": {"id": 310, "name": "Triton", "slug": "triton"},
    "trs-80": {"id": 58, "name": "TRS-80", "slug": "trs-80"},
    "trs-80-coco": {"id": 62, "name": "TRS-80 Color Computer", "slug": "trs-80-coco"},
    "trs-80-color-computer": {
        "id": 62,
        "name": "TRS-80 Color Computer",
        "slug": "trs-80-coco",
    },
    "trs-80-mc-10": {"id": 193, "name": "TRS-80 MC-10", "slug": "trs-80-mc-10"},
    "trs-80-model-100": {
        "id": 312,
        "name": "TRS-80 Model 100",
        "slug": "trs-80-model-100",
    },
    "turbo-grafx": {"id": 40, "name": "TurboGrafx-16", "slug": "turbo-grafx"},
    "turbografx-16-slash-pc-engine-cd": {
        "id": 45,
        "name": "TurboGrafx CD",
        "slug": "turbografx-cd",
    },
    "turbografx-cd": {"id": 45, "name": "TurboGrafx CD", "slug": "turbografx-cd"},
    "turbografx16--1": {"id": 40, "name": "TurboGrafx-16", "slug": "turbo-grafx"},
    "tvos": {"id": 179, "name": "tvOS", "slug": "tvos"},
    "vectrex": {"id": 37, "name": "Vectrex"},
    "versatile": {"id": 299, "name": "Versatile"},
    "vflash": {"id": 189, "name": "V.Flash"},
    "vic-20": {"id": 43, "name": "VIC-20"},
    "videobrain": {"id": 214, "name": "VideoBrain"},
    "videopac-g7400": {"id": 128, "name": "Videopac+ G7400"},
    "virtual-boy": {"id": 38, "name": "Virtual Boy"},
    "virtualboy": {"id": 38, "name": "Virtual Boy"},
    "vis": {"id": 164, "name": "VIS"},
    "vsmile": {"id": 42, "name": "V.Smile"},
    "wang2200": {"id": 217, "name": "Wang 2200"},
    "watchos": {"id": 180, "name": "watchOS"},
    "webos": {"id": 100, "name": "webOS"},
    "wii": {"id": 82, "name": "Wii"},
    "wii-u": {"id": 132, "name": "Wii U"},
    "wiiu": {"id": 132, "name": "Wii U"},
    "win": {"id": 3, "name": "Windows"},
    "win3x": {"id": 5, "name": "Windows 3.x"},
    "windows": {"id": 3, "name": "Windows"},
    "windows-apps": {"id": 140, "name": "Windows Apps"},
    "windows-mobile": {"id": 66, "name": "Windows Mobile"},
    "windows-phone": {"id": 98, "name": "Windows Phone"},
    "windowsmobile": {"id": 66, "name": "Windows Mobile"},
    "winphone": {"id": 98, "name": "Windows Phone"},
    "wipi": {"id": 260, "name": "WIPI"},
    "wonderswan": {"id": 48, "name": "WonderSwan"},
    "wonderswan-color": {"id": 49, "name": "WonderSwan Color"},
    "x1": {"id": 121, "name": "Sharp X1"},
    "xavixport": {"id": 191, "name": "XaviXPORT"},
    "xbox": {"id": 13, "name": "Xbox"},
    "xbox-one": {"id": 142, "name": "Xbox One"},
    "xbox-series": {"id": 289, "name": "Xbox Series"},
    "xbox360": {"id": 69, "name": "Xbox 360"},
    "xboxcloudgaming": {"id": 293, "name": "Xbox Cloud Gaming"},
    "xboxone": {"id": 142, "name": "Xbox One"},
    "xerox-alto": {"id": 254, "name": "Xerox Alto"},
    "z-machine": {"id": 169, "name": "Z-machine"},
    "z80": {"id": 227, "name": "Zilog Z80"},
    "zeebo": {"id": 88, "name": "Zeebo"},
    "zilog-z8000": {"id": 276, "name": "Zilog Z8000"},
    "zodiac": {"id": 68, "name": "Zodiac"},
    "zune": {"id": 211, "name": "Zune"},
    "zx-spectrum": {"id": 41, "name": "ZX Spectrum"},
    "zx-spectrum-next": {"id": 280, "name": "ZX Spectrum Next"},
    "zx80": {"id": 118, "name": "ZX80"},
    "zx81": {"id": 119, "name": "ZX81"},
}


# Reverse lookup
MOBY_ID_TO_SLUG = {v["id"]: k for k, v in MOBYGAMES_PLATFORM_LIST.items()}
