import json
from typing import Final, NotRequired, TypedDict

from handler.redis_handler import async_cache
from tasks.update_launchbox_metadata import (  # LAUNCHBOX_PLATFORMS_KEY,; LAUNCHBOX_METADATA_IMAGE_KEY,; LAUNCHBOX_MAME_KEY,; update_launchbox_metadata_task,
    LAUNCHBOX_FILES_KEY,
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
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    launchbox_metadata: NotRequired[LaunchboxMetadata]


def extract_metadata_from_launchbox_rom(index_entry: dict) -> LaunchboxMetadata:
    return LaunchboxMetadata(
        {
            "release_date": index_entry.get("ReleaseDate", ""),
            "max_players": index_entry.get("MaxPlayers", 0),
            "release_type": index_entry.get("ReleaseType", ""),
            "cooperative": index_entry.get("Cooperative", False),
            "video_url": index_entry.get("VideoURL", ""),
            "community_rating": index_entry.get("CommunityRating", 0),
            "community_rating_count": index_entry.get("CommunityRatingCount", 0),
            "wikipedia_url": index_entry.get("WikipediaURL", ""),
            "esrb": index_entry.get("ESRB", ""),
            "genres": index_entry.get("Genres", []),
            "developer": index_entry.get("Developer", ""),
            "publisher": index_entry.get("Publisher", ""),
        }
    )


class LaunchboxHandler(MetadataHandler):
    async def _search_rom(self, file_name: str) -> dict | None:
        file_index_entry = await async_cache.hget(LAUNCHBOX_FILES_KEY, file_name)
        if not file_index_entry:
            return None

        file_index_entry = json.loads(file_index_entry)
        metadata_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_NAME_KEY, file_index_entry["name"]
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
            return LaunchboxRom()

        search_term = fs_rom_handler.get_file_name_with_no_extension(fs_name)
        fallback_rom = LaunchboxRom()

        index_entry = await self._search_rom(search_term)
        if not index_entry:
            return fallback_rom

        rom = {
            "name": index_entry["Name"],
            "summary": index_entry.get("Overview", ""),
            "launchbox_metadata": extract_metadata_from_launchbox_rom(index_entry),
        }

        return LaunchboxRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, database_id: int) -> LaunchboxRom:
        if not LAUNCHBOX_API_ENABLED:
            return LaunchboxRom()

        metadata_database_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_DATABASE_ID_KEY, str(database_id)
        )

        if not metadata_database_index_entry:
            return LaunchboxRom()

        rom = {
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
    "": "GCE Vectrex",
    "": "Game Wave Family Entertainment System",
    "": "GamePark GP32",
    "": "GameWave",
    "": "Hartung Game Master",
    "": "Hector HRX",
    "vc-4000": "Interton VC 4000",
    "": "Jupiter Ace",
    "": "Linux",
    "": "MS-DOS",
    "": "MUGEN",
    "": "Magnavox Odyssey",
    "": "Magnavox Odyssey 2",
    "": "Matra and Hachette Alice",
    "": "Mattel Aquarius",
    "": "Mattel HyperScan",
    "": "Mattel Intellivision",
    "": "Mega Duck",
    "": "Memotech MTX512",
    "": "Microsoft MSX",
    "": "Microsoft MSX2",
    "": "Microsoft MSX2+",
    "": "Microsoft Xbox",
    "": "Microsoft Xbox 360",
    "": "Microsoft Xbox One",
    "": "Microsoft Xbox Series X/S",
    "": "NEC PC-8801",
    "": "NEC PC-9801",
    "": "NEC PC-FX",
    "": "NEC TurboGrafx-16",
    "": "NEC TurboGrafx-CD",
    "": "Namco System 22",
    "": "Nintendo 3DS",
    "": "Nintendo 64",
    "": "Nintendo 64DD",
    "": "Nintendo DS",
    "": "Nintendo Entertainment System",
    "": "Nintendo Famicom Disk System",
    "": "Nintendo Game & Watch",
    "": "Nintendo Game Boy",
    "": "Nintendo Game Boy Advance",
    "": "Nintendo Game Boy Color",
    "": "Nintendo GameCube",
    "": "Nintendo Pokemon Mini",
    "": "Nintendo Satellaview",
    "": "Nintendo Switch",
    "": "Nintendo Switch 2",
    "": "Nintendo Virtual Boy",
    "": "Nintendo Wii",
    "": "Nintendo Wii U",
    "": "Nokia N-Gage",
    "": "Nuon",
    "": "OpenBOR",
    "": "Oric Atmos",
    "": "Othello Multivision",
    "": "Ouya",
    "": "PC Engine SuperGrafx",
    "": "PICO-8",
    "": "Philips CD-i",
    "": "Philips VG 5000",
    "": "Philips Videopac+",
    "": "Pinball",
    "": "RCA Studio II",
    "": "SAM Coupé",
    "": "SNK Neo Geo AES",
    "": "SNK Neo Geo CD",
    "": "SNK Neo Geo MVS",
    "": "SNK Neo Geo Pocket",
    "": "SNK Neo Geo Pocket Color",
    "": "Sammy Atomiswave",
    "": "ScummVM",
    "": "Sega 32X",
    "": "Sega CD",
    "": "Sega CD 32X",
    "": "Sega Dreamcast",
    "": "Sega Dreamcast VMU",
    "": "Sega Game Gear",
    "": "Sega Genesis",
    "": "Sega Hikaru",
    "": "Sega Master System",
    "": "Sega Model 1",
    "": "Sega Model 2",
    "": "Sega Model 3",
    "": "Sega Naomi",
    "": "Sega Naomi 2",
    "": "Sega Pico",
    "": "Sega SC-3000",
    "": "Sega SG-1000",
    "": "Sega ST-V",
    "": "Sega Saturn",
    "": "Sega System 16",
    "": "Sega System 32",
    "": "Sega Triforce",
    "": "Sharp MZ-2500",
    "": "Sharp X1",
    "": "Sharp X68000",
    "": "Sinclair ZX Spectrum",
    "": "Sinclair ZX-81",
    "": "Sony PSP",
    "": "Sony PSP Minis",
    "": "Sony Playstation",
    "": "Sony Playstation 2",
    "": "Sony Playstation 3",
    "": "Sony Playstation 4",
    "": "Sony Playstation 5",
    "": "Sony Playstation Vita",
    "": "Sony PocketStation",
    "": "Sord M5",
    "": "Spectravideo",
    "": "Super Nintendo Entertainment System",
    "": "TRS-80 Color Computer",
    "": "Taito Type X",
    "": "Tandy TRS-80",
    "": "Tapwave Zodiac",
    "": "Texas Instruments TI 99/4A",
    "": "Tiger Game.com",
    "": "Tomy Tutor",
    "": "VTech CreatiVision",
    "": "VTech Socrates",
    "": "VTech V.Smile",
    "": "Vector-06C",
    "": "Watara Supervision",
    "": "Web Browser",
    "": "Windows",
    "": "Windows 3.X",
    "": "WoW Action Max",
    "": "WonderSwan",
    "": "WonderSwan Color",
    "": "XaviXPORT",
    "": "ZiNc",
}

# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in SLUG_TO_LAUNCHBOX_PLATFORM_NAME.items()
}
