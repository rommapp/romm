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

from .base_hander import BaseRom, MetadataHandler, UniversalPlatformSlug


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


LAUNCHBOX_PLATFORM_LIST: dict[UniversalPlatformSlug, SlugToLaunchboxPlatformName] = {
    UniversalPlatformSlug.VECTOR_06C: {"id": 199, "name": "Vector-06C"},
    UniversalPlatformSlug._3DO: {"id": 1, "name": "3DO Interactive Multiplayer"},
    UniversalPlatformSlug.N3DS: {"id": 24, "name": "Nintendo 3DS"},
    UniversalPlatformSlug.N64DD: {"id": 194, "name": "Nintendo 64DD"},
    UniversalPlatformSlug.ACORN_ARCHIMEDES: {"id": 74, "name": "Acorn Archimedes"},
    UniversalPlatformSlug.ACORN_ELECTRON: {"id": 65, "name": "Acorn Electron"},
    UniversalPlatformSlug.ACPC: {"id": 3, "name": "Amstrad CPC"},
    UniversalPlatformSlug.ACTION_MAX: {"id": 154, "name": "WoW Action Max"},
    UniversalPlatformSlug.ADVENTURE_VISION: {
        "id": 67,
        "name": "Entex Adventure Vision",
    },
    UniversalPlatformSlug.ALICE_3290: {"id": 189, "name": "Matra and Hachette Alice"},
    UniversalPlatformSlug.AMIGA: {"id": 2, "name": "Commodore Amiga"},
    UniversalPlatformSlug.AMIGA_CD32: {"id": 119, "name": "Commodore Amiga CD32"},
    UniversalPlatformSlug.AMSTRAD_GX4000: {"id": 109, "name": "Amstrad GX4000"},
    UniversalPlatformSlug.ANDROID: {"id": 4, "name": "Android"},
    UniversalPlatformSlug.APF: {"id": 68, "name": "APF Imagination Machine"},
    UniversalPlatformSlug.APPLE_IIGS: {"id": 112, "name": "Apple IIGS"},
    UniversalPlatformSlug.APPLEII: {"id": 110, "name": "Apple II"},
    UniversalPlatformSlug.ARCADE: {"id": 5, "name": "Arcade"},
    UniversalPlatformSlug.ARCADIA_2001: {"id": 79, "name": "Emerson Arcadia 2001"},
    UniversalPlatformSlug.ASTROCADE: {"id": 77, "name": "Bally Astrocade"},
    UniversalPlatformSlug.ATARI_JAGUAR_CD: {"id": 10, "name": "Atari Jaguar CD"},
    UniversalPlatformSlug.ATARI_ST: {"id": 76, "name": "Atari ST"},
    UniversalPlatformSlug.ATARI_XEGS: {"id": 12, "name": "Atari XEGS"},
    UniversalPlatformSlug.ATARI2600: {"id": 6, "name": "Atari 2600"},
    UniversalPlatformSlug.ATARI5200: {"id": 7, "name": "Atari 5200"},
    UniversalPlatformSlug.ATARI7800: {"id": 8, "name": "Atari 7800"},
    UniversalPlatformSlug.ATARI800: {"id": 102, "name": "Atari 800"},
    UniversalPlatformSlug.ATMOS: {"id": 64, "name": "Oric Atmos"},
    UniversalPlatformSlug.ATOM: {"id": 107, "name": "Acorn Atom"},
    UniversalPlatformSlug.BBCMICRO: {"id": 59, "name": "BBC Microcomputer System"},
    UniversalPlatformSlug.BK: {"id": 131, "name": "Elektronika BK"},
    UniversalPlatformSlug.BK_01: {"id": 175, "name": "Apogee BK-01"},
    UniversalPlatformSlug.BROWSER: {"id": 85, "name": "Web Browser"},
    UniversalPlatformSlug.C_PLUS_4: {"id": 121, "name": "Commodore Plus 4"},
    UniversalPlatformSlug.C128: {"id": 118, "name": "Commodore 128"},
    UniversalPlatformSlug.C64: {"id": 14, "name": "Commodore 64"},
    UniversalPlatformSlug.CAMPUTERS_LYNX: {"id": 61, "name": "Camputers Lynx"},
    UniversalPlatformSlug.CASIO_LOOPY: {"id": 114, "name": "Casio Loopy"},
    UniversalPlatformSlug.CASIO_PV_1000: {"id": 115, "name": "Casio PV-1000"},
    UniversalPlatformSlug.COLECOADAM: {"id": 117, "name": "Coleco Adam"},
    UniversalPlatformSlug.COLECOVISION: {"id": 13, "name": "ColecoVision"},
    UniversalPlatformSlug.COLOUR_GENIE: {"id": 73, "name": "EACA EG2000 Colour Genie"},
    UniversalPlatformSlug.COMMODORE_CDTV: {"id": 120, "name": "Commodore CDTV"},
    UniversalPlatformSlug.CPET: {"id": 180, "name": "Commodore PET"},
    UniversalPlatformSlug.CREATIVISION: {"id": 152, "name": "VTech CreatiVision"},
    UniversalPlatformSlug.DC: {"id": 40, "name": "Sega Dreamcast"},
    UniversalPlatformSlug.DOS: {"id": 83, "name": "MS-DOS"},
    UniversalPlatformSlug.DRAGON_32_SLASH_64: {"id": 66, "name": "Dragon 32/64"},
    UniversalPlatformSlug.ENTERPRISE: {"id": 72, "name": "Enterprise"},
    UniversalPlatformSlug.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 132,
        "name": "Epoch Game Pocket Computer",
    },
    UniversalPlatformSlug.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 81,
        "name": "Epoch Super Cassette Vision",
    },
    UniversalPlatformSlug.EXELVISION: {"id": 183, "name": "Exelvision EXL 100"},
    UniversalPlatformSlug.EXIDY_SORCERER: {"id": 184, "name": "Exidy Sorcerer"},
    UniversalPlatformSlug.FAIRCHILD_CHANNEL_F: {
        "id": 58,
        "name": "Fairchild Channel F",
    },
    UniversalPlatformSlug.FAMICOM: {"id": 157, "name": "Nintendo Famicom Disk System"},
    UniversalPlatformSlug.FDS: {"id": 157, "name": "Nintendo Famicom Disk System"},
    UniversalPlatformSlug.FM_7: {"id": 186, "name": "Fujitsu FM-7"},
    UniversalPlatformSlug.FM_TOWNS: {"id": 124, "name": "Fujitsu FM Towns Marty"},
    UniversalPlatformSlug.G_AND_W: {"id": 166, "name": "Nintendo Game & Watch"},
    UniversalPlatformSlug.GAME_DOT_COM: {"id": 63, "name": "Tiger Game.com"},
    UniversalPlatformSlug.GAME_WAVE: {"id": 216, "name": "GameWave"},
    UniversalPlatformSlug.GAMEGEAR: {"id": 41, "name": "Sega Game Gear"},
    UniversalPlatformSlug.GB: {"id": 28, "name": "Nintendo Game Boy"},
    UniversalPlatformSlug.GBA: {"id": 29, "name": "Nintendo Game Boy Advance"},
    UniversalPlatformSlug.GBC: {"id": 30, "name": "Nintendo Game Boy Color"},
    UniversalPlatformSlug.GENESIS: {"id": 42, "name": "Sega Genesis"},
    UniversalPlatformSlug.GP32: {"id": 135, "name": "GamePark GP32"},
    UniversalPlatformSlug.HARTUNG: {"id": 136, "name": "Hartung Game Master"},
    UniversalPlatformSlug.HIKARU: {"id": 208, "name": "Sega Hikaru"},
    UniversalPlatformSlug.HRX: {"id": 187, "name": "Hector HRX"},
    UniversalPlatformSlug.HYPERSCAN: {"id": 171, "name": "Mattel HyperScan"},
    UniversalPlatformSlug.INTELLIVISION: {"id": 15, "name": "Mattel Intellivision"},
    UniversalPlatformSlug.IOS: {"id": 18, "name": "Apple iOS"},
    UniversalPlatformSlug.JAGUAR: {"id": 9, "name": "Atari Jaguar"},
    UniversalPlatformSlug.JUPITER_ACE: {"id": 70, "name": "Jupiter Ace"},
    UniversalPlatformSlug.LINUX: {"id": 218, "name": "Linux"},
    UniversalPlatformSlug.LYNX: {"id": 11, "name": "Atari Lynx"},
    UniversalPlatformSlug.MAC: {"id": 16, "name": "Apple Mac OS"},
    UniversalPlatformSlug.MATTEL_AQUARIUS: {"id": 69, "name": "Mattel Aquarius"},
    UniversalPlatformSlug.MEGA_DUCK_SLASH_COUGAR_BOY: {"id": 127, "name": "Mega Duck"},
    UniversalPlatformSlug.MODEL1: {"id": 104, "name": "Sega Model 1"},
    UniversalPlatformSlug.MODEL2: {"id": 88, "name": "Sega Model 2"},
    UniversalPlatformSlug.MODEL3: {"id": 94, "name": "Sega Model 3"},
    UniversalPlatformSlug.MSX: {"id": 82, "name": "Microsoft MSX"},
    UniversalPlatformSlug.MSX2: {"id": 190, "name": "Microsoft MSX2"},
    UniversalPlatformSlug.MSX2PLUS: {"id": 191, "name": "Microsoft MSX2+"},
    UniversalPlatformSlug.MTX512: {"id": 60, "name": "Memotech MTX512"},
    UniversalPlatformSlug.MUGEN: {"id": 138, "name": "MUGEN"},
    UniversalPlatformSlug.MULTIVISION: {"id": 197, "name": "Othello Multivision"},
    UniversalPlatformSlug.N64: {"id": 25, "name": "Nintendo 64"},
    UniversalPlatformSlug.NDS: {"id": 26, "name": "Nintendo DS"},
    UniversalPlatformSlug.NEO_GEO_CD: {"id": 167, "name": "SNK Neo Geo CD"},
    UniversalPlatformSlug.NEO_GEO_POCKET: {"id": 21, "name": "SNK Neo Geo Pocket"},
    UniversalPlatformSlug.NEO_GEO_POCKET_COLOR: {
        "id": 22,
        "name": "SNK Neo Geo Pocket Color",
    },
    UniversalPlatformSlug.NEOGEOAES: {"id": 23, "name": "SNK Neo Geo AES"},
    UniversalPlatformSlug.NEOGEOMVS: {"id": 210, "name": "SNK Neo Geo MVS"},
    UniversalPlatformSlug.NES: {"id": 27, "name": "Nintendo Entertainment System"},
    UniversalPlatformSlug.NGAGE: {"id": 213, "name": "Nokia N-Gage"},
    UniversalPlatformSlug.NGC: {"id": 31, "name": "Nintendo GameCube"},
    UniversalPlatformSlug.NUON: {"id": 126, "name": "Nuon"},
    UniversalPlatformSlug.ODYSSEY: {"id": 78, "name": "Magnavox Odyssey"},
    UniversalPlatformSlug.ODYSSEY_2_SLASH_VIDEOPAC_G7000: {
        "id": 57,
        "name": "Magnavox Odyssey 2",
    },
    UniversalPlatformSlug.OPENBOR: {"id": 139, "name": "OpenBOR"},
    UniversalPlatformSlug.OUYA: {"id": 35, "name": "Ouya"},
    UniversalPlatformSlug.PC_8800_SERIES: {"id": 192, "name": "NEC PC-8801"},
    UniversalPlatformSlug.PC_9800_SERIES: {"id": 193, "name": "NEC PC-9801"},
    UniversalPlatformSlug.PC_FX: {"id": 161, "name": "NEC PC-FX"},
    UniversalPlatformSlug.PEGASUS: {"id": 174, "name": "Aamber Pegasus"},
    UniversalPlatformSlug.PHILIPS_CD_I: {"id": 37, "name": "Philips CD-i"},
    UniversalPlatformSlug.PHILIPS_VG_5000: {"id": 140, "name": "Philips VG 5000"},
    UniversalPlatformSlug.PICO: {"id": 220, "name": "PICO-8"},
    UniversalPlatformSlug.PINBALL: {"id": 151, "name": "Pinball"},
    UniversalPlatformSlug.POCKETSTATION: {"id": 203, "name": "Sony PocketStation"},
    UniversalPlatformSlug.POKEMON_MINI: {"id": 195, "name": "Nintendo Pokemon Mini"},
    UniversalPlatformSlug.PS2: {"id": 48, "name": "Sony Playstation 2"},
    UniversalPlatformSlug.PS3: {"id": 49, "name": "Sony Playstation 3"},
    UniversalPlatformSlug.PS4: {"id": 50, "name": "Sony Playstation 4"},
    UniversalPlatformSlug.PS5: {"id": 219, "name": "Sony Playstation 5"},
    UniversalPlatformSlug.PSP: {"id": 52, "name": "Sony PSP"},
    UniversalPlatformSlug.PSP_MINIS: {"id": 202, "name": "Sony PSP Minis"},
    UniversalPlatformSlug.PSVITA: {"id": 51, "name": "Sony Playstation Vita"},
    UniversalPlatformSlug.PSX: {"id": 47, "name": "Sony Playstation"},
    UniversalPlatformSlug.RCA_STUDIO_II: {"id": 142, "name": "RCA Studio II"},
    UniversalPlatformSlug.SAM_COUPE: {"id": 71, "name": "SAM Coupé"},
    UniversalPlatformSlug.SATELLAVIEW: {"id": 168, "name": "Nintendo Satellaview"},
    UniversalPlatformSlug.SATURN: {"id": 45, "name": "Sega Saturn"},
    UniversalPlatformSlug.SC3000: {"id": 145, "name": "Sega SC-3000"},
    UniversalPlatformSlug.SCUMMVM: {"id": 143, "name": "ScummVM"},
    UniversalPlatformSlug.SEGA_PICO: {"id": 105, "name": "Sega Pico"},
    UniversalPlatformSlug.SEGA32: {"id": 38, "name": "Sega 32X"},
    UniversalPlatformSlug.SEGACD: {"id": 39, "name": "Sega CD"},
    UniversalPlatformSlug.SEGACD32: {"id": 173, "name": "Sega CD 32X"},
    UniversalPlatformSlug.SERIES_X_S: {"id": 222, "name": "Microsoft Xbox Series X/S"},
    UniversalPlatformSlug.SFAM: {"id": 53, "name": "Super Famicom"},
    UniversalPlatformSlug.SG1000: {"id": 80, "name": "Sega SG-1000"},
    UniversalPlatformSlug.SHARP_MZ_80B20002500: {"id": 205, "name": "Sharp MZ-2500"},
    UniversalPlatformSlug.SHARP_X68000: {"id": 128, "name": "Sharp X68000"},
    UniversalPlatformSlug.SMS: {"id": 43, "name": "Sega Master System"},
    UniversalPlatformSlug.SNES: {
        "id": 53,
        "name": "Super Nintendo Entertainment System",
    },
    UniversalPlatformSlug.SOCRATES: {"id": 198, "name": "VTech Socrates"},
    UniversalPlatformSlug.SORD_M5: {"id": 148, "name": "Sord M5"},
    UniversalPlatformSlug.SPECTRAVIDEO: {"id": 201, "name": "Spectravideo"},
    UniversalPlatformSlug.STV: {"id": 146, "name": "Sega ST-V"},
    UniversalPlatformSlug.SUPER_VISION_8000: {
        "id": 223,
        "name": "Bandai Super Vision 8000",
    },
    UniversalPlatformSlug.SUPERGRAFX: {"id": 162, "name": "PC Engine SuperGrafx"},
    UniversalPlatformSlug.SWITCH: {"id": 211, "name": "Nintendo Switch"},
    UniversalPlatformSlug.SWITCH_2: {"id": 224, "name": "Nintendo Switch 2"},
    UniversalPlatformSlug.SYSTEM_32: {"id": 93, "name": "Namco System 22"},
    UniversalPlatformSlug.SYSTEM16: {"id": 97, "name": "Sega System 16"},
    UniversalPlatformSlug.SYSTEM32: {"id": 96, "name": "Sega System 32"},
    UniversalPlatformSlug.TG16: {"id": 54, "name": "NEC TurboGrafx-16"},
    UniversalPlatformSlug.TI_994A: {"id": 149, "name": "Texas Instruments TI 99/4A"},
    UniversalPlatformSlug.TOMY_TUTOR: {"id": 200, "name": "Tomy Tutor"},
    UniversalPlatformSlug.TRS_80: {"id": 129, "name": "Tandy TRS-80"},
    UniversalPlatformSlug.TRS_80_COLOR_COMPUTER: {
        "id": 164,
        "name": "TRS-80 Color Computer",
    },
    UniversalPlatformSlug.TURBOGRAFX_CD: {"id": 163, "name": "NEC TurboGrafx-CD"},
    UniversalPlatformSlug.TYPE_X: {"id": 169, "name": "Taito Type X"},
    UniversalPlatformSlug.VC_4000: {"id": 137, "name": "Interton VC 4000"},
    UniversalPlatformSlug.VECTREX: {"id": 125, "name": "GCE Vectrex"},
    UniversalPlatformSlug.VIC_20: {"id": 122, "name": "Commodore VIC-20"},
    UniversalPlatformSlug.VIDEOPAC_G7400: {"id": 141, "name": "Philips Videopac+"},
    UniversalPlatformSlug.VIRTUALBOY: {"id": 32, "name": "Nintendo Virtual Boy"},
    UniversalPlatformSlug.VMU: {"id": 144, "name": "Sega Dreamcast VMU"},
    UniversalPlatformSlug.VSMILE: {"id": 221, "name": "VTech V.Smile"},
    UniversalPlatformSlug.SUPERVISION: {"id": 153, "name": "Watara Supervision"},
    UniversalPlatformSlug.WII: {"id": 33, "name": "Nintendo Wii"},
    UniversalPlatformSlug.WIIU: {"id": 34, "name": "Nintendo Wii U"},
    UniversalPlatformSlug.WIN: {"id": 84, "name": "Windows"},
    UniversalPlatformSlug.WIN3X: {"id": 212, "name": "Windows 3.X"},
    UniversalPlatformSlug.WONDERSWAN: {"id": 55, "name": "WonderSwan"},
    UniversalPlatformSlug.WONDERSWAN_COLOR: {"id": 56, "name": "WonderSwan Color"},
    UniversalPlatformSlug.X1: {"id": 204, "name": "Sharp X1"},
    UniversalPlatformSlug.XAVIXPORT: {"id": 170, "name": "XaviXPORT"},
    UniversalPlatformSlug.XBOX: {"id": 18, "name": "Microsoft Xbox"},
    UniversalPlatformSlug.XBOX360: {"id": 19, "name": "Microsoft Xbox 360"},
    UniversalPlatformSlug.XBOXONE: {"id": 20, "name": "Microsoft Xbox One"},
    UniversalPlatformSlug.ZINC: {"id": 155, "name": "ZiNc"},
    UniversalPlatformSlug.ZOD: {"id": 75, "name": "Tapwave Zodiac"},
    UniversalPlatformSlug.ZX81: {"id": 147, "name": "Sinclair ZX-81"},
    UniversalPlatformSlug.ZXS: {"id": 46, "name": "Sinclair ZX Spectrum"},
}


# Reverse lookup
LAUNCHBOX_PLATFORM_NAME_TO_SLUG = {
    v["id"]: k for k, v in LAUNCHBOX_PLATFORM_LIST.items()
}
