import os
import uuid
from pathlib import Path
from typing import NotRequired, TypedDict
from xml.etree.ElementTree import Element  # trunk-ignore(bandit/B405)

import pydash
from defusedxml import ElementTree as ET

from config.config_manager import config_manager as cm
from handler.filesystem import fs_platform_handler
from logger.logger import log
from models.platform import Platform

from .base_handler import BaseRom, MetadataHandler

# https://github.com/Aloshi/EmulationStation/blob/master/GAMELISTS.md#reference


class GamelistMetadataMedia(TypedDict):
    box2d: str | None
    box2d_back: str | None
    box3d: str | None
    fanart: str | None
    image: str | None
    manual: str | None
    marquee: str | None
    miximage: str | None
    physical: str | None
    screenshot: str | None
    thumbnail: str | None
    title_screen: str | None
    video: str | None


class GamelistMetadata(GamelistMetadataMedia):
    rating: float | None
    first_release_date: str | None
    companies: list[str] | None
    franchises: list[str] | None
    genres: list[str] | None
    player_count: str | None
    md5_hash: str | None


class GamelistRom(BaseRom):
    gamelist_id: str | None
    regions: NotRequired[list[str]]
    languages: NotRequired[list[str]]
    gamelist_metadata: NotRequired[GamelistMetadata]


def get_cover_style() -> str:
    """Get cover art style from config"""
    config = cm.get_config()
    return config.SCAN_ARTWORK_COVER_STYLE


def extract_media_from_gamelist_rom(game: Element) -> GamelistMetadataMedia:
    image_elem = game.find("image")
    video_elem = game.find("video")
    box3d_elem = game.find("box3d")
    box2d_back_elem = game.find("backcover")
    box2d_elem = game.find("cover")
    fanart_elem = game.find("fanart")
    manual_elem = game.find("manual")
    marquee_elem = game.find("marquee")
    miximage_elem = game.find("miximage")
    physical_elem = game.find("physicalmedia")
    screenshot_elem = game.find("screenshot")
    title_screen_elem = game.find("title_screen")
    thumbnail_elem = game.find("thumbnail")

    return GamelistMetadataMedia(
        image=(
            image_elem.text.replace("./", "")
            if image_elem is not None and image_elem.text
            else None
        ),
        video=(
            video_elem.text.replace("./", "")
            if video_elem is not None and video_elem.text
            else None
        ),
        box2d=(
            box2d_elem.text.replace("./", "")
            if box2d_elem is not None and box2d_elem.text
            else None
        ),
        box2d_back=(
            box2d_back_elem.text.replace("./", "")
            if box2d_back_elem is not None and box2d_back_elem.text
            else None
        ),
        box3d=(
            box3d_elem.text.replace("./", "")
            if box3d_elem is not None and box3d_elem.text
            else None
        ),
        fanart=(
            fanart_elem.text.replace("./", "")
            if fanart_elem is not None and fanart_elem.text
            else None
        ),
        manual=(
            manual_elem.text.replace("./", "")
            if manual_elem is not None and manual_elem.text
            else None
        ),
        marquee=(
            marquee_elem.text.replace("./", "")
            if marquee_elem is not None and marquee_elem.text
            else None
        ),
        miximage=(
            miximage_elem.text.replace("./", "")
            if miximage_elem is not None and miximage_elem.text
            else None
        ),
        physical=(
            physical_elem.text.replace("./", "")
            if physical_elem is not None and physical_elem.text
            else None
        ),
        screenshot=(
            screenshot_elem.text.replace("./", "")
            if screenshot_elem is not None and screenshot_elem.text
            else None
        ),
        title_screen=(
            title_screen_elem.text.replace("./", "")
            if title_screen_elem is not None and title_screen_elem.text
            else None
        ),
        thumbnail=(
            thumbnail_elem.text.replace("./", "")
            if thumbnail_elem is not None and thumbnail_elem.text
            else None
        ),
    )


def extract_metadata_from_gamelist_rom(game: Element) -> GamelistMetadata:
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
        **extract_media_from_gamelist_rom(game),
    )


class GamelistHandler(MetadataHandler):
    """Handler for EmulationStation gamelist.xml metadata source"""

    @classmethod
    def is_enabled(cls) -> bool:
        return True

    async def heartbeat(self) -> bool:
        return True

    async def _find_gamelist_file(self, platform: Platform) -> Path | None:
        """Find the gamelist.xml file for a platform"""
        platform_dir = fs_platform_handler.get_plaform_fs_structure(platform.fs_slug)

        # Check for platform-level gamelist.xml
        platform_gamelist = f"{platform_dir}/gamelist.xml"
        if await fs_platform_handler.file_exists(platform_gamelist):
            return fs_platform_handler.validate_path(platform_gamelist)

        return None

    def _parse_gamelist_xml(
        self, gamelist_path: Path, platform: Platform
    ) -> dict[str, GamelistRom]:
        """Parse a gamelist.xml file and return ROM data indexed by filename"""
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
                rom_media = extract_media_from_gamelist_rom(game)
                rom_metadata = extract_metadata_from_gamelist_rom(game)
                rom_data = GamelistRom(
                    gamelist_id=str(uuid.uuid4()),
                    name=name,
                    summary=summary,
                    regions=regions,
                    languages=languages,
                    gamelist_metadata=rom_metadata,
                )

                platform_dir = fs_platform_handler.get_plaform_fs_structure(
                    platform.fs_slug
                )

                # Choose which cover style to use
                cover_path = str(rom_media.get(get_cover_style()))
                if cover_path:
                    cover_path_path = fs_platform_handler.validate_path(
                        f"{platform_dir}/{cover_path}"
                    )
                    rom_data["url_cover"] = f"file://{str(cover_path_path)}"

                # Grab the manual
                if rom_media["manual"]:
                    manual_path = fs_platform_handler.validate_path(
                        f"{platform_dir}/{rom_media['manual']}"
                    )
                    rom_data["url_manual"] = f"file://{str(manual_path)}"

                # Build list of screenshot URLs
                url_screenshots = []
                if rom_media["title_screen"]:
                    title_screen_path = fs_platform_handler.validate_path(
                        f"{platform_dir}/{rom_media['title_screen']}"
                    )
                    url_screenshots.append(f"file://{str(title_screen_path)}")
                if rom_media["screenshot"]:
                    screenshot_path = fs_platform_handler.validate_path(
                        f"{platform_dir}/{rom_media['screenshot']}"
                    )
                    url_screenshots.append(f"file://{str(screenshot_path)}")
                if rom_media["miximage"] and get_cover_style() != "miximage":
                    miximage_path = fs_platform_handler.validate_path(
                        f"{platform_dir}/{rom_media['miximage']}"
                    )
                    url_screenshots.append(f"file://{str(miximage_path)}")
                rom_data["url_screenshots"] = url_screenshots

                # TODO: Add support for importing videos
                # if rom_media["video"]:
                #     video_path = fs_platform_handler.validate_path(
                #         f"{platform_dir}/{rom_media['video']}"
                #     )
                #     rom_data["url_video"] = f"file://{str(video_path)}")

                # Store by filename for matching
                roms_data[rom_filename] = rom_data
        except ET.ParseError as e:
            log.warning(f"Failed to parse gamelist.xml at {gamelist_path}: {e}")
        except Exception as e:
            log.error(f"Error reading gamelist.xml at {gamelist_path}: {e}")

        return roms_data

    async def get_rom(self, fs_name: str, platform: Platform) -> GamelistRom:
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
            return all_roms_data[fs_name]

        return GamelistRom(gamelist_id=None)
