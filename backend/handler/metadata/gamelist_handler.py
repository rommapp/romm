import os
from typing import NotRequired, TypedDict
from xml.etree.ElementTree import Element

import pydash
from defusedxml import ElementTree as ET

from handler.filesystem import fs_rom_handler
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
    player_count: int | None
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
        int(players_elem.text)
        if players_elem is not None and players_elem.text
        else None
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

    def _find_gamelist_files(self, platform: Platform) -> list[tuple[str, str]]:
        """Find gamelist.xml files for a platform

        Returns:
            List of (gamelist_path, rom_path) tuples
        """
        gamelist_files = []

        # Get platform ROM directory
        roms_path = fs_rom_handler.get_roms_fs_structure(platform.fs_slug)
        platform_dir = os.path.join(roms_path, platform.fs_slug)

        # Check for platform-level gamelist.xml
        platform_gamelist = os.path.join(platform_dir, "gamelist.xml")
        if os.path.exists(platform_gamelist):
            gamelist_files.append((platform_gamelist, platform_dir))

        return gamelist_files

    def _parse_gamelist_xml(
        self, gamelist_path: str, rom_dir: str
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

                rom_path = path_elem.text
                gamelist_id = game.find("id")

                # Handle relative paths
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
                    gamelist_id=gamelist_id.text if gamelist_id is not None else None,
                    name=name,
                    summary=summary,
                    regions=regions,
                    languages=languages,
                    gamelist_metadata=extract_metadata_from_gamelist_rom(game),
                )

                image_elem = game.find("image")
                video_elem = game.find("video")
                # marquee_elem = game.find("marquee")
                # thumbnail_elem = game.find("thumbnail")

                # Handle media files
                if image_elem is not None and image_elem.text:
                    cover_url = self._resolve_media_path(image_elem.text, rom_dir)
                    if cover_url:
                        rom_data["url_cover"] = cover_url

                if video_elem is not None and video_elem.text:
                    # Store video as first screenshot for now
                    video_url = self._resolve_media_path(video_elem.text, rom_dir)
                    if video_url:
                        rom_data["url_screenshots"] = [video_url]

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

        # Find all gamelist.xml files for this platform
        gamelist_files = self._find_gamelist_files(platform)

        if not gamelist_files:
            return GamelistRom(gamelist_id=None)

        # Parse all gamelist files
        all_roms_data = {}
        for gamelist_path, rom_dir in gamelist_files:
            roms_data = self._parse_gamelist_xml(gamelist_path, rom_dir)
            all_roms_data.update(roms_data)

        # Try to find exact match first
        if fs_name in all_roms_data:
            log.debug(f"Found exact gamelist match for {fs_name}")
            return all_roms_data[fs_name]

        # Try to find match by filename without extension
        fs_name_no_ext = fs_rom_handler.get_file_name_with_no_extension(fs_name)
        for rom_filename, rom_data in all_roms_data.items():
            rom_filename_no_ext = fs_rom_handler.get_file_name_with_no_extension(
                rom_filename
            )
            if rom_filename_no_ext == fs_name_no_ext:
                log.debug(
                    f"Found gamelist match by name for {fs_name} -> {rom_filename}"
                )
                return rom_data

        # Try fuzzy matching
        best_match, best_score = self.find_best_match(
            fs_name_no_ext,
            [
                fs_rom_handler.get_file_name_with_no_extension(f)
                for f in all_roms_data.keys()
            ],
            min_similarity_score=0.8,
        )

        if best_match:
            log.debug(f"Found fuzzy gamelist match for {fs_name} -> {best_match}")
            return all_roms_data[best_match]

        return GamelistRom(gamelist_id=None)
