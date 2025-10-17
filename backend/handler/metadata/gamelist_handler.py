import os
import uuid
from pathlib import Path
from typing import NotRequired, TypedDict
from xml.etree.ElementTree import Element

import pydash
from defusedxml import ElementTree as ET

from handler.filesystem import fs_platform_handler
from logger.logger import log
from models.platform import Platform

from .base_handler import BaseRom, MetadataHandler

# https://github.com/Aloshi/EmulationStation/blob/master/GAMELISTS.md#reference


class GamelistMetadata(TypedDict):
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
    )


class GamelistHandler(MetadataHandler):
    """Handler for EmulationStation gamelist.xml metadata source"""

    @classmethod
    def is_enabled(cls) -> bool:
        return True

    async def heartbeat(self) -> bool:
        return True

    def _resolve_media_path(
        self, media_path: str | None, gamelist_dir: str
    ) -> str | None:
        """Convert relative media path to file:// URL"""
        if not media_path:
            return None

        # Handle relative paths starting with ./
        if media_path.startswith("./"):
            media_path = media_path[2:]

        # Build absolute path
        abs_path = os.path.join(gamelist_dir, media_path)

        # Check if file exists
        if os.path.exists(abs_path):
            return f"file://{os.path.abspath(abs_path)}"

        return None

    async def _find_gamelist_file(self, platform: Platform) -> Path | None:
        """Find the gamelist.xml file for a platform"""
        platform_dir = fs_platform_handler.get_plaform_fs_structure(platform.fs_slug)

        # Check for platform-level gamelist.xml
        platform_gamelist = f"{platform_dir}/gamelist.xml"
        if await fs_platform_handler.file_exists(platform_gamelist):
            return fs_platform_handler.validate_path(platform_gamelist)

        return None

    def _parse_gamelist_xml(self, gamelist_path: Path) -> dict[str, GamelistRom]:
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
                rom_data = GamelistRom(
                    gamelist_id=str(uuid.uuid4()),
                    name=name,
                    summary=summary,
                    regions=regions,
                    languages=languages,
                    gamelist_metadata=extract_metadata_from_gamelist_rom(game),
                )

                # image_elem = game.find("image")
                # video_elem = game.find("video")
                # marquee_elem = game.find("marquee")
                # thumbnail_elem = game.find("thumbnail")

                # Handle media files
                # if image_elem is not None and image_elem.text:
                #     cover_url = self._resolve_media_path(image_elem.text, gamelist_path)
                #     if cover_url:
                #         rom_data["url_cover"] = cover_url

                # if video_elem is not None and video_elem.text:
                #     # Store video as first screenshot for now
                #     video_url = self._resolve_media_path(video_elem.text, gamelist_path)
                #     if video_url:
                #         rom_data["url_screenshots"] = [video_url]

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
        all_roms_data = self._parse_gamelist_xml(gamelist_file_path)

        # Try to find exact match first
        if fs_name in all_roms_data:
            log.debug(f"Found exact gamelist match for {fs_name}")
            return all_roms_data[fs_name]

        return GamelistRom(gamelist_id=None)
