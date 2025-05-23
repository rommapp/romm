import json
from typing import Final, NotRequired, TypedDict

from config import str_to_bool
from handler.redis_handler import async_cache
from tasks.update_launchbox_metadata import (  # LAUNCHBOX_PLATFORMS_KEY, LAUNCHBOX_MAME_KEY, update_launchbox_metadata_task,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
)

from .base_hander import MetadataHandler

LAUNCHBOX_API_ENABLED: Final = True


class LaunchboxPlatform(TypedDict):
    slug: str
    launchbox_id: int | None
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
            "genres": (
                index_entry["Genres"].split() if index_entry.get("Genres", None) else []
            ),
            "developer": index_entry.get("Developer") or "",
            "publisher": index_entry.get("Publisher") or "",
        }
    )


class LaunchboxHandler(MetadataHandler):
    async def _get_rom_from_metadata(self, file_name: str) -> dict | None:
        metadata_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_NAME_KEY, file_name
        )

        if metadata_name_index_entry:
            return json.loads(metadata_name_index_entry)

        metadata_alternate_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY, file_name
        )

        if not metadata_alternate_name_index_entry:
            return None

        database_id = metadata_alternate_name_index_entry["DatabaseID"]
        metadata_database_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_DATABASE_ID_KEY, database_id
        )

        if not metadata_database_index_entry:
            return None

        return json.loads(metadata_database_index_entry)

    async def _get_game_images(self, database_id: str) -> list[dict] | None:
        metadata_image_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_IMAGE_KEY, database_id
        )

        if not metadata_image_index_entry:
            return None

        return json.loads(metadata_image_index_entry)

    def _get_best_cover_image(self, game_images: list[dict]) -> dict | None:
        """
        Get the best cover image from a list of game images based on priority order:
        """
        # Define priority order
        priority_types = [
            "Box - Front",
            "Cart - Front",
            "Box - 3D",
            "Cart - 3D",
            "Fanart - Box - Front",
        ]

        for image_type in priority_types:
            for image in game_images:
                if image.get("Type") == image_type:
                    return image

        return None

    def _get_screenshots(self, game_images: list[dict]) -> list[str]:
        screenshots: list[str] = []
        for image in game_images:
            if "Screenshot" in image.get("Type", ""):
                screenshots.append(
                    f"https://images.launchbox-app.com/{image.get('FileName')}"
                )

        return screenshots

    def get_platform(self, slug: str) -> LaunchboxPlatform:
        platform = LAUNCHBOX_PLATFORM_LIST.get(slug, None)

        if not platform:
            return LaunchboxPlatform(slug=slug, launchbox_id=None)

        return LaunchboxPlatform(
            slug=slug,
            launchbox_id=platform["id"],
            name=platform["name"],
        )

    async def get_rom(self, fs_name: str) -> LaunchboxRom:
        from handler.filesystem import fs_rom_handler

        if not LAUNCHBOX_API_ENABLED:
            return LaunchboxRom(launchbox_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = LaunchboxRom(launchbox_id=None)

        index_entry = await self._get_rom_from_metadata(search_term)
        if not index_entry:
            return fallback_rom

        url_cover = None
        url_screenshots = []

        game_images = await self._get_game_images(index_entry["DatabaseID"])
        if game_images:
            best_cover = self._get_best_cover_image(game_images)
            if best_cover:
                url_cover = (
                    f"https://images.launchbox-app.com/{best_cover.get("FileName")}"
                )

            url_screenshots = self._get_screenshots(game_images)

        rom = {
            "launchbox_id": index_entry["DatabaseID"],
            "name": index_entry["Name"],
            "summary": index_entry.get("Overview", ""),
            "url_cover": url_cover,
            "url_screenshots": url_screenshots,
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


LAUNCHBOX_PLATFORM_LIST: dict[str, SlugToLaunchboxPlatformName] = {
    "3do": {"id": 1, "name": "3DO Interactive Multiplayer"},
    "apf": {"id": 2, "name": "APF Imagination Machine"},
    "pegasus": {"id": 3, "name": "Aamber Pegasus"},
    "acorn-archimedes": {"id": 4, "name": "Acorn Archimedes"},
    "atom": {"id": 5, "name": "Acorn Atom"},
    "acorn-electron": {"id": 6, "name": "Acorn Electron"},
    "acpc": {"id": 7, "name": "Amstrad CPC"},
    "gx4000": {"id": 8, "name": "Amstrad GX4000"},
    "android": {"id": 9, "name": "Android"},
    "bk-01": {"id": 10, "name": "Apogee BK-01"},
    "apple2": {"id": 11, "name": "Apple II"},
    "apple2gs": {"id": 12, "name": "Apple IIGS"},
    "mac": {"id": 13, "name": "Apple Mac OS"},
    "ios": {"id": 14, "name": "Apple iOS"},
    "arcade": {"id": 15, "name": "Arcade"},
    "atari2600": {"id": 16, "name": "Atari 2600"},
    "atari5200": {"id": 17, "name": "Atari 5200"},
    "atari7800": {"id": 18, "name": "Atari 7800"},
    "atari800": {"id": 19, "name": "Atari 800"},
    "jaguar": {"id": 20, "name": "Atari Jaguar"},
    "atari-jaguar-cd": {"id": 21, "name": "Atari Jaguar CD"},
    "lynx": {"id": 22, "name": "Atari Lynx"},
    "atari-st": {"id": 23, "name": "Atari ST"},
    "atari-xegs": {"id": 24, "name": "Atari XEGS"},
    "bbcmicro": {"id": 25, "name": "BBC Microcomputer System"},
    "astrocade": {"id": 26, "name": "Bally Astrocade"},
    "super-vision-8000": {"id": 27, "name": "Bandai Super Vision 8000"},
    "camputers-lynx": {"id": 28, "name": "Camputers Lynx"},
    "casio-loopy": {"id": 29, "name": "Casio Loopy"},
    "casio-pv-1000": {"id": 30, "name": "Casio PV-1000"},
    "colecoadam": {"id": 31, "name": "Coleco ADAM"},
    "colecovision": {"id": 32, "name": "ColecoVision"},
    "c128": {"id": 33, "name": "Commodore 128"},
    "c64": {"id": 34, "name": "Commodore 64"},
    "amiga": {"id": 35, "name": "Commodore Amiga"},
    "amiga-cd32": {"id": 36, "name": "Commodore Amiga CD32"},
    "commodore-cdtv": {"id": 37, "name": "Commodore CDTV"},
    "cpet": {"id": 38, "name": "Commodore PET"},
    "c-plus-4": {"id": 39, "name": "Commodore Plus 4"},
    "vic-20": {"id": 40, "name": "Commodore VIC-20"},
    "dragon-32-slash-64": {"id": 41, "name": "Dragon 32/64"},
    "colour-genie": {"id": 42, "name": "EACA EG2000 Colour Genie"},
    "bk": {"id": 43, "name": "Elektronika BK"},
    "arcadia-2001": {"id": 44, "name": "Emerson Arcadia 2001"},
    "enterprise": {"id": 45, "name": "Enterprise"},
    "adventure-vision": {"id": 46, "name": "Entex Adventure Vision"},
    "epoch-game-pocket-computer": {"id": 47, "name": "Epoch Game Pocket Computer"},
    "epoch-super-cassette-vision": {"id": 48, "name": "Epoch Super Cassette Vision"},
    "exelvision": {"id": 49, "name": "Exelvision EXL 100"},
    "exidy-sorcerer": {"id": 50, "name": "Exidy Sorcerer"},
    "fairchild-channel-f": {"id": 51, "name": "Fairchild Channel F"},
    "fm-towns": {"id": 52, "name": "Fujitsu FM Towns Marty"},
    "fm-7": {"id": 53, "name": "Fujitsu FM-7"},
    "super-acan": {"id": 54, "name": "Funtech Super Acan"},
    "vectrex": {"id": 55, "name": "GCE Vectrex"},
    "gp32": {"id": 56, "name": "GamePark GP32"},
    "game-wave": {"id": 57, "name": "GameWave"},
    "hartung": {"id": 58, "name": "Hartung Game Master"},
    "hrx": {"id": 59, "name": "Hector HRX"},
    "vc-4000": {"id": 60, "name": "Interton VC 4000"},
    "jupiter-ace": {"id": 61, "name": "Jupiter Ace"},
    "linux": {"id": 62, "name": "Linux"},
    "dos": {"id": 63, "name": "MS-DOS"},
    "mugen": {"id": 64, "name": "MUGEN"},
    "odyssey--1": {"id": 65, "name": "Magnavox Odyssey"},
    "odyssey-2-slash-videopac-g7000": {"id": 66, "name": "Magnavox Odyssey 2"},
    "alice-3290": {"id": 67, "name": "Matra and Hachette Alice"},
    "mattel-aquarius": {"id": 68, "name": "Mattel Aquarius"},
    "hyperscan": {"id": 69, "name": "Mattel HyperScan"},
    "intellivision": {"id": 70, "name": "Mattel Intellivision"},
    "mega-duck-slash-cougar-boy": {"id": 71, "name": "Mega Duck"},
    "mtx512": {"id": 72, "name": "Memotech MTX512"},
    "msx": {"id": 73, "name": "Microsoft MSX"},
    "msx2": {"id": 74, "name": "Microsoft MSX2"},
    "msx2plus": {"id": 75, "name": "Microsoft MSX2+"},
    "xbox": {"id": 76, "name": "Microsoft Xbox"},
    "xbox360": {"id": 77, "name": "Microsoft Xbox 360"},
    "xboxone": {"id": 78, "name": "Microsoft Xbox One"},
    "series-x": {"id": 79, "name": "Microsoft Xbox Series X/S"},
    "pc-8800-series": {"id": 80, "name": "NEC PC-8801"},
    "pc-9800-series": {"id": 81, "name": "NEC PC-9801"},
    "pc-fx": {"id": 82, "name": "NEC PC-FX"},
    "turbografx16--1": {"id": 83, "name": "NEC TurboGrafx-16"},
    "turbografx-16-slash-pc-engine-cd": {"id": 84, "name": "NEC TurboGrafx-CD"},
    "system-32": {"id": 85, "name": "Namco System 22"},
    "3ds": {"id": 86, "name": "Nintendo 3DS"},
    "n64": {"id": 87, "name": "Nintendo 64"},
    "64dd": {"id": 88, "name": "Nintendo 64DD"},
    "nds": {"id": 89, "name": "Nintendo DS"},
    "nes": {"id": 90, "name": "Nintendo Entertainment System"},
    "famicom": {"id": 91, "name": "Nintendo Famicom Disk System"},
    "g-and-w": {"id": 92, "name": "Nintendo Game & Watch"},
    "gb": {"id": 93, "name": "Nintendo Game Boy"},
    "gba": {"id": 94, "name": "Nintendo Game Boy Advance"},
    "gbc": {"id": 95, "name": "Nintendo Game Boy Color"},
    "ngc": {"id": 96, "name": "Nintendo GameCube"},
    "pokemon-mini": {"id": 97, "name": "Nintendo Pokemon Mini"},
    "satellaview": {"id": 98, "name": "Nintendo Satellaview"},
    "switch": {"id": 99, "name": "Nintendo Switch"},
    "switch2": {"id": 100, "name": "Nintendo Switch 2"},
    "virtualboy": {"id": 101, "name": "Nintendo Virtual Boy"},
    "wii": {"id": 102, "name": "Nintendo Wii"},
    "wiiu": {"id": 103, "name": "Nintendo Wii U"},
    "ngage": {"id": 104, "name": "Nokia N-Gage"},
    "nuon": {"id": 105, "name": "Nuon"},
    "openbor": {"id": 106, "name": "OpenBOR"},
    "atmos": {"id": 107, "name": "Oric Atmos"},
    "multivision": {"id": 108, "name": "Othello Multivision"},
    "ouya": {"id": 109, "name": "Ouya"},
    "supergrafx": {"id": 110, "name": "PC Engine SuperGrafx"},
    "pico": {"id": 111, "name": "PICO-8"},
    "philips-cd-i": {"id": 112, "name": "Philips CD-i"},
    "philips-vg-5000": {"id": 113, "name": "Philips VG 5000"},
    "videopac-g7400": {"id": 114, "name": "Philips Videopac+"},
    "pinball": {"id": 115, "name": "Pinball"},
    "rca-studio-ii": {"id": 116, "name": "RCA Studio II"},
    "sam-coupe": {"id": 117, "name": "SAM Coupé"},
    "neogeoaes": {"id": 118, "name": "SNK Neo Geo AES"},
    "neo-geo-cd": {"id": 119, "name": "SNK Neo Geo CD"},
    "neogeomvs": {"id": 120, "name": "SNK Neo Geo MVS"},
    "neo-geo-pocket": {"id": 121, "name": "SNK Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 122, "name": "SNK Neo Geo Pocket Color"},
    "scummvm": {"id": 123, "name": "ScummVM"},
    "sega32": {"id": 124, "name": "Sega 32X"},
    "segacd": {"id": 125, "name": "Sega CD"},
    "segacd32": {"id": 126, "name": "Sega CD 32X"},
    "dc": {"id": 127, "name": "Sega Dreamcast"},
    "vmu": {"id": 128, "name": "Sega Dreamcast VMU"},
    "gamegear": {"id": 129, "name": "Sega Game Gear"},
    "genesis-slash-megadrive": {"id": 130, "name": "Sega Genesis"},
    "hikaru": {"id": 131, "name": "Sega Hikaru"},
    "sms": {"id": 132, "name": "Sega Master System"},
    "model1": {"id": 133, "name": "Sega Model 1"},
    "model2": {"id": 134, "name": "Sega Model 2"},
    "model3": {"id": 135, "name": "Sega Model 3"},
    "sega-pico": {"id": 136, "name": "Sega Pico"},
    "sc3000": {"id": 137, "name": "Sega SC-3000"},
    "sg1000": {"id": 138, "name": "Sega SG-1000"},
    "stv": {"id": 139, "name": "Sega ST-V"},
    "saturn": {"id": 140, "name": "Sega Saturn"},
    "system16": {"id": 141, "name": "Sega System 16"},
    "system32": {"id": 142, "name": "Sega System 32"},
    "sharp-mz-80b20002500": {"id": 143, "name": "Sharp MZ-2500"},
    "x1": {"id": 144, "name": "Sharp X1"},
    "sharp-x68000": {"id": 145, "name": "Sharp X68000"},
    "zxs": {"id": 146, "name": "Sinclair ZX Spectrum"},
    "sinclair-zx81": {"id": 147, "name": "Sinclair ZX-81"},
    "psp": {"id": 148, "name": "Sony PSP"},
    "psp-minis": {"id": 149, "name": "Sony PSP Minis"},
    "ps": {"id": 150, "name": "Sony Playstation"},
    "ps2": {"id": 151, "name": "Sony Playstation 2"},
    "ps3": {"id": 152, "name": "Sony Playstation 3"},
    "ps4--1": {"id": 153, "name": "Sony Playstation 4"},
    "ps5": {"id": 154, "name": "Sony Playstation 5"},
    "psvita": {"id": 155, "name": "Sony Playstation Vita"},
    "pocketstation": {"id": 156, "name": "Sony PocketStation"},
    "sord-m5": {"id": 157, "name": "Sord M5"},
    "spectravideo": {"id": 158, "name": "Spectravideo"},
    "snes": {"id": 159, "name": "Super Nintendo Entertainment System"},
    "trs-80-color-computer": {"id": 160, "name": "TRS-80 Color Computer"},
    "type-x": {"id": 161, "name": "Taito Type X"},
    "trs-80": {"id": 162, "name": "Tandy TRS-80"},
    "zod": {"id": 163, "name": "Tapwave Zodiac"},
    "ti-994a": {"id": 164, "name": "Texas Instruments TI 99/4A"},
    "game-dot-com": {"id": 165, "name": "Tiger Game.com"},
    "tomy-tutor": {"id": 166, "name": "Tomy Tutor"},
    "creativision": {"id": 167, "name": "VTech CreatiVision"},
    "socrates": {"id": 168, "name": "VTech Socrates"},
    "vsmile": {"id": 169, "name": "VTech V.Smile"},
    "06c": {"id": 170, "name": "Vector-06C"},
    "watara-slash-quickshot-supervision": {"id": 171, "name": "Watara Supervision"},
    "browser": {"id": 172, "name": "Web Browser"},
    "win": {"id": 173, "name": "Windows"},
    "win3x": {"id": 174, "name": "Windows 3.X"},
    "action-max": {"id": 175, "name": "WoW Action Max"},
    "wonderswan": {"id": 176, "name": "WonderSwan"},
    "wonderswan-color": {"id": 177, "name": "WonderSwan Color"},
    "xavixport": {"id": 178, "name": "XaviXPORT"},
    "zinc": {"id": 179, "name": "ZiNc"},
}

# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}
