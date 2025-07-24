import json
from datetime import datetime
from typing import NotRequired, TypedDict

import pydash
from config import LAUNCHBOX_API_ENABLED, str_to_bool
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.scheduled.update_launchbox_metadata import (  # LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    update_launchbox_metadata_task,
)

from .base_hander import BaseRom, MetadataHandler


class LaunchboxPlatform(TypedDict):
    slug: str
    launchbox_id: int | None
    name: NotRequired[str]


class LaunchboxImage(TypedDict):
    url: str
    type: NotRequired[str]
    region: NotRequired[str]


class LaunchboxMetadata(TypedDict):
    first_release_date: int | None
    max_players: NotRequired[int]
    release_type: NotRequired[str]
    cooperative: NotRequired[bool]
    youtube_video_id: NotRequired[str]
    community_rating: NotRequired[float]
    community_rating_count: NotRequired[int]
    wikipedia_url: NotRequired[str]
    esrb: NotRequired[str]
    genres: NotRequired[list[str]]
    companies: NotRequired[list[str]]
    images: list[LaunchboxImage]


class LaunchboxRom(BaseRom):
    launchbox_id: int | None
    launchbox_metadata: NotRequired[LaunchboxMetadata]


def extract_video_id_from_youtube_url(url: str | None) -> str:
    """
    Extracts the video ID from a YouTube URL.
    Returns None if the URL is not a valid YouTube URL.
    """
    if not url:
        return ""

    if "youtube.com/watch?v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1].split("?")[0]

    return ""


def extract_metadata_from_launchbox_rom(
    index_entry: dict, game_images: list[dict] | None
) -> LaunchboxMetadata:
    try:
        first_release_date = int(
            datetime.strptime(
                index_entry["ReleaseDate"], "%Y-%m-%dT%H:%M:%S%z"
            ).timestamp()
        )
    except (ValueError, KeyError, IndexError):
        first_release_date = None

    return LaunchboxMetadata(
        {
            "first_release_date": first_release_date,
            "max_players": int(index_entry.get("MaxPlayers") or 0),
            "release_type": index_entry.get("ReleaseType", ""),
            "cooperative": str_to_bool(index_entry.get("Cooperative") or "false"),
            "youtube_video_id": extract_video_id_from_youtube_url(
                index_entry.get("VideoURL")
            ),
            "community_rating": float(index_entry.get("CommunityRating") or 0.0),
            "community_rating_count": int(index_entry.get("CommunityRatingCount") or 0),
            "wikipedia_url": index_entry.get("WikipediaURL", ""),
            "esrb": index_entry.get("ESRB", "").split(" - ")[0].strip(),
            "genres": (
                index_entry["Genres"].split() if index_entry.get("Genres", None) else []
            ),
            "companies": pydash.compact(
                [
                    index_entry.get("Publisher", None),
                    index_entry.get("Developer", None),
                ]
            ),
            "images": [
                LaunchboxImage(
                    {
                        "url": f"https://images.launchbox-app.com/{image['FileName']}",
                        "type": image.get("Type", ""),
                        "region": image.get("Region", ""),
                    }
                )
                for image in game_images or []
            ],
        }
    )


class LaunchboxHandler(MetadataHandler):
    async def _get_rom_from_metadata(
        self, file_name: str, platform_slug: str
    ) -> dict | None:
        if not (await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)):
            log.info("Fetching the Launchbox Metadata.xml file...")
            await update_launchbox_metadata_task.run(force=True)

            if not (await async_cache.exists(LAUNCHBOX_METADATA_NAME_KEY)):
                log.error("Could not fetch the Launchbox Metadata.xml file")
                return None

        lb_platform = self.get_platform(platform_slug)
        platform_name = lb_platform.get("name", None)
        if not platform_name:
            return None

        metadata_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_NAME_KEY, f"{file_name}:{platform_name}"
        )

        if metadata_name_index_entry:
            return json.loads(metadata_name_index_entry)

        metadata_alternate_name_index_entry = await async_cache.hget(
            LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY, file_name
        )

        if not metadata_alternate_name_index_entry:
            return None

        metadata_alternate_name_index_entry = json.loads(
            metadata_alternate_name_index_entry
        )
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
            "Box - 3D",
            "Fanart - Box - Front",
            "Cart - Front",
            "Cart - 3D",
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

    async def get_rom(self, fs_name: str, platform_slug: str) -> LaunchboxRom:
        from handler.filesystem import fs_rom_handler

        fallback_rom = LaunchboxRom(launchbox_id=None)

        if not LAUNCHBOX_API_ENABLED:
            return fallback_rom

        # We replace " - " with ": " to match Launchbox's naming convention
        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name).replace(
            " - ", ": "
        )
        index_entry = await self._get_rom_from_metadata(search_term, platform_slug)

        if not index_entry:
            return fallback_rom

        url_cover = None
        url_screenshots = []

        game_images = await self._get_game_images(index_entry["DatabaseID"])
        if game_images:
            best_cover = self._get_best_cover_image(game_images)
            if best_cover:
                url_cover = (
                    f"https://images.launchbox-app.com/{best_cover.get('FileName')}"
                )

            url_screenshots = self._get_screenshots(game_images)

        rom = {
            "launchbox_id": index_entry["DatabaseID"],
            "name": index_entry["Name"],
            "summary": index_entry.get("Overview", ""),
            "url_cover": url_cover,
            "url_screenshots": url_screenshots,
            "launchbox_metadata": extract_metadata_from_launchbox_rom(
                index_entry, game_images
            ),
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

        game_images = await self._get_game_images(
            metadata_database_index_entry["DatabaseID"]
        )

        rom = {
            "launchbox_id": database_id,
            "name": metadata_database_index_entry["Name"],
            "summary": metadata_database_index_entry.get("Overview", ""),
            "launchbox_metadata": extract_metadata_from_launchbox_rom(
                metadata_database_index_entry,
                game_images,
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
    "06c": {"id": 199, "name": "Vector-06C"},
    "3do": {"id": 1, "name": "3DO Interactive Multiplayer"},
    "3ds": {"id": 24, "name": "Nintendo 3DS"},
    "64dd": {"id": 194, "name": "Nintendo 64DD"},
    "acorn-archimedes": {"id": 74, "name": "Acorn Archimedes"},
    "acorn-electron": {"id": 65, "name": "Acorn Electron"},
    "acpc": {"id": 3, "name": "Amstrad CPC"},
    "action-max": {"id": 154, "name": "WoW Action Max"},
    "adventure-vision": {"id": 67, "name": "Entex Adventure Vision"},
    "alice-3290": {"id": 189, "name": "Matra and Hachette Alice"},
    "amiga": {"id": 2, "name": "Commodore Amiga"},
    "amiga-cd32": {"id": 119, "name": "Commodore Amiga CD32"},
    "amstrad-gx4000": {"id": 109, "name": "Amstrad GX4000"},
    "android": {"id": 4, "name": "Android"},
    "apf": {"id": 68, "name": "APF Imagination Machine"},
    "apple-iigs": {"id": 112, "name": "Apple IIGS"},
    "appleii": {"id": 110, "name": "Apple II"},
    "arcade": {"id": 5, "name": "Arcade"},
    "arcadia-2001": {"id": 79, "name": "Emerson Arcadia 2001"},
    "astrocade": {"id": 77, "name": "Bally Astrocade"},
    "atari-jaguar-cd": {"id": 10, "name": "Atari Jaguar CD"},
    "atari-st": {"id": 76, "name": "Atari ST"},
    "atari-xegs": {"id": 12, "name": "Atari XEGS"},
    "atari2600": {"id": 6, "name": "Atari 2600"},
    "atari5200": {"id": 7, "name": "Atari 5200"},
    "atari7800": {"id": 8, "name": "Atari 7800"},
    "atari800": {"id": 102, "name": "Atari 800"},
    "atmos": {"id": 64, "name": "Oric Atmos"},
    "atom": {"id": 107, "name": "Acorn Atom"},
    "bbcmicro": {"id": 59, "name": "BBC Microcomputer System"},
    "bk": {"id": 131, "name": "Elektronika BK"},
    "bk-01": {"id": 175, "name": "Apogee BK-01"},
    "browser": {"id": 85, "name": "Web Browser"},
    "c-plus-4": {"id": 121, "name": "Commodore Plus 4"},
    "c128": {"id": 118, "name": "Commodore 128"},
    "c64": {"id": 14, "name": "Commodore 64"},
    "camputers-lynx": {"id": 61, "name": "Camputers Lynx"},
    "casio-loopy": {"id": 114, "name": "Casio Loopy"},
    "casio-pv-1000": {"id": 115, "name": "Casio PV-1000"},
    "colecoadam": {"id": 117, "name": "Coleco Adam"},
    "colecovision": {"id": 13, "name": "ColecoVision"},
    "colour-genie": {"id": 73, "name": "EACA EG2000 Colour Genie"},
    "commodore-cdtv": {"id": 120, "name": "Commodore CDTV"},
    "cpet": {"id": 180, "name": "Commodore PET"},
    "creativision": {"id": 152, "name": "VTech CreatiVision"},
    "dc": {"id": 40, "name": "Sega Dreamcast"},
    "dos": {"id": 83, "name": "MS-DOS"},
    "dragon-32-slash-64": {"id": 66, "name": "Dragon 32/64"},
    "enterprise": {"id": 72, "name": "Enterprise"},
    "epoch-game-pocket-computer": {"id": 132, "name": "Epoch Game Pocket Computer"},
    "epoch-super-cassette-vision": {"id": 81, "name": "Epoch Super Cassette Vision"},
    "exelvision": {"id": 183, "name": "Exelvision EXL 100"},
    "exidy-sorcerer": {"id": 184, "name": "Exidy Sorcerer"},
    "fairchild-channel-f": {"id": 58, "name": "Fairchild Channel F"},
    "famicom": {"id": 157, "name": "Nintendo Famicom Disk System"},
    "fds": {"id": 157, "name": "Nintendo Famicom Disk System"},
    "fm-7": {"id": 186, "name": "Fujitsu FM-7"},
    "fm-towns": {"id": 124, "name": "Fujitsu FM Towns Marty"},
    "g-and-w": {"id": 166, "name": "Nintendo Game & Watch"},
    "game-dot-com": {"id": 63, "name": "Tiger Game.com"},
    "game-wave": {"id": 216, "name": "GameWave"},
    "gamegear": {"id": 41, "name": "Sega Game Gear"},
    "gb": {"id": 28, "name": "Nintendo Game Boy"},
    "gba": {"id": 29, "name": "Nintendo Game Boy Advance"},
    "gbc": {"id": 30, "name": "Nintendo Game Boy Color"},
    "genesis": {"id": 42, "name": "Sega Genesis"},
    "gp32": {"id": 135, "name": "GamePark GP32"},
    "hartung": {"id": 136, "name": "Hartung Game Master"},
    "hikaru": {"id": 208, "name": "Sega Hikaru"},
    "hrx": {"id": 187, "name": "Hector HRX"},
    "hyperscan": {"id": 171, "name": "Mattel HyperScan"},
    "intellivision": {"id": 15, "name": "Mattel Intellivision"},
    "ios": {"id": 18, "name": "Apple iOS"},
    "jaguar": {"id": 9, "name": "Atari Jaguar"},
    "jupiter-ace": {"id": 70, "name": "Jupiter Ace"},
    "linux": {"id": 218, "name": "Linux"},
    "lynx": {"id": 11, "name": "Atari Lynx"},
    "mac": {"id": 16, "name": "Apple Mac OS"},
    "mattel-aquarius": {"id": 69, "name": "Mattel Aquarius"},
    "mega-duck-slash-cougar-boy": {"id": 127, "name": "Mega Duck"},
    "model1": {"id": 104, "name": "Sega Model 1"},
    "model2": {"id": 88, "name": "Sega Model 2"},
    "model3": {"id": 94, "name": "Sega Model 3"},
    "msx": {"id": 82, "name": "Microsoft MSX"},
    "msx2": {"id": 190, "name": "Microsoft MSX2"},
    "msx2plus": {"id": 191, "name": "Microsoft MSX2+"},
    "mtx512": {"id": 60, "name": "Memotech MTX512"},
    "mugen": {"id": 138, "name": "MUGEN"},
    "multivision": {"id": 197, "name": "Othello Multivision"},
    "n64": {"id": 25, "name": "Nintendo 64"},
    "nds": {"id": 26, "name": "Nintendo DS"},
    "neo-geo-cd": {"id": 167, "name": "SNK Neo Geo CD"},
    "neo-geo-pocket": {"id": 21, "name": "SNK Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 22, "name": "SNK Neo Geo Pocket Color"},
    "neogeoaes": {"id": 23, "name": "SNK Neo Geo AES"},
    "neogeomvs": {"id": 210, "name": "SNK Neo Geo MVS"},
    "nes": {"id": 27, "name": "Nintendo Entertainment System"},
    "ngage": {"id": 213, "name": "Nokia N-Gage"},
    "ngc": {"id": 31, "name": "Nintendo GameCube"},
    "nuon": {"id": 126, "name": "Nuon"},
    "odyssey": {"id": 78, "name": "Magnavox Odyssey"},
    "odyssey-2-slash-videopac-g7000": {"id": 57, "name": "Magnavox Odyssey 2"},
    "openbor": {"id": 139, "name": "OpenBOR"},
    "ouya": {"id": 35, "name": "Ouya"},
    "pc-8800-series": {"id": 192, "name": "NEC PC-8801"},
    "pc-9800-series": {"id": 193, "name": "NEC PC-9801"},
    "pc-fx": {"id": 161, "name": "NEC PC-FX"},
    "pegasus": {"id": 174, "name": "Aamber Pegasus"},
    "philips-cd-i": {"id": 37, "name": "Philips CD-i"},
    "philips-vg-5000": {"id": 140, "name": "Philips VG 5000"},
    "pico": {"id": 220, "name": "PICO-8"},
    "pinball": {"id": 151, "name": "Pinball"},
    "pocketstation": {"id": 203, "name": "Sony PocketStation"},
    "pokemon-mini": {"id": 195, "name": "Nintendo Pokemon Mini"},
    "ps2": {"id": 48, "name": "Sony Playstation 2"},
    "ps3": {"id": 49, "name": "Sony Playstation 3"},
    "ps4": {"id": 50, "name": "Sony Playstation 4"},
    "ps5": {"id": 219, "name": "Sony Playstation 5"},
    "psp": {"id": 52, "name": "Sony PSP"},
    "psp-minis": {"id": 202, "name": "Sony PSP Minis"},
    "psvita": {"id": 51, "name": "Sony Playstation Vita"},
    "psx": {"id": 47, "name": "Sony Playstation"},
    "rca-studio-ii": {"id": 142, "name": "RCA Studio II"},
    "sam-coupe": {"id": 71, "name": "SAM Coupé"},
    "satellaview": {"id": 168, "name": "Nintendo Satellaview"},
    "saturn": {"id": 45, "name": "Sega Saturn"},
    "sc3000": {"id": 145, "name": "Sega SC-3000"},
    "scummvm": {"id": 143, "name": "ScummVM"},
    "sega-pico": {"id": 105, "name": "Sega Pico"},
    "sega32": {"id": 38, "name": "Sega 32X"},
    "segacd": {"id": 39, "name": "Sega CD"},
    "segacd32": {"id": 173, "name": "Sega CD 32X"},
    "series-x-s": {"id": 222, "name": "Microsoft Xbox Series X/S"},
    "sfam": {"id": 53, "name": "Super Famicom"},
    "sg1000": {"id": 80, "name": "Sega SG-1000"},
    "sharp-mz-80b20002500": {"id": 205, "name": "Sharp MZ-2500"},
    "sharp-x68000": {"id": 128, "name": "Sharp X68000"},
    "sms": {"id": 43, "name": "Sega Master System"},
    "snes": {"id": 53, "name": "Super Nintendo Entertainment System"},
    "socrates": {"id": 198, "name": "VTech Socrates"},
    "sord-m5": {"id": 148, "name": "Sord M5"},
    "spectravideo": {"id": 201, "name": "Spectravideo"},
    "stv": {"id": 146, "name": "Sega ST-V"},
    "super-vision-8000": {"id": 223, "name": "Bandai Super Vision 8000"},
    "supergrafx": {"id": 162, "name": "PC Engine SuperGrafx"},
    "switch": {"id": 211, "name": "Nintendo Switch"},
    "switch-2": {"id": 224, "name": "Nintendo Switch 2"},
    "system-32": {"id": 93, "name": "Namco System 22"},
    "system16": {"id": 97, "name": "Sega System 16"},
    "system32": {"id": 96, "name": "Sega System 32"},
    "tg16": {"id": 54, "name": "NEC TurboGrafx-16"},
    "ti-994a": {"id": 149, "name": "Texas Instruments TI 99/4A"},
    "tomy-tutor": {"id": 200, "name": "Tomy Tutor"},
    "trs-80": {"id": 129, "name": "Tandy TRS-80"},
    "trs-80-color-computer": {"id": 164, "name": "TRS-80 Color Computer"},
    "turbografx-cd": {"id": 163, "name": "NEC TurboGrafx-CD"},
    "type-x": {"id": 169, "name": "Taito Type X"},
    "vc-4000": {"id": 137, "name": "Interton VC 4000"},
    "vectrex": {"id": 125, "name": "GCE Vectrex"},
    "vic-20": {"id": 122, "name": "Commodore VIC-20"},
    "videopac-g7400": {"id": 141, "name": "Philips Videopac+"},
    "virtualboy": {"id": 32, "name": "Nintendo Virtual Boy"},
    "vmu": {"id": 144, "name": "Sega Dreamcast VMU"},
    "vsmile": {"id": 221, "name": "VTech V.Smile"},
    "supervision": {"id": 153, "name": "Watara Supervision"},
    "wii": {"id": 33, "name": "Nintendo Wii"},
    "wiiu": {"id": 34, "name": "Nintendo Wii U"},
    "win": {"id": 84, "name": "Windows"},
    "win3x": {"id": 212, "name": "Windows 3.X"},
    "wonderswan": {"id": 55, "name": "WonderSwan"},
    "wonderswan-color": {"id": 56, "name": "WonderSwan Color"},
    "x1": {"id": 204, "name": "Sharp X1"},
    "xavixport": {"id": 170, "name": "XaviXPORT"},
    "xbox": {"id": 18, "name": "Microsoft Xbox"},
    "xbox360": {"id": 19, "name": "Microsoft Xbox 360"},
    "xboxone": {"id": 20, "name": "Microsoft Xbox One"},
    "zinc": {"id": 155, "name": "ZiNc"},
    "zod": {"id": 75, "name": "Tapwave Zodiac"},
    "zx81": {"id": 147, "name": "Sinclair ZX-81"},
    "zxs": {"id": 46, "name": "Sinclair ZX Spectrum"},
}


# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}
