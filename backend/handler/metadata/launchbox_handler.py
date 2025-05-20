import json
from typing import Final, NotRequired, TypedDict

from config import str_to_bool
from handler.redis_handler import async_cache
from tasks.update_launchbox_metadata import (  # LAUNCHBOX_PLATFORMS_KEY,; LAUNCHBOX_METADATA_IMAGE_KEY,; LAUNCHBOX_MAME_KEY,; update_launchbox_metadata_task,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
)

from .base_hander import MetadataHandler

LAUNCHBOX_API_ENABLED: Final = True


class LaunchboxPlatform(TypedDict):
    slug: str
    name: NotRequired[str]


class LaunchboxMetadata(TypedDict):
    release_date: NotRequired[str]
    max_players: NotRequired[int]
    release_type: NotRequired[str]
    cooperative: NotRequired[bool]
    video_url: NotRequired[str]
    community_rating: NotRequired[float]
    community_rating_count: NotRequired[int]
    wikipedia_url: NotRequired[str]
    esrb: NotRequired[str]
    genres: NotRequired[list[str]]
    developer: NotRequired[str]
    publisher: NotRequired[str]


class LaunchboxRom(TypedDict):
    launchbox_id: int | None
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    launchbox_metadata: NotRequired[LaunchboxMetadata]


def extract_metadata_from_launchbox_rom(index_entry: dict) -> LaunchboxMetadata:
    return LaunchboxMetadata(
        {
            "release_date": index_entry.get("ReleaseDate", ""),
            "max_players": int(index_entry.get("MaxPlayers") or 0),
            "release_type": index_entry.get("ReleaseType", ""),
            "cooperative": str_to_bool(index_entry.get("Cooperative") or "false"),
            "video_url": index_entry.get("VideoURL") or "",
            "community_rating": float(index_entry.get("CommunityRating") or 0.0),
            "community_rating_count": int(index_entry.get("CommunityRatingCount") or 0),
            "wikipedia_url": index_entry.get("WikipediaURL", ""),
            "esrb": index_entry.get("ESRB", ""),
            "genres": index_entry.get("Genres", []).split(),
            "developer": index_entry.get("Developer") or "",
            "publisher": index_entry.get("Publisher") or "",
        }
    )


class LaunchboxHandler(MetadataHandler):
    async def _search_rom(self, file_name: str) -> dict | None:
        metadata_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_NAME_KEY, file_name
        )

        if not metadata_name_index_entry:
            return None

        return json.loads(metadata_name_index_entry)

    def get_platform(self, slug: str) -> LaunchboxPlatform:
        platform_name = SLUG_TO_LAUNCHBOX_PLATFORM_NAME.get(slug, None)

        if not platform_name:
            return LaunchboxPlatform(slug=slug)

        return LaunchboxPlatform(
            slug=slug,
            name=platform_name,
        )

    async def get_rom(self, fs_name: str) -> LaunchboxRom:
        from handler.filesystem import fs_rom_handler

        if not LAUNCHBOX_API_ENABLED:
            return LaunchboxRom(launchbox_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = LaunchboxRom(launchbox_id=None)

        index_entry = await self._search_rom(search_term)
        if not index_entry:
            return fallback_rom

        rom = {
            "launchbox_id": index_entry["DatabaseID"],
            "name": index_entry["Name"],
            "summary": index_entry.get("Overview", ""),
            "launchbox_metadata": extract_metadata_from_launchbox_rom(index_entry),
        }

        return LaunchboxRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, database_id: int) -> LaunchboxRom:
        if not LAUNCHBOX_API_ENABLED:
            return LaunchboxRom(launchbox_id=None)

        metadata_database_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_DATABASE_ID_KEY, str(database_id)
        )

        if not metadata_database_index_entry:
            return LaunchboxRom(launchbox_id=None)

        rom = {
            "launchbox_id": database_id,
            "name": metadata_database_index_entry["Name"],
            "summary": metadata_database_index_entry.get("Overview", ""),
            "launchbox_metadata": extract_metadata_from_launchbox_rom(
                metadata_database_index_entry
            ),
        }

        return LaunchboxRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_matched_rom_by_id(self, database_id: int) -> LaunchboxRom | None:
        if not LAUNCHBOX_API_ENABLED:
            return None

        return await self.get_rom_by_id(database_id)


class SlugToLaunchboxPlatformName(TypedDict):
    id: int
    name: str


SLUG_TO_LAUNCHBOX_PLATFORM_NAME = {
    "3do": "3DO Interactive Multiplayer",
    "apf": "APF Imagination Machine",
    "pegasus": "Aamber Pegasus",
    "acorn-archimedes": "Acorn Archimedes",
    "atom": "Acorn Atom",
    "acorn-electron": "Acorn Electron",
    "acpc": "Amstrad CPC",
    "gx4000": "Amstrad GX4000",
    "android": "Android",
    "bk-01": "Apogee BK-01",
    "apple2": "Apple II",
    "apple2gs": "Apple IIGS",
    "mac": "Apple Mac OS",
    "ios": "Apple iOS",
    "arcade": "Arcade",
    "atari2600": "Atari 2600",
    "atari5200": "Atari 5200",
    "atari7800": "Atari 7800",
    "atari800": "Atari 800",
    "jaguar": "Atari Jaguar",
    "atari-jaguar-cd": "Atari Jaguar CD",
    "lynx": "Atari Lynx",
    "atari-st": "Atari ST",
    "atari-xegs": "Atari XEGS",
    "bbcmicro": "BBC Microcomputer System",
    "astrocade": "Bally Astrocade",
    "super-vision-8000": "Bandai Super Vision 8000",
    "camputers-lynx": "Camputers Lynx",
    "casio-loopy": "Casio Loopy",
    "casio-pv-1000": "Casio PV-1000",
    "colecoadam": "Coleco ADAM",
    "colecovision": "ColecoVision",
    "c128": "Commodore 128",
    "c64": "Commodore 64",
    "amiga": "Commodore Amiga",
    "amiga-cd32": "Commodore Amiga CD32",
    "commodore-cdtv": "Commodore CDTV",
    "cpet": "Commodore PET",
    "c-plus-4": "Commodore Plus 4",
    "vic-20": "Commodore VIC-20",
    "dragon-32-slash-64": "Dragon 32/64",
    "colour-genie": "EACA EG2000 Colour Genie",
    "bk": "Elektronika BK",
    "arcadia-2001": "Emerson Arcadia 2001",
    "enterprise": "Enterprise",
    "adventure-vision": "Entex Adventure Vision",
    "epoch-game-pocket-computer": "Epoch Game Pocket Computer",
    "epoch-super-cassette-vision": "Epoch Super Cassette Vision",
    "exelvision": "Exelvision EXL 100",
    "exidy-sorcerer": "Exidy Sorcerer",
    "fairchild-channel-f": "Fairchild Channel F",
    "fm-towns": "Fujitsu FM Towns Marty",
    "fm-7": "Fujitsu FM-7",
    "super-acan": "Funtech Super Acan",
    "vectrex": "GCE Vectrex",
    # "game-wave": "Game Wave Family Entertainment System",
    "gp32": "GamePark GP32",
    "game-wave": "GameWave",
    "hartung": "Hartung Game Master",
    "hrx": "Hector HRX",
    "vc-4000": "Interton VC 4000",
    "jupiter-ace": "Jupiter Ace",
    "linux": "Linux",
    "dos": "MS-DOS",
    "mugen": "MUGEN",
    "odyssey--1": "Magnavox Odyssey",
    "odyssey-2-slash-videopac-g7000": "Magnavox Odyssey 2",
    "alice-3290": "Matra and Hachette Alice",
    "mattel-aquarius": "Mattel Aquarius",
    "hyperscan": "Mattel HyperScan",
    "intellivision": "Mattel Intellivision",
    "mega-duck-slash-cougar-boy": "Mega Duck",
    "mtx512": "Memotech MTX512",
    "msx": "Microsoft MSX",
    "msx2": "Microsoft MSX2",
    "msx2plus": "Microsoft MSX2+",
    "xbox": "Microsoft Xbox",
    "xbox360": "Microsoft Xbox 360",
    "xboxone": "Microsoft Xbox One",
    "series-x": "Microsoft Xbox Series X/S",
    "pc-8800-series": "NEC PC-8801",
    "pc-9800-series": "NEC PC-9801",
    "pc-fx": "NEC PC-FX",
    "turbografx16--1": "NEC TurboGrafx-16",
    "turbografx-16-slash-pc-engine-cd": "NEC TurboGrafx-CD",
    "system-32": "Namco System 22",
    "3ds": "Nintendo 3DS",
    "n64": "Nintendo 64",
    "64dd": "Nintendo 64DD",
    "nds": "Nintendo DS",
    "nes": "Nintendo Entertainment System",
    "famicom": "Nintendo Famicom Disk System",
    "g-and-w": "Nintendo Game & Watch",
    "gb": "Nintendo Game Boy",
    "gba": "Nintendo Game Boy Advance",
    "gbc": "Nintendo Game Boy Color",
    "ngc": "Nintendo GameCube",
    "pokemon-mini": "Nintendo Pokemon Mini",
    "satellaview": "Nintendo Satellaview",
    "switch": "Nintendo Switch",
    "switch2": "Nintendo Switch 2",
    "virtualboy": "Nintendo Virtual Boy",
    "wii": "Nintendo Wii",
    "wiiu": "Nintendo Wii U",
    "ngage": "Nokia N-Gage",
    "nuon": "Nuon",
    "openbor": "OpenBOR",
    "atmos": "Oric Atmos",
    "multivision": "Othello Multivision",
    "ouya": "Ouya",
    "supergrafx": "PC Engine SuperGrafx",
    "pico": "PICO-8",
    "philips-cd-i": "Philips CD-i",
    "philips-vg-5000": "Philips VG 5000",
    "videopac-g7400": "Philips Videopac+",
    "pinball": "Pinball",
    "rca-studio-ii": "RCA Studio II",
    "sam-coupe": "SAM Coupé",
    "neogeoaes": "SNK Neo Geo AES",
    "neo-geo-cd": "SNK Neo Geo CD",
    "neogeomvs": "SNK Neo Geo MVS",
    "neo-geo-pocket": "SNK Neo Geo Pocket",
    "neo-geo-pocket-color": "SNK Neo Geo Pocket Color",
    # "": "Sammy Atomiswave",
    "scummvm": "ScummVM",
    "sega32": "Sega 32X",
    "segacd": "Sega CD",
    "segacd32": "Sega CD 32X",
    "dc": "Sega Dreamcast",
    "vmu": "Sega Dreamcast VMU",
    "gamegear": "Sega Game Gear",
    "genesis-slash-megadrive": "Sega Genesis",
    "hikaru": "Sega Hikaru",
    "sms": "Sega Master System",
    "model1": "Sega Model 1",
    "model2": "Sega Model 2",
    "model3": "Sega Model 3",
    # "": "Sega Naomi",
    # "": "Sega Naomi 2",
    "sega-pico": "Sega Pico",
    "sc3000": "Sega SC-3000",
    "sg1000": "Sega SG-1000",
    "stv": "Sega ST-V",
    "saturn": "Sega Saturn",
    "system16": "Sega System 16",
    "system32": "Sega System 32",
    # "": "Sega Triforce",
    "sharp-mz-80b20002500": "Sharp MZ-2500",
    "x1": "Sharp X1",
    "sharp-x68000": "Sharp X68000",
    "zxs": "Sinclair ZX Spectrum",
    "sinclair-zx81": "Sinclair ZX-81",
    "psp": "Sony PSP",
    "psp-minis": "Sony PSP Minis",
    "ps": "Sony Playstation",
    "ps2": "Sony Playstation 2",
    "ps3": "Sony Playstation 3",
    "ps4--1": "Sony Playstation 4",
    "ps5": "Sony Playstation 5",
    "psvita": "Sony Playstation Vita",
    "pocketstation": "Sony PocketStation",
    "sord-m5": "Sord M5",
    "spectravideo": "Spectravideo",
    "snes": "Super Nintendo Entertainment System",
    "trs-80-color-computer": "TRS-80 Color Computer",
    "type-x": "Taito Type X",
    "trs-80": "Tandy TRS-80",
    "zod": "Tapwave Zodiac",
    "ti-994a": "Texas Instruments TI 99/4A",
    "game-dot-com": "Tiger Game.com",
    "tomy-tutor": "Tomy Tutor",
    "creativision": "VTech CreatiVision",
    "socrates": "VTech Socrates",
    "vsmile": "VTech V.Smile",
    "06c": "Vector-06C",
    "watara-slash-quickshot-supervision": "Watara Supervision",
    "browser": "Web Browser",
    "win": "Windows",
    "win3x": "Windows 3.X",
    "action-max": "WoW Action Max",
    "wonderswan": "WonderSwan",
    "wonderswan-color": "WonderSwan Color",
    "xavixport": "XaviXPORT",
    "zinc": "ZiNc",
}

# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v: k for k, v in SLUG_TO_LAUNCHBOX_PLATFORM_NAME.items()
}
