import os
import xml.etree.ElementTree as ET
from typing import NotRequired

from handler.filesystem import fs_rom_handler
from logger.logger import log
from models.platform import Platform

from .base_handler import BaseRom, MetadataHandler


class GamelistRom(BaseRom):
    """ROM data extracted from gamelist.xml"""

    gamelist_id: str | None
    developer: NotRequired[str | None]
    publisher: NotRequired[str | None]
    genre: NotRequired[str | None]
    players: NotRequired[str | None]
    lang: NotRequired[str | None]
    region: NotRequired[str | None]
    releasedate: NotRequired[str | None]
    rating: NotRequired[float | None]
    hidden: NotRequired[bool]
    marquee: NotRequired[str | None]
    thumbnail: NotRequired[str | None]


class GamelistHandler(MetadataHandler):
    """Handler for EmulationStation gamelist.xml metadata source"""

    @classmethod
    def is_enabled(cls) -> bool:
        """Gamelist handler is always enabled (no API keys required)"""
        return True

    def _parse_release_date(self, date_str: str | None) -> str | None:
        """Parse release date from YYYYMMDDTHHMMSS format"""
        if not date_str:
            return None

        try:
            # Convert YYYYMMDDTHHMMSS to YYYY-MM-DD
            if len(date_str) >= 8:
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:8]
                return f"{year}-{month}-{day}"
        except (ValueError, IndexError):
            pass

        return None

    def _parse_rating(self, rating_str: str | None) -> float | None:
        """Parse rating from 0.0-1.0 scale"""
        if not rating_str:
            return None

        try:
            rating = float(rating_str)
            # Ensure rating is in valid range
            if 0.0 <= rating <= 1.0:
                return rating
        except (ValueError, TypeError):
            pass

        return None

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

        # Check for ROM-level gamelist.xml files (for multi-file ROMs)
        try:
            for rom_name in os.listdir(platform_dir):
                rom_path = os.path.join(platform_dir, rom_name)
                if os.path.isdir(rom_path):
                    # Check if this is a multi-file ROM directory
                    rom_gamelist = os.path.join(rom_path, "gamelist.xml")
                    if os.path.exists(rom_gamelist):
                        gamelist_files.append((rom_gamelist, rom_path))
        except OSError:
            pass

        return gamelist_files

    def _parse_gamelist_xml(
        self, gamelist_path: str, rom_dir: str
    ) -> dict[str, GamelistRom]:
        """Parse a gamelist.xml file and return ROM data indexed by filename"""
        roms_data = {}

        try:
            tree = ET.parse(gamelist_path)
            root = tree.getroot()

            for game in root.findall("game"):
                # Get ROM path from XML
                path_elem = game.find("path")
                if path_elem is None or path_elem.text is None:
                    continue

                rom_path = path_elem.text

                # Handle relative paths
                if rom_path.startswith("./"):
                    rom_path = rom_path[2:]

                # Extract filename for matching
                rom_filename = os.path.basename(rom_path)

                # Extract metadata
                name_elem = game.find("name")
                desc_elem = game.find("desc")
                image_elem = game.find("image")
                video_elem = game.find("video")
                marquee_elem = game.find("marquee")
                thumbnail_elem = game.find("thumbnail")
                rating_elem = game.find("rating")
                releasedate_elem = game.find("releasedate")
                developer_elem = game.find("developer")
                publisher_elem = game.find("publisher")
                genre_elem = game.find("genre")
                players_elem = game.find("players")
                lang_elem = game.find("lang")
                region_elem = game.find("region")
                id_elem = game.find("id")
                hidden_elem = game.find("hidden")

                # Build ROM data
                rom_data = GamelistRom(
                    gamelist_id=id_elem.text if id_elem is not None else None,
                    name=name_elem.text if name_elem is not None else "",
                    summary=desc_elem.text if desc_elem is not None else "",
                    url_cover="",
                    url_screenshots=[],
                    url_manual="",
                    developer=(
                        developer_elem.text if developer_elem is not None else None
                    ),
                    publisher=(
                        publisher_elem.text if publisher_elem is not None else None
                    ),
                    genre=genre_elem.text if genre_elem is not None else None,
                    players=players_elem.text if players_elem is not None else None,
                    lang=lang_elem.text if lang_elem is not None else None,
                    region=region_elem.text if region_elem is not None else None,
                    releasedate=self._parse_release_date(
                        releasedate_elem.text if releasedate_elem is not None else None
                    ),
                    rating=self._parse_rating(
                        rating_elem.text if rating_elem is not None else None
                    ),
                    hidden=(
                        hidden_elem.text == "true" if hidden_elem is not None else False
                    ),
                    marquee=None,
                    thumbnail=None,
                )

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

                if marquee_elem is not None and marquee_elem.text:
                    rom_data["marquee"] = self._resolve_media_path(
                        marquee_elem.text, rom_dir
                    )

                if thumbnail_elem is not None and thumbnail_elem.text:
                    rom_data["thumbnail"] = self._resolve_media_path(
                        thumbnail_elem.text, rom_dir
                    )

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
            return GamelistRom(
                gamelist_id=None,
                name="",
                summary="",
                url_cover="",
                url_screenshots=[],
                url_manual="",
                developer=None,
                publisher=None,
                genre=None,
                players=None,
                lang=None,
                region=None,
                releasedate=None,
                rating=None,
                hidden=False,
                marquee=None,
                thumbnail=None,
            )

        # Find all gamelist.xml files for this platform
        gamelist_files = self._find_gamelist_files(platform)

        if not gamelist_files:
            return GamelistRom(
                gamelist_id=None,
                name="",
                summary="",
                url_cover="",
                url_screenshots=[],
                url_manual="",
                developer=None,
                publisher=None,
                genre=None,
                players=None,
                lang=None,
                region=None,
                releasedate=None,
                rating=None,
                hidden=False,
                marquee=None,
                thumbnail=None,
            )

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

        return GamelistRom(
            gamelist_id=None,
            name="",
            summary="",
            url_cover="",
            url_screenshots=[],
            url_manual="",
            developer=None,
            publisher=None,
            genre=None,
            players=None,
            lang=None,
            region=None,
            releasedate=None,
            rating=None,
            hidden=False,
            marquee=None,
            thumbnail=None,
        )
