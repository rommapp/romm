import base64
import re
from datetime import datetime
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import pydash
from unidecode import unidecode as uc

from adapters.services.screenscraper import ScreenScraperService
from adapters.services.screenscraper_types import SSGame, SSGameDate
from config import SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
from config.config_manager import MetadataMediaType
from config.config_manager import config_manager as cm
from handler.filesystem import fs_resource_handler
from logger.logger import log
from models.rom import Rom, RomFile

from .base_handler import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    BaseRom,
    MetadataHandler,
)
from .base_handler import UniversalPlatformSlug as UPS

SS_DEV_ID: Final = base64.b64decode("enVyZGkxNQ==").decode()
SS_DEV_PASSWORD: Final = base64.b64decode("eFRKd29PRmpPUUc=").decode()


def get_preferred_regions() -> list[str]:
    """Get preferred regions from config"""
    config = cm.get_config()
    return list(
        dict.fromkeys(config.SCAN_REGION_PRIORITY + ["us", "wor", "ss", "eu", "jp"])
    ) + ["unk"]


def get_preferred_languages() -> list[str]:
    """Get preferred languages from config.

    Returns language priority list with default fallbacks.
    """
    config = cm.get_config()
    return list(dict.fromkeys(config.SCAN_LANGUAGE_PRIORITY + ["en", "fr"]))


def get_preferred_media_types() -> list[MetadataMediaType]:
    """Get preferred media types from config"""
    config = cm.get_config()
    return [MetadataMediaType(media) for media in config.SCAN_MEDIA]


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

# Regex to detect ScreenScraper ID tags in filenames like (ssfr-12345)
SS_TAG_REGEX = re.compile(r"\(ssfr-(\d+)\)", re.IGNORECASE)

ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG = {
    UPS.DC: ["cue", "chd", "gdi", "cdi"],
    UPS.SEGACD: ["cue", "chd", "bin"],
    UPS.NGC: ["rvz", "iso", "gcz"],
}


class SSPlatform(TypedDict):
    slug: str
    ss_id: int | None
    name: NotRequired[str]


class SSAgeRating(TypedDict):
    rating: str
    category: str
    rating_cover_url: str


class SSMetadataMedia(TypedDict):
    bezel_url: str | None  # bezel-16-9
    box2d_url: str | None  # box-2D
    box2d_side_url: str | None  # box-2D-side
    box2d_back_url: str | None  # box-2D-back
    box3d_url: str | None  # box-3D
    fanart_url: str | None  # fanart
    fullbox_url: str | None  # box-texture
    logo_url: str | None  # wheel-hd or wheel
    manual_url: str | None  # manual
    marquee_url: str | None  # screenmarquee
    miximage_url: str | None  # mixrbv1 | mixrbv2
    physical_url: str | None  # support-2D
    screenshot_url: str | None  # ss
    steamgrid_url: str | None  # steamgrid
    title_screen_url: str | None  # sstitle
    video_url: str | None  # video
    video_normalized_url: str | None  # video-normalized

    # Resources stored in filesystem
    bezel_path: str | None
    box2d_back_path: str | None
    box3d_path: str | None
    fanart_path: str | None
    miximage_path: str | None
    physical_path: str | None
    marquee_path: str | None
    logo_path: str | None
    video_path: str | None


class SSMetadata(SSMetadataMedia):
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


def extract_media_from_ss_game(rom: Rom, game: SSGame) -> SSMetadataMedia:
    preferred_media_types = get_preferred_media_types()

    ss_media = SSMetadataMedia(
        bezel_url=None,
        box2d_url=None,
        box2d_back_url=None,
        box2d_side_url=None,
        box3d_url=None,
        fanart_url=None,
        fullbox_url=None,
        logo_url=None,
        manual_url=None,
        marquee_url=None,
        miximage_url=None,
        physical_url=None,
        screenshot_url=None,
        steamgrid_url=None,
        title_screen_url=None,
        video_url=None,
        video_normalized_url=None,
        bezel_path=None,
        box2d_back_path=None,
        box3d_path=None,
        fanart_path=None,
        miximage_path=None,
        physical_path=None,
        marquee_path=None,
        logo_path=None,
        video_path=None,
    )

    for region in get_preferred_regions():
        for media in game.get("medias", []):
            if media.get("region", "unk") != region or media.get("parent") != "jeu":
                continue

            if media.get("type") == "box-2D-back" and not ss_media["box2d_back_url"]:
                ss_media["box2d_back_url"] = media["url"]
                if MetadataMediaType.BOX2D_BACK in preferred_media_types:
                    ss_media["box2d_back_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BOX2D_BACK)}/box2d_back.png"
                    )
            elif media.get("type") == "bezel-16-9" and not ss_media["bezel_url"]:
                ss_media["bezel_url"] = media["url"]
                if MetadataMediaType.BEZEL in preferred_media_types:
                    ss_media["bezel_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BEZEL)}/bezel.png"
                    )
            elif media.get("type") == "box-2D" and not ss_media["box2d_url"]:
                ss_media["box2d_url"] = media["url"]
            elif media.get("type") == "fanart" and not ss_media["fanart_url"]:
                ss_media["fanart_url"] = media["url"]
                if MetadataMediaType.FANART in preferred_media_types:
                    ss_media["fanart_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.FANART)}/fanart.png"
                    )
            elif media.get("type") == "box-texture" and not ss_media["fullbox_url"]:
                ss_media["fullbox_url"] = media["url"]
            elif media.get("type") == "wheel-hd" and not ss_media["logo_url"]:
                ss_media["logo_url"] = media["url"]

                if MetadataMediaType.LOGO in preferred_media_types:
                    ss_media["logo_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.LOGO)}/logo.png"
                    )
            elif media.get("type") == "wheel" and not ss_media["logo_url"]:
                ss_media["logo_url"] = media["url"]
                if MetadataMediaType.LOGO in preferred_media_types:
                    ss_media["logo_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.LOGO)}/logo.png"
                    )
            elif media.get("type") == "manuel" and not ss_media["manual_url"]:
                ss_media["manual_url"] = media["url"]
            elif media.get("type") == "screenmarquee" and not ss_media["marquee_url"]:
                ss_media["marquee_url"] = media["url"]
                if MetadataMediaType.MARQUEE in preferred_media_types:
                    ss_media["marquee_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MARQUEE)}/marquee.png"
                    )
            elif (
                media.get("type") == "miximage1"
                or media.get("type") == "miximage2"
                or media.get("type") == "mixrbv1"
                or media.get("type") == "mixrbv2"
            ) and not ss_media["miximage_url"]:
                ss_media["miximage_url"] = media["url"]
                if MetadataMediaType.MIXIMAGE in preferred_media_types:
                    ss_media["miximage_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MIXIMAGE)}/miximage.png"
                    )
            elif media.get("type") == "support-2D" and not ss_media["physical_url"]:
                ss_media["physical_url"] = media["url"]
                if MetadataMediaType.PHYSICAL in preferred_media_types:
                    ss_media["physical_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.PHYSICAL)}/physical.png"
                    )
            elif media.get("type") == "ss" and not ss_media["screenshot_url"]:
                ss_media["screenshot_url"] = media["url"]
            elif media.get("type") == "box-2D-side" and not ss_media["box2d_side_url"]:
                ss_media["box2d_side_url"] = media["url"]
            elif media.get("type") == "steamgrid" and not ss_media["steamgrid_url"]:
                ss_media["steamgrid_url"] = media["url"]
            elif media.get("type") == "box-3D" and not ss_media["box3d_url"]:
                ss_media["box3d_url"] = media["url"]
                if MetadataMediaType.BOX3D in preferred_media_types:
                    ss_media["box3d_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BOX3D)}/box3d.png"
                    )
            elif media.get("type") == "sstitle" and not ss_media["title_screen_url"]:
                ss_media["title_screen_url"] = media["url"]
            elif media.get("type") == "video" and not ss_media["video_url"]:
                ss_media["video_url"] = media["url"]
                if MetadataMediaType.VIDEO in preferred_media_types:
                    ss_media["video_path"] = (
                        f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.VIDEO)}/video.mp4"
                    )
            elif (
                media.get("type") == "video-normalized"
                and not ss_media["video_normalized_url"]
            ):
                ss_media["video_normalized_url"] = media["url"]

    return ss_media


def extract_metadata_from_ss_rom(rom: Rom, game: SSGame) -> SSMetadata:
    preferred_languages = get_preferred_languages()

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

    def _get_genres(game: SSGame) -> list[str]:
        return [
            genre_name["text"]
            for genre in game.get("genres", [])
            for genre_name in genre.get("noms", [])
            if genre_name.get("langue") == "en"
        ]

    def _get_franchises(game: SSGame) -> list[str]:
        for lang in preferred_languages:
            franchises = [
                franchise_name["text"]
                for franchise in game.get("familles", [])
                for franchise_name in franchise.get("noms", [])
                if franchise_name.get("langue") == lang
            ]
            if franchises:
                return franchises
        return []

    def _get_game_modes(game: SSGame) -> list[str]:
        for lang in preferred_languages:
            modes = [
                mode_name["text"]
                for mode in game.get("modes", [])
                for mode_name in mode.get("noms", [])
                if mode_name.get("langue") == lang
            ]
            if modes:
                return modes
        return []

    return SSMetadata(
        {
            "ss_score": _normalize_score(game.get("note", {}).get("text", "")),
            "alternative_names": [name["text"] for name in game.get("noms", [])],
            "companies": pydash.compact(
                [
                    game.get("editeur", {}).get("text"),
                    game.get("developpeur", {}).get("text"),
                ]
            ),
            "genres": _get_genres(game),
            "first_release_date": _get_lowest_date(game.get("dates", [])),
            "franchises": _get_franchises(game),
            "game_modes": _get_game_modes(game),
            **extract_media_from_ss_game(rom, game),
        }
    )


def build_ss_game(rom: Rom, game: SSGame) -> SSRom:
    ss_metadata = extract_metadata_from_ss_rom(rom, game)
    preferred_media_types = get_preferred_media_types()

    res_name = ""
    for region in get_preferred_regions():
        res_name = next(
            (
                name["text"]
                for name in game.get("noms", [])
                if name.get("region", "unk") == region
            ),
            "",
        )
        if res_name:
            break

    res_summary = ""
    preferred_languages = get_preferred_languages()
    used_lang = None
    for lang in preferred_languages:
        res_summary = next(
            (
                synopsis["text"]
                for synopsis in game.get("synopsis", [])
                if synopsis.get("langue") == lang
            ),
            "",
        )
        if res_summary:
            used_lang = lang
            break

    # Log warning if we had to fall back from the preferred locale
    if preferred_languages and used_lang and used_lang != preferred_languages[0]:
        log.warning(
            f"ScreenScraper locale '{preferred_languages[0]}' not found for '{res_name}', using '{used_lang}'"
        )

    url_cover = ss_metadata["box2d_url"]
    url_manual = (
        ss_metadata["manual_url"]
        if MetadataMediaType.MANUAL in preferred_media_types
        else None
    )
    url_screenshots = pydash.compact(
        [
            (
                ss_metadata["screenshot_url"]
                if MetadataMediaType.SCREENSHOT in preferred_media_types
                else None
            ),
            (
                ss_metadata["title_screen_url"]
                if MetadataMediaType.TITLE_SCREEN in preferred_media_types
                else None
            ),
            (
                ss_metadata["fanart_url"]
                if MetadataMediaType.FANART in preferred_media_types
                else None
            ),
        ]
    )

    ss_id = int(game["id"]) if game.get("id") is not None else None
    game_rom: SSRom = {
        "ss_id": ss_id,
        "name": res_name.replace(" : ", ": "),  # Normalize colons
        "summary": res_summary,
        "url_cover": str(url_cover) if url_cover else "",
        "url_manual": str(url_manual) if url_manual else "",
        "url_screenshots": url_screenshots,
        "ss_metadata": ss_metadata,
    }

    return SSRom({k: v for k, v in game_rom.items() if v})  # type: ignore[misc]


class SSHandler(MetadataHandler):
    def __init__(self) -> None:
        self.ss_service = ScreenScraperService()

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(SCREENSCRAPER_USER and SCREENSCRAPER_PASSWORD)

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self.ss_service.get_infra_info()
        except Exception as e:
            log.error("Error checking ScreenScraper API: %s", e)
            return False

        return bool(response.get("response", {}))

    @staticmethod
    def extract_ss_id_from_filename(fs_name: str) -> int | None:
        """Extract ScreenScraper ID from filename tag like (ss-12345)."""
        match = SS_TAG_REGEX.search(fs_name)
        if match:
            return int(match.group(1))
        return None

    async def _search_rom(
        self, search_term: str, platform_ss_id: int, split_game_name: bool = False
    ) -> SSGame | None:
        if not platform_ss_id:
            return None

        roms = await self.ss_service.search_games(
            term=quote(uc(search_term), safe="/ "),
            system_id=platform_ss_id,
        )

        games_by_name: dict[str, SSGame] = {}
        for rom in roms:
            for name in rom.get("noms", []):
                if name["text"] not in games_by_name or int(rom["id"]) < int(
                    games_by_name[name["text"]]["id"]
                ):
                    games_by_name[name["text"]] = rom

        best_match, best_score = self.find_best_match(
            search_term,
            list(games_by_name.keys()),
            split_game_name=split_game_name,
        )
        if best_match:
            log.debug(
                f"Found match for '{search_term}' -> '{best_match}' (score: {best_score:.3f})"
            )
            return games_by_name[best_match]

        return None

    def get_platform(self, slug: str) -> SSPlatform:
        if slug not in SCREENSAVER_PLATFORM_LIST:
            return SSPlatform(ss_id=None, slug=slug)

        platform = SCREENSAVER_PLATFORM_LIST[UPS(slug)]

        return SSPlatform(
            ss_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def lookup_rom(
        self, rom: Rom, platform_ss_id: int, files: list[RomFile]
    ) -> SSRom:
        if not self.is_enabled():
            return SSRom(ss_id=None)

        if not platform_ss_id:
            return SSRom(ss_id=None)

        filtered_files = [
            file
            for file in files
            if file.file_size_bytes > 0
            and file.is_top_level
            and (
                UPS(rom.platform_slug)
                not in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG
                or file.file_extension
                in ACCEPTABLE_FILE_EXTENSIONS_BY_PLATFORM_SLUG[UPS(rom.platform_slug)]
            )
        ]

        # Select the largest file by size, as it is most likely to be the main ROM file.
        # This increases the accuracy of metadata lookups, since the largest file is
        # expected to have the correct and complete hash values for external services.
        first_file = max(filtered_files, key=lambda f: f.file_size_bytes, default=None)
        if first_file is None:
            return SSRom(ss_id=None)

        md5_hash = first_file.md5_hash
        sha1_hash = first_file.sha1_hash
        crc_hash = first_file.crc_hash
        fs_size_bytes = first_file.file_size_bytes

        if not (md5_hash or sha1_hash or crc_hash):
            log.info(
                "No hashes provided for ScreenScraper lookup. "
                "At least one of md5_hash, sha1_hash, or crc_hash is required."
            )
            return SSRom(ss_id=None)

        res = await self.ss_service.get_game_info(
            system_id=platform_ss_id,
            md5=md5_hash,
            sha1=sha1_hash,
            crc=crc_hash,
            rom_size_bytes=fs_size_bytes,
        )
        if not res:
            return SSRom(ss_id=None)

        return build_ss_game(rom, res)

    async def get_rom(self, rom: Rom, file_name: str, platform_ss_id: int) -> SSRom:
        from handler.filesystem import fs_rom_handler

        if not self.is_enabled():
            return SSRom(ss_id=None)

        if not platform_ss_id:
            return SSRom(ss_id=None)

        # Check for ScreenScraper ID tag in filename first
        ss_id_from_tag = self.extract_ss_id_from_filename(file_name)
        if ss_id_from_tag:
            log.debug(f"Found ScreenScraper ID tag in filename: {ss_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(rom, ss_id_from_tag)
            if rom_by_id["ss_id"]:
                log.debug(
                    f"Successfully matched ROM by ScreenScraper ID tag: {file_name} -> {ss_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"ScreenScraper ID {ss_id_from_tag} from filename tag not found in ScreenScraper"
                )

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
        res = await self._search_rom(
            self.SEARCH_TERM_NORMALIZER.sub(" : ", normalized_search_term),
            platform_ss_id,
        )

        # SS API doesn't handle some special characters well
        if not res and " : " in search_term:
            terms = re.split(self.SEARCH_TERM_SPLIT_PATTERN, search_term)
            res = await self._search_rom(
                terms[-1], platform_ss_id, split_game_name=True
            )

        if not res or not res.get("id"):
            return fallback_rom

        return build_ss_game(rom, res)

    async def get_rom_by_id(self, rom: Rom, ss_id: int) -> SSRom:
        if not self.is_enabled():
            return SSRom(ss_id=None)

        res = await self.ss_service.get_game_info(game_id=ss_id)
        if not res:
            return SSRom(ss_id=None)

        return build_ss_game(rom, res)

    async def get_matched_rom_by_id(self, rom: Rom, ss_id: int) -> SSRom | None:
        if not self.is_enabled():
            return None

        game_rom = await self.get_rom_by_id(rom, ss_id)
        return game_rom if game_rom.get("ss_id", "") else None

    async def get_matched_roms_by_name(
        self, rom: Rom, search_term: str, platform_ss_id: int | None
    ) -> list[SSRom]:
        if not self.is_enabled():
            return []

        if not platform_ss_id:
            return []

        matched_games = await self.ss_service.search_games(
            term=quote(uc(search_term), safe="/ "),
            system_id=platform_ss_id,
        )

        def _is_ss_region(game: SSGame) -> bool:
            return any(name.get("region") == "ss" for name in game.get("noms", []))

        return [
            build_ss_game(rom, game)
            for game in matched_games
            if _is_ss_region(game) and game.get("id")
        ]


class SlugToSSId(TypedDict):
    id: int
    name: str


SCREENSAVER_PLATFORM_LIST: dict[UPS, SlugToSSId] = {
    UPS._3DO: {"id": 29, "name": "3DO"},
    UPS.AMIGA: {"id": 64, "name": "Amiga"},
    UPS.AMIGA_CD: {"id": 134, "name": "Amiga CD"},
    UPS.AMIGA_CD32: {"id": 130, "name": "Amiga CD32"},
    UPS.ACPC: {"id": 65, "name": "CPC"},
    UPS.ADVENTURE_VISION: {
        "id": 78,
        "name": "Entex Adventure Vision",
    },
    UPS.AMSTRAD_GX4000: {"id": 87, "name": "Amstrad GX4000"},
    UPS.ANDROID: {"id": 63, "name": "Android"},
    UPS.APPLEII: {"id": 86, "name": "Apple II"},
    UPS.APPLE_IIGS: {"id": 51, "name": "Apple IIGS"},
    UPS.ARCADIA_2001: {"id": 94, "name": "Arcadia 2001"},
    UPS.ARDUBOY: {"id": 263, "name": "Arduboy"},
    UPS.ATARI2600: {"id": 26, "name": "Atari 2600"},
    UPS.ATARI5200: {"id": 40, "name": "Atari 5200"},
    UPS.ATARI7800: {"id": 41, "name": "Atari 7800"},
    UPS.ATARI8BIT: {"id": 43, "name": "Atari 8bit"},
    UPS.ATARI_ST: {"id": 42, "name": "Atari ST"},
    UPS.ATOM: {"id": 36, "name": "Atom"},
    UPS.BBCMICRO: {"id": 37, "name": "BBC Micro"},
    UPS.ASTROCADE: {"id": 44, "name": "Astrocade"},
    UPS.PHILIPS_CD_I: {"id": 133, "name": "CD-i"},
    UPS.COMMODORE_CDTV: {"id": 129, "name": "Amiga CDTV"},
    UPS.CAMPUTERS_LYNX: {"id": 88, "name": "Camputers Lynx"},
    UPS.CASIO_LOOPY: {"id": 98, "name": "Loopy"},
    UPS.CASIO_PV_1000: {"id": 74, "name": "PV-1000"},
    UPS.FAIRCHILD_CHANNEL_F: {"id": 80, "name": "Channel F"},
    UPS.COLECOADAM: {"id": 89, "name": "Coleco Adam"},
    UPS.COLECOVISION: {"id": 48, "name": "Colecovision"},
    UPS.COLOUR_GENIE: {"id": 92, "name": "EG2000 Colour Genie"},
    UPS.C128: {"id": 66, "name": "Commodore 64"},
    UPS.C_PLUS_4: {"id": 99, "name": "Plus/4"},
    UPS.C16: {"id": 99, "name": "Plus/4"},
    UPS.C64: {"id": 66, "name": "Commodore 64"},
    UPS.CPET: {"id": 240, "name": "PET"},
    UPS.CREATIVISION: {"id": 241, "name": "CreatiVision"},
    UPS.DOS: {"id": 135, "name": "PC Dos"},
    UPS.DRAGON_32_SLASH_64: {"id": 91, "name": "Dragon 32/64"},
    UPS.DC: {"id": 23, "name": "Dreamcast"},
    UPS.ACORN_ELECTRON: {"id": 85, "name": "Electron"},
    UPS.EPOCH_GAME_POCKET_COMPUTER: {
        "id": 95,
        "name": "Game Pocket Computer",
    },
    UPS.EPOCH_SUPER_CASSETTE_VISION: {
        "id": 67,
        "name": "Super Cassette Vision",
    },
    UPS.EXELVISION: {"id": 96, "name": "EXL 100"},
    UPS.EXIDY_SORCERER: {"id": 165, "name": "Exidy"},
    UPS.FM_TOWNS: {"id": 253, "name": "FM Towns"},
    UPS.FM_7: {"id": 97, "name": "FM-7"},
    UPS.G_AND_W: {"id": 52, "name": "Game & Watch"},
    UPS.GP32: {"id": 101, "name": "GP32"},
    UPS.GB: {"id": 9, "name": "Game Boy"},
    UPS.GBA: {"id": 12, "name": "Game Boy Advance"},
    UPS.GBC: {"id": 10, "name": "Game Boy Color"},
    UPS.GAMEGEAR: {"id": 21, "name": "Game Gear"},
    UPS.GAME_DOT_COM: {"id": 121, "name": "Game.com"},
    UPS.NGC: {"id": 13, "name": "GameCube"},
    UPS.GENESIS: {"id": 1, "name": "Megadrive"},
    UPS.HARTUNG: {"id": 103, "name": "Game Master"},
    UPS.INTELLIVISION: {"id": 115, "name": "Intellivision"},
    UPS.JAGUAR: {"id": 27, "name": "Jaguar"},
    UPS.JUPITER_ACE: {"id": 126, "name": "Jupiter Ace"},
    UPS.LINUX: {"id": 145, "name": "Linux"},
    UPS.LYNX: {"id": 28, "name": "Lynx"},
    UPS.MSX: {"id": 113, "name": "MSX"},
    UPS.MSX_TURBO: {"id": 118, "name": "MSX Turbo R"},
    UPS.MAC: {"id": 146, "name": "Mac OS"},
    UPS.NGAGE: {"id": 30, "name": "N-Gage"},
    UPS.NES: {"id": 3, "name": "NES"},
    UPS.FAMICOM: {"id": 3, "name": "Famicom"},
    UPS.FDS: {"id": 106, "name": "Famicom"},
    UPS.NEOGEOAES: {"id": 142, "name": "Neo-Geo"},
    UPS.NEOGEOMVS: {"id": 68, "name": "Neo-Geo MVS"},
    UPS.NEO_GEO_CD: {"id": 70, "name": "Neo-Geo CD"},
    UPS.NEO_GEO_POCKET: {"id": 25, "name": "Neo-Geo Pocket"},
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 82,
        "name": "Neo-Geo Pocket Color",
    },
    UPS.N3DS: {"id": 17, "name": "Nintendo 3DS"},
    UPS.N64: {"id": 14, "name": "Nintendo 64"},
    UPS.N64DD: {"id": 122, "name": "Nintendo 64DD"},
    UPS.NDS: {"id": 15, "name": "Nintendo DS"},
    UPS.NINTENDO_DSI: {"id": 15, "name": "Nintendo DS"},
    UPS.SWITCH: {"id": 225, "name": "Switch"},
    UPS.ODYSSEY_2: {"id": 104, "name": "Videopac G7000"},
    UPS.ORIC: {"id": 131, "name": "Oric 1 / Atmos"},
    UPS.PC_8800_SERIES: {"id": 221, "name": "NEC PC-8801"},
    UPS.PC_9800_SERIES: {"id": 208, "name": "NEC PC-9801"},
    UPS.PC_FX: {"id": 72, "name": "PC-FX"},
    UPS.PICO: {"id": 234, "name": "Pico-8"},
    UPS.PSVITA: {"id": 62, "name": "PS Vita"},
    UPS.PSP: {"id": 61, "name": "PSP"},
    UPS.PALM_OS: {"id": 219, "name": "Palm OS"},
    UPS.PHILIPS_VG_5000: {"id": 261, "name": "Philips VG 5000"},
    UPS.PSX: {"id": 57, "name": "Playstation"},
    UPS.PS2: {"id": 58, "name": "Playstation 2"},
    UPS.PS3: {"id": 59, "name": "Playstation 3"},
    UPS.PS4: {"id": 60, "name": "Playstation 4"},
    UPS.PS5: {"id": 284, "name": "Playstation 5"},
    UPS.POKEMON_MINI: {"id": 211, "name": "Pokémon mini"},
    UPS.SAM_COUPE: {"id": 213, "name": "MGT SAM Coupé"},
    UPS.SEGA32: {"id": 19, "name": "Megadrive 32X"},
    UPS.SEGACD: {"id": 20, "name": "Mega-CD"},
    UPS.SMS: {"id": 2, "name": "Master System"},
    UPS.SEGA_PICO: {"id": 250, "name": "Sega Pico"},
    UPS.SATURN: {"id": 22, "name": "Saturn"},
    UPS.SG1000: {"id": 109, "name": "SG-1000"},
    UPS.SNES: {"id": 4, "name": "Super Nintendo"},
    UPS.SFAM: {"id": 4, "name": "Super Famicom"},
    UPS.X1: {"id": 220, "name": "Sharp X1"},
    UPS.SHARP_X68000: {"id": 79, "name": "Sharp X68000"},
    UPS.SPECTRAVIDEO: {"id": 218, "name": "Spectravideo"},
    UPS.SUFAMI_TURBO: {"id": 108, "name": "Sufami Turbo"},
    UPS.SUPER_ACAN: {"id": 100, "name": "Super A'can"},
    UPS.SUPERGRAFX: {"id": 105, "name": "PC Engine SuperGrafx"},
    UPS.SUPERVISION: {"id": 207, "name": "Watara Supervision"},
    UPS.TI_99: {"id": 205, "name": "TI-99/4A"},
    UPS.TRS_80_COLOR_COMPUTER: {
        "id": 144,
        "name": "TRS-80 Color Computer",
    },
    UPS.TAITO_X_55: {"id": 112, "name": "Type X"},
    UPS.THOMSON_MO5: {"id": 141, "name": "Thomson MO/TO"},
    UPS.THOMSON_TO: {"id": 141, "name": "Thomson MO/TO"},
    UPS.TURBOGRAFX_CD: {"id": 114, "name": "PC Engine CD-Rom"},
    UPS.TG16: {"id": 31, "name": "PC Engine"},
    UPS.UZEBOX: {"id": 216, "name": "UzeBox"},
    UPS.VSMILE: {"id": 120, "name": "V.Smile"},
    UPS.VIC_20: {"id": 73, "name": "Vic-20"},
    UPS.VECTREX: {"id": 102, "name": "Vectrex"},
    UPS.VIDEOPAC_G7400: {"id": 104, "name": "Videopac G7000"},
    UPS.VIRTUALBOY: {"id": 11, "name": "Virtual Boy"},
    UPS.WII: {"id": 16, "name": "Wii"},
    UPS.WIIU: {"id": 18, "name": "Wii U"},
    UPS.WIN: {"id": 138, "name": "PC Windows"},
    UPS.WIN3X: {"id": 136, "name": "PC Win3.xx"},
    UPS.WONDERSWAN: {"id": 45, "name": "WonderSwan"},
    UPS.WONDERSWAN_COLOR: {"id": 46, "name": "WonderSwan Color"},
    UPS.XBOX: {"id": 32, "name": "Xbox"},
    UPS.XBOX360: {"id": 33, "name": "Xbox 360"},
    UPS.XBOXONE: {"id": 34, "name": "Xbox One"},
    UPS.Z_MACHINE: {"id": 215, "name": "Z-Machine"},
    UPS.ZXS: {"id": 76, "name": "ZX Spectrum"},
    UPS.ZX81: {"id": 77, "name": "ZX81"},
}

# Reverse lookup
SS_ID_TO_SLUG = {v["id"]: k for k, v in SCREENSAVER_PLATFORM_LIST.items()}
