import glob
import os
import uuid
from pathlib import Path
from typing import Final, NotRequired, TypedDict
from xml.etree.ElementTree import Element  # trunk-ignore(bandit/B405)

import pydash
from defusedxml import ElementTree as ET

from config.config_manager import MetadataMediaType
from config.config_manager import config_manager as cm
from handler.filesystem import fs_platform_handler, fs_resource_handler
from logger.logger import log
from models.platform import Platform
from models.rom import Rom

from .base_handler import BaseRom, MetadataHandler

# https://github.com/Aloshi/EmulationStation/blob/master/GAMELISTS.md#reference


def get_preferred_media_types() -> list[MetadataMediaType]:
    """Get preferred media types from config"""
    config = cm.get_config()
    return [MetadataMediaType(media) for media in config.SCAN_MEDIA]


class GamelistMetadataMedia(TypedDict):
    box2d_url: str | None
    box2d_back_url: str | None
    box3d_url: str | None
    fanart_url: str | None
    image_url: str | None
    manual_url: str | None
    marquee_url: str | None
    miximage_url: str | None
    physical_url: str | None
    screenshot_url: str | None
    thumbnail_url: str | None
    title_screen_url: str | None
    video_url: str | None


class GamelistMetadata(GamelistMetadataMedia):
    rating: float | None
    first_release_date: str | None
    companies: list[str] | None
    franchises: list[str] | None
    genres: list[str] | None
    player_count: str | None
    md5_hash: str | None
    box3d_path: str | None
    miximage_path: str | None
    physical_path: str | None
    marquee_path: str | None
    video_path: str | None


class GamelistRom(BaseRom):
    gamelist_id: str | None
    regions: NotRequired[list[str]]
    languages: NotRequired[list[str]]
    gamelist_metadata: NotRequired[GamelistMetadata]


ESDE_MEDIA_MAP: Final = {
    "image_url": "images",
    "box2d_url": "covers",
    "box2d_back_url": "backcovers",
    "box3d_url": "3dboxes",
    "fanart_url": "fanart",
    "manual_url": "manuals",
    "marquee_url": "marquees",
    "miximage_url": "miximages",
    "physical_url": "physicalmedia",
    "screenshot_url": "screenshots",
    "title_screen_url": "titlescreens",
    "thumbnail_url": "thumbnails",
    "video_url": "videos",
}

XML_TAG_MAP: Final = {
    "image_url": "image",
    "box2d_url": "cover",
    "box2d_back_url": "backcover",
    "box3d_url": "box3d",
    "fanart_url": "fanart",
    "manual_url": "manual",
    "marquee_url": "marquee",
    "miximage_url": "miximage",
    "physical_url": "physicalmedia",
    "screenshot_url": "screenshot",
    "title_screen_url": "title_screen",
    "thumbnail_url": "thumbnail",
    "video_url": "video",
}


def _make_file_uri(platform_dir: str, raw_text: str) -> str:
    cleaned_text = raw_text.replace("./", "")
    validated_path = fs_platform_handler.validate_path(
        os.path.join(platform_dir, cleaned_text)
    )
    return f"file://{str(validated_path)}"


def extract_media_from_gamelist_rom(
    game: Element, platform: Platform
) -> GamelistMetadataMedia:
    platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)

    gamelist_media = GamelistMetadataMedia(
        box2d_url=None,
        box2d_back_url=None,
        box3d_url=None,
        fanart_url=None,
        image_url=None,
        manual_url=None,
        marquee_url=None,
        miximage_url=None,
        physical_url=None,
        screenshot_url=None,
        title_screen_url=None,
        thumbnail_url=None,
        video_url=None,
    )

    # Check explicit XML elements defined in gamelist.xml
    for media_key, xml_tag in XML_TAG_MAP.items():
        elem = game.find(xml_tag)
        if elem is not None and elem.text:
            # trunk-ignore(mypy/literal-required)
            gamelist_media[media_key] = _make_file_uri(platform_dir, elem.text)

    # Fallback to searching media folders by ROM basename
    path_elem = game.find("path")
    if path_elem is not None and path_elem.text:
        rom_stem = os.path.splitext(os.path.basename(path_elem.text))[0]

        for media_key, folder_name in ESDE_MEDIA_MAP.items():
            # trunk-ignore(mypy/literal-required)
            if gamelist_media[media_key]:
                continue

            search_pattern = os.path.join(platform_dir, folder_name, f"{rom_stem}.*")
            search_path = fs_platform_handler.validate_path(search_pattern)
            found_files = glob.glob(str(search_path))
            if found_files:
                # trunk-ignore(mypy/literal-required)
                gamelist_media[media_key] = f"file://{str(found_files[0])}"

    return gamelist_media


def extract_metadata_from_gamelist_rom(
    game: Element, platform: Platform
) -> GamelistMetadata:
    rating_elem = game.find("rating")
    releasedate_elem = game.find("releasedate")
    developer_elem = game.find("developer")
    publisher_elem = game.find("publisher")
    family_elem = game.find("family")
    genre_elem = game.find("genre")
    players_elem = game.find("players")
    md5_elem = game.find("md5")

    rating = (
        float(rating_elem.text)
        if rating_elem is not None and rating_elem.text
        else None
    )
    first_release_date = (
        releasedate_elem.text
        if releasedate_elem is not None and releasedate_elem.text
        else None
    )
    developer = (
        developer_elem.text
        if developer_elem is not None and developer_elem.text
        else None
    )
    publisher = (
        publisher_elem.text
        if publisher_elem is not None and publisher_elem.text
        else None
    )
    family = family_elem.text if family_elem is not None and family_elem.text else None
    genre = genre_elem.text if genre_elem is not None and genre_elem.text else None
    players = (
        players_elem.text if players_elem is not None and players_elem.text else None
    )
    md5 = md5_elem.text if md5_elem is not None and md5_elem.text else None

    return GamelistMetadata(
        rating=rating,
        first_release_date=first_release_date,
        companies=pydash.compact([developer, publisher]),
        franchises=pydash.compact([family]),
        genres=pydash.compact([genre]),
        player_count=players,
        md5_hash=md5,
        box3d_path=None,
        miximage_path=None,
        physical_path=None,
        marquee_path=None,
        video_path=None,
        **extract_media_from_gamelist_rom(game, platform),
    )


def populate_rom_specific_paths(
    rom_metadata: GamelistMetadata, rom: Rom
) -> dict[str, str]:
    """Populate ROM-specific paths after retrieving metadata from cache"""
    preferred_media_types = get_preferred_media_types()

    # Create a copy of the metadata to avoid modifying the cached version
    updated_metadata: dict[str, str] = {}

    # Set paths for media types that are preferred
    if MetadataMediaType.BOX3D in preferred_media_types and rom_metadata.get(
        "box3d_url"
    ):
        updated_metadata["box3d_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.BOX3D)}/box3d.png"
        )
    if MetadataMediaType.MARQUEE in preferred_media_types and rom_metadata.get(
        "marquee_url"
    ):
        updated_metadata["marquee_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MARQUEE)}/marquee.png"
        )
    if MetadataMediaType.MIXIMAGE in preferred_media_types and rom_metadata.get(
        "miximage_url"
    ):
        updated_metadata["miximage_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.MIXIMAGE)}/miximage.png"
        )
    if MetadataMediaType.PHYSICAL in preferred_media_types and rom_metadata.get(
        "physical_url"
    ):
        updated_metadata["physical_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.PHYSICAL)}/physical.png"
        )
    if MetadataMediaType.VIDEO in preferred_media_types and rom_metadata.get(
        "video_url"
    ):
        updated_metadata["video_path"] = (
            f"{fs_resource_handler.get_media_resources_path(rom.platform_id, rom.id, MetadataMediaType.VIDEO)}/video.mp4"
        )

    return updated_metadata


class GamelistHandler(MetadataHandler):
    """Handler for ES-DE gamelist.xml metadata source"""

    def __init__(self):
        # Cache for storing parsed gamelist data by platform ID
        self._gamelist_cache = {}

    async def populate_cache(self, platform: Platform):
        if not self.is_enabled():
            return

        # Find the gamelist.xml file for this platform
        gamelist_file_path = await self._find_gamelist_file(platform)
        if not gamelist_file_path:
            return

        # Parse the gamelist file
        self._parse_gamelist_xml(gamelist_file_path, platform)

    def clear_cache(self):
        """Clear the gamelist cache"""
        self._gamelist_cache.clear()

    @classmethod
    def is_enabled(cls) -> bool:
        return True

    async def heartbeat(self) -> bool:
        return True

    async def _find_gamelist_file(self, platform: Platform) -> Path | None:
        """Find the gamelist.xml file for a platform"""
        platform_dir = fs_platform_handler.get_platform_fs_structure(platform.fs_slug)

        # Check for platform-level gamelist.xml
        platform_gamelist = f"{platform_dir}/gamelist.xml"
        if await fs_platform_handler.file_exists(platform_gamelist):
            return fs_platform_handler.validate_path(platform_gamelist)

        return None

    def _parse_gamelist_xml(
        self, gamelist_path: Path, platform: Platform
    ) -> dict[str, GamelistRom]:
        """Parse a gamelist.xml file and return ROM data indexed by filename.
        Results are cached by platform ID  to avoid re-parsing the same file multiple times.
        """
        # Check if we already have cached data for this platform
        cache_key = platform.id
        if cache_key in self._gamelist_cache:
            log.debug(f"Using cached gamelist data for platform {platform.id}")
            return self._gamelist_cache[cache_key]

        preferred_media_types = get_preferred_media_types()
        roms_data: dict[str, GamelistRom] = {}

        try:
            tree = ET.parse(gamelist_path)
            root = tree.getroot()
            if root is None:
                return roms_data

            for game in root.findall("game"):
                path_elem = game.find("path")
                if path_elem is None or path_elem.text is None:
                    continue

                # Handle relative paths
                rom_path = path_elem.text
                if rom_path.startswith("./"):
                    rom_path = rom_path[2:]

                # Extract filename for matching
                rom_filename = os.path.basename(rom_path)

                # Extract metadata
                name_elem = game.find("name")
                desc_elem = game.find("desc")
                lang_elem = game.find("lang")
                region_elem = game.find("region")

                name = (
                    name_elem.text if name_elem is not None and name_elem.text else ""
                )
                summary = (
                    desc_elem.text if desc_elem is not None and desc_elem.text else ""
                )
                regions = (
                    pydash.compact([region_elem.text])
                    if region_elem is not None
                    else []
                )
                languages = (
                    pydash.compact([lang_elem.text]) if lang_elem is not None else []
                )

                # Build ROM data
                rom_metadata = extract_metadata_from_gamelist_rom(game, platform)
                rom_data = GamelistRom(
                    gamelist_id=str(uuid.uuid4()),
                    name=name,
                    summary=summary,
                    regions=regions,
                    languages=languages,
                    gamelist_metadata=rom_metadata,
                )

                # Choose which cover style to use
                cover_url = rom_metadata["box2d_url"] or rom_metadata["image_url"]
                if cover_url:
                    rom_data["url_cover"] = cover_url

                # Grab the manual
                manual_url = rom_metadata["manual_url"]
                if manual_url and MetadataMediaType.MANUAL in preferred_media_types:
                    rom_data["url_manual"] = manual_url

                # Build list of screenshot URLs
                url_screenshots = []
                if (
                    rom_metadata["screenshot_url"]
                    and MetadataMediaType.SCREENSHOT in preferred_media_types
                ):
                    url_screenshots.append(rom_metadata["screenshot_url"])
                if (
                    rom_metadata["title_screen_url"]
                    and MetadataMediaType.TITLE_SCREEN in preferred_media_types
                ):
                    url_screenshots.append(rom_metadata["title_screen_url"])
                rom_data["url_screenshots"] = url_screenshots

                # Store by filename for matching
                roms_data[rom_filename] = rom_data

            # Cache the parsed data for this platform
            self._gamelist_cache[cache_key] = roms_data
        except ET.ParseError as e:
            log.warning(f"Failed to parse gamelist.xml at {gamelist_path}: {e}")
        except Exception as e:
            log.error(f"Error reading gamelist.xml at {gamelist_path}: {e}")

        return roms_data

    async def get_rom(self, fs_name: str, platform: Platform, rom: Rom) -> GamelistRom:
        """Get ROM metadata from gamelist.xml files"""
        if not self.is_enabled():
            return GamelistRom(gamelist_id=None)

        # Find the gamelist.xml file for this platform
        gamelist_file_path = await self._find_gamelist_file(platform)
        if not gamelist_file_path:
            return GamelistRom(gamelist_id=None)

        # Parse the gamelist file
        all_roms_data = self._parse_gamelist_xml(gamelist_file_path, platform)

        # Try to find exact match first
        if fs_name in all_roms_data:
            log.debug(f"Found exact gamelist match for {fs_name}")
            matched_rom = pydash.clone_deep(all_roms_data[fs_name])
            gamelist_metadata = matched_rom.get("gamelist_metadata")

            # Populate ROM-specific paths using the actual rom object
            if gamelist_metadata:
                rom_specific_paths = populate_rom_specific_paths(gamelist_metadata, rom)
                gamelist_metadata.update(**rom_specific_paths)  # type: ignore
                matched_rom["gamelist_metadata"] = gamelist_metadata

            return matched_rom

        return GamelistRom(gamelist_id=None)
