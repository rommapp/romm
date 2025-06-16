import json
from typing import NotRequired, TypedDict

from config import LAUNCHBOX_API_ENABLED, str_to_bool
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.update_launchbox_metadata import (  # LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    update_launchbox_metadata_task,
)

from .base_hander import MetadataHandler


class LaunchboxPlatform(TypedDict):
    slug: str
    launchbox_id: int | None
    name: NotRequired[str]


class LaunchboxImage(TypedDict):
    url: str
    type: NotRequired[str]
    region: NotRequired[str]


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
    images: list[LaunchboxImage]


class LaunchboxRom(TypedDict):
    launchbox_id: int | None
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    launchbox_metadata: NotRequired[LaunchboxMetadata]


def extract_metadata_from_launchbox_rom(
    index_entry: dict, game_images: list[dict] | None
) -> LaunchboxMetadata:
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
            log.warning("Fetching the Launchbox Metadata.xml file...")
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

        if not LAUNCHBOX_API_ENABLED:
            return LaunchboxRom(launchbox_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(fs_name)
        fallback_rom = LaunchboxRom(launchbox_id=None)

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
                    f"https://images.launchbox-app.com/{best_cover.get("FileName")}"
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
    "3do": {"id": 1, "name": "3DO Interactive Multiplayer"},
    "apf": {"id": 68, "name": "APF Imagination Machine"},
    "pegasus": {"id": 174, "name": "Aamber Pegasus"},
    "acorn-archimedes": {"id": 74, "name": "Acorn Archimedes"},
    "atom": {"id": 107, "name": "Acorn Atom"},
    "acorn-electron": {"id": 65, "name": "Acorn Electron"},
    "acpc": {"id": 3, "name": "Amstrad CPC"},
    "gx4000": {"id": 109, "name": "Amstrad GX4000"},
    "android": {"id": 4, "name": "Android"},
    "bk-01": {"id": 175, "name": "Apogee BK-01"},
    "appleii": {"id": 110, "name": "Apple II"},
    "apple2": {"id": 111, "name": "Apple II"},
    "apple-iigs": {"id": 112, "name": "Apple IIGS"},
    "apple2gs": {"id": 112, "name": "Apple IIGS"},
    "mac": {"id": 16, "name": "Apple Mac OS"},
    "ios": {"id": 18, "name": "Apple iOS"},
    "arcade": {"id": 5, "name": "Arcade"},
    "atari2600": {"id": 6, "name": "Atari 2600"},
    "atari5200": {"id": 7, "name": "Atari 5200"},
    "atari7800": {"id": 8, "name": "Atari 7800"},
    "atari800": {"id": 102, "name": "Atari 800"},
    "jaguar": {"id": 9, "name": "Atari Jaguar"},
    "atari-jaguar-cd": {"id": 10, "name": "Atari Jaguar CD"},
    "lynx": {"id": 11, "name": "Atari Lynx"},
    "atari-st": {"id": 76, "name": "Atari ST"},
    "atari-xegs": {"id": 12, "name": "Atari XEGS"},
    "bbcmicro": {"id": 59, "name": "BBC Microcomputer System"},
    "astrocade": {"id": 77, "name": "Bally Astrocade"},
    "super-vision-8000": {"id": 223, "name": "Bandai Super Vision 8000"},
    "camputers-lynx": {"id": 61, "name": "Camputers Lynx"},
    "casio-loopy": {"id": 114, "name": "Casio Loopy"},
    "casio-pv-1000": {"id": 115, "name": "Casio PV-1000"},
    "colecoadam": {"id": 117, "name": "Coleco ADAM"},
    "colecovision": {"id": 13, "name": "ColecoVision"},
    "c128": {"id": 118, "name": "Commodore 128"},
    "c64": {"id": 14, "name": "Commodore 64"},
    "amiga": {"id": 2, "name": "Commodore Amiga"},
    "amiga-cd32": {"id": 119, "name": "Commodore Amiga CD32"},
    "commodore-cdtv": {"id": 120, "name": "Commodore CDTV"},
    "cpet": {"id": 180, "name": "Commodore PET"},
    "c-plus-4": {"id": 121, "name": "Commodore Plus 4"},
    "vic-20": {"id": 122, "name": "Commodore VIC-20"},
    "dragon-32-slash-64": {"id": 66, "name": "Dragon 32/64"},
    "colour-genie": {"id": 73, "name": "EACA EG2000 Colour Genie"},
    "bk": {"id": 131, "name": "Elektronika BK"},
    "arcadia-2001": {"id": 79, "name": "Emerson Arcadia 2001"},
    "enterprise": {"id": 72, "name": "Enterprise"},
    "adventure-vision": {"id": 67, "name": "Entex Adventure Vision"},
    "epoch-game-pocket-computer": {"id": 132, "name": "Epoch Game Pocket Computer"},
    "epoch-super-cassette-vision": {"id": 81, "name": "Epoch Super Cassette Vision"},
    "exelvision": {"id": 183, "name": "Exelvision EXL 100"},
    "exidy-sorcerer": {"id": 184, "name": "Exidy Sorcerer"},
    "fairchild-channel-f": {"id": 58, "name": "Fairchild Channel F"},
    "fm-towns": {"id": 124, "name": "Fujitsu FM Towns Marty"},
    "fm-7": {"id": 186, "name": "Fujitsu FM-7"},
    "gp32": {"id": 135, "name": "GamePark GP32"},
    "game-wave": {"id": 216, "name": "GameWave"},
    "vectrex": {"id": 125, "name": "GCE Vectrex"},
    "hartung": {"id": 136, "name": "Hartung Game Master"},
    "hrx": {"id": 187, "name": "Hector HRX"},
    "vc-4000": {"id": 137, "name": "Interton VC 4000"},
    "jupiter-ace": {"id": 70, "name": "Jupiter Ace"},
    "linux": {"id": 218, "name": "Linux"},
    "dos": {"id": 83, "name": "MS-DOS"},
    "mugen": {"id": 138, "name": "MUGEN"},
    "odyssey--1": {"id": 78, "name": "Magnavox Odyssey"},
    "odyssey-2-slash-videopac-g7000": {"id": 57, "name": "Magnavox Odyssey 2"},
    "alice-3290": {"id": 189, "name": "Matra and Hachette Alice"},
    "mattel-aquarius": {"id": 69, "name": "Mattel Aquarius"},
    "hyperscan": {"id": 171, "name": "Mattel HyperScan"},
    "intellivision": {"id": 15, "name": "Mattel Intellivision"},
    "mega-duck-slash-cougar-boy": {"id": 127, "name": "Mega Duck"},
    "mtx512": {"id": 60, "name": "Memotech MTX512"},
    "msx": {"id": 82, "name": "Microsoft MSX"},
    "msx2": {"id": 190, "name": "Microsoft MSX2"},
    "msx2plus": {"id": 191, "name": "Microsoft MSX2+"},
    "xbox": {"id": 18, "name": "Microsoft Xbox"},
    "xbox360": {"id": 19, "name": "Microsoft Xbox 360"},
    "xboxone": {"id": 20, "name": "Microsoft Xbox One"},
    "series-x-s": {"id": 222, "name": "Microsoft Xbox Series X/S"},
    "pc-8800-series": {"id": 192, "name": "NEC PC-8801"},
    "pc-9800-series": {"id": 193, "name": "NEC PC-9801"},
    "pc-fx": {"id": 161, "name": "NEC PC-FX"},
    "turbografx16--1": {"id": 54, "name": "NEC TurboGrafx-16"},
    "turbografx-16-slash-pc-engine-cd": {"id": 163, "name": "NEC TurboGrafx-CD"},
    "system-32": {"id": 93, "name": "Namco System 22"},
    "3ds": {"id": 24, "name": "Nintendo 3DS"},
    "n64": {"id": 25, "name": "Nintendo 64"},
    "64dd": {"id": 194, "name": "Nintendo 64DD"},
    "nds": {"id": 26, "name": "Nintendo DS"},
    "nes": {"id": 27, "name": "Nintendo Entertainment System"},
    "fds": {"id": 157, "name": "Nintendo Famicom Disk System"},
    "famicom": {"id": 157, "name": "Nintendo Famicom Disk System"},
    "g-and-w": {"id": 166, "name": "Nintendo Game & Watch"},
    "gb": {"id": 28, "name": "Nintendo Game Boy"},
    "gba": {"id": 29, "name": "Nintendo Game Boy Advance"},
    "gbc": {"id": 30, "name": "Nintendo Game Boy Color"},
    "ngc": {"id": 31, "name": "Nintendo GameCube"},
    "pokemon-mini": {"id": 195, "name": "Nintendo Pokemon Mini"},
    "satellaview": {"id": 168, "name": "Nintendo Satellaview"},
    "switch": {"id": 211, "name": "Nintendo Switch"},
    "switch2": {"id": 224, "name": "Nintendo Switch 2"},
    "virtualboy": {"id": 32, "name": "Nintendo Virtual Boy"},
    "wii": {"id": 33, "name": "Nintendo Wii"},
    "wiiu": {"id": 34, "name": "Nintendo Wii U"},
    "ngage": {"id": 213, "name": "Nokia N-Gage"},
    "nuon": {"id": 126, "name": "Nuon"},
    "openbor": {"id": 139, "name": "OpenBOR"},
    "atmos": {"id": 64, "name": "Oric Atmos"},
    "multivision": {"id": 197, "name": "Othello Multivision"},
    "ouya": {"id": 35, "name": "Ouya"},
    "supergrafx": {"id": 162, "name": "PC Engine SuperGrafx"},
    "pico": {"id": 220, "name": "PICO-8"},
    "philips-cd-i": {"id": 37, "name": "Philips CD-i"},
    "philips-vg-5000": {"id": 140, "name": "Philips VG 5000"},
    "videopac-g7400": {"id": 141, "name": "Philips Videopac+"},
    "pinball": {"id": 151, "name": "Pinball"},
    "rca-studio-ii": {"id": 142, "name": "RCA Studio II"},
    "sam-coupe": {"id": 71, "name": "SAM Coupé"},
    "neogeoaes": {"id": 23, "name": "SNK Neo Geo AES"},
    "neo-geo-cd": {"id": 167, "name": "SNK Neo Geo CD"},
    "neogeomvs": {"id": 210, "name": "SNK Neo Geo MVS"},
    "neo-geo-pocket": {"id": 21, "name": "SNK Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 22, "name": "SNK Neo Geo Pocket Color"},
    "scummvm": {"id": 143, "name": "ScummVM"},
    "sega32": {"id": 38, "name": "Sega 32X"},
    "segacd": {"id": 39, "name": "Sega CD"},
    "segacd32": {"id": 173, "name": "Sega CD 32X"},
    "dc": {"id": 40, "name": "Sega Dreamcast"},
    "vmu": {"id": 144, "name": "Sega Dreamcast VMU"},
    "gamegear": {"id": 41, "name": "Sega Game Gear"},
    "genesis-slash-megadrive": {"id": 42, "name": "Sega Genesis"},
    "hikaru": {"id": 208, "name": "Sega Hikaru"},
    "sms": {"id": 43, "name": "Sega Master System"},
    "model1": {"id": 104, "name": "Sega Model 1"},
    "model2": {"id": 88, "name": "Sega Model 2"},
    "model3": {"id": 94, "name": "Sega Model 3"},
    "sega-pico": {"id": 105, "name": "Sega Pico"},
    "sc3000": {"id": 145, "name": "Sega SC-3000"},
    "sg1000": {"id": 80, "name": "Sega SG-1000"},
    "stv": {"id": 146, "name": "Sega ST-V"},
    "saturn": {"id": 45, "name": "Sega Saturn"},
    "system16": {"id": 97, "name": "Sega System 16"},
    "system32": {"id": 96, "name": "Sega System 32"},
    "sharp-mz-80b20002500": {"id": 205, "name": "Sharp MZ-2500"},
    "x1": {"id": 204, "name": "Sharp X1"},
    "sharp-x68000": {"id": 128, "name": "Sharp X68000"},
    "zxs": {"id": 46, "name": "Sinclair ZX Spectrum"},
    "sinclair-zx81": {"id": 147, "name": "Sinclair ZX-81"},
    "psp": {"id": 52, "name": "Sony PSP"},
    "psp-minis": {"id": 202, "name": "Sony PSP Minis"},
    "ps": {"id": 47, "name": "Sony Playstation"},
    "ps2": {"id": 48, "name": "Sony Playstation 2"},
    "ps3": {"id": 49, "name": "Sony Playstation 3"},
    "ps4--1": {"id": 50, "name": "Sony Playstation 4"},
    "ps5": {"id": 219, "name": "Sony Playstation 5"},
    "psvita": {"id": 51, "name": "Sony Playstation Vita"},
    "pocketstation": {"id": 203, "name": "Sony PocketStation"},
    "sord-m5": {"id": 148, "name": "Sord M5"},
    "spectravideo": {"id": 201, "name": "Spectravideo"},
    "snes": {"id": 53, "name": "Super Nintendo Entertainment System"},
    "sfam": {"id": 53, "name": "Super Famicom"},
    "trs-80-color-computer": {"id": 164, "name": "TRS-80 Color Computer"},
    "type-x": {"id": 169, "name": "Taito Type X"},
    "trs-80": {"id": 129, "name": "Tandy TRS-80"},
    "zod": {"id": 75, "name": "Tapwave Zodiac"},
    "ti-994a": {"id": 149, "name": "Texas Instruments TI 99/4A"},
    "game-dot-com": {"id": 63, "name": "Tiger Game.com"},
    "tomy-tutor": {"id": 200, "name": "Tomy Tutor"},
    "creativision": {"id": 152, "name": "VTech CreatiVision"},
    "socrates": {"id": 198, "name": "VTech Socrates"},
    "vsmile": {"id": 221, "name": "VTech V.Smile"},
    "06c": {"id": 199, "name": "Vector-06C"},
    "watara-slash-quickshot-supervision": {"id": 153, "name": "Watara Supervision"},
    "browser": {"id": 85, "name": "Web Browser"},
    "win": {"id": 84, "name": "Windows"},
    "win3x": {"id": 212, "name": "Windows 3.X"},
    "action-max": {"id": 154, "name": "WoW Action Max"},
    "wonderswan": {"id": 55, "name": "WonderSwan"},
    "wonderswan-color": {"id": 56, "name": "WonderSwan Color"},
    "xavixport": {"id": 170, "name": "XaviXPORT"},
    "zinc": {"id": 155, "name": "ZiNc"},
}

# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}
