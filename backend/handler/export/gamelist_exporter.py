import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional

from handler.database import db_platform_handler, db_rom_handler
from logger.logger import log
from models.rom import Rom


class GamelistExporter:
    """Export RomM collections to EmulationStation gamelist.xml format"""

    def __init__(self):
        self.base_path = "/romm/library"  # Base path for ROM files

    def _format_release_date(self, date_str: Optional[str]) -> str:
        """Format release date to YYYYMMDDTHHMMSS format"""
        if not date_str:
            return ""

        try:
            # Parse date string (assuming YYYY-MM-DD format)
            if len(date_str) >= 10:
                year = date_str[:4]
                month = date_str[5:7]
                day = date_str[8:10]
                return f"{year}{month}{day}T000000"
        except (ValueError, IndexError):
            pass

        return ""

    def _format_rating(self, rating: Optional[float]) -> str:
        """Format rating to 0.0-1.0 scale"""
        if rating is None:
            return ""

        # Ensure rating is in valid range
        if 0.0 <= rating <= 1.0:
            return str(rating)

        return ""

    def _get_relative_path(self, file_path: str, platform_dir: str) -> str:
        """Convert absolute path to relative path for gamelist.xml"""
        if not file_path:
            return ""

        # Handle file:// URLs
        if file_path.startswith("file://"):
            file_path = file_path[7:]

        # Get relative path from platform directory
        try:
            rel_path = os.path.relpath(file_path, platform_dir)
            return f"./{rel_path}"
        except ValueError:
            # If paths are on different drives, return the original path
            return file_path

    def _get_media_path(
        self, media_url: str, platform_dir: str, media_type: str
    ) -> str:
        """Get relative path for media files"""
        if not media_url:
            return ""

        # Handle file:// URLs
        if media_url.startswith("file://"):
            file_path = media_url[7:]
            return self._get_relative_path(file_path, platform_dir)

        # Handle HTTP URLs - store as-is for now
        return media_url

    def _create_game_element(self, rom: Rom, platform_dir: str) -> ET.Element:
        """Create a <game> element for a ROM"""
        game = ET.Element("game")

        # Basic game info
        ET.SubElement(game, "path").text = f"./{rom.fs_name}"
        ET.SubElement(game, "name").text = rom.name or rom.fs_name

        if rom.summary:
            ET.SubElement(game, "desc").text = rom.summary

        # Media files
        if rom.url_cover:
            image_path = self._get_media_path(rom.url_cover, platform_dir, "image")
            if image_path:
                ET.SubElement(game, "image").text = image_path

        if rom.url_screenshots:
            for screenshot_url in rom.url_screenshots:
                video_path = self._get_media_path(screenshot_url, platform_dir, "video")
                if video_path:
                    ET.SubElement(game, "video").text = video_path
                    break  # Only use first screenshot as video

        # Additional metadata
        if hasattr(rom, "developer") and rom.developer:
            ET.SubElement(game, "developer").text = rom.developer

        if hasattr(rom, "publisher") and rom.publisher:
            ET.SubElement(game, "publisher").text = rom.publisher

        if hasattr(rom, "genre") and rom.genre:
            ET.SubElement(game, "genre").text = rom.genre

        if hasattr(rom, "players") and rom.players:
            ET.SubElement(game, "players").text = rom.players

        if hasattr(rom, "lang") and rom.lang:
            ET.SubElement(game, "lang").text = rom.lang

        if hasattr(rom, "region") and rom.region:
            ET.SubElement(game, "region").text = rom.region

        if hasattr(rom, "releasedate") and rom.releasedate:
            release_date = self._format_release_date(rom.releasedate)
            if release_date:
                ET.SubElement(game, "releasedate").text = release_date

        if hasattr(rom, "rating") and rom.rating is not None:
            rating = self._format_rating(rom.rating)
            if rating:
                ET.SubElement(game, "rating").text = rating

        # Add external ID if available
        if rom.igdb_id:
            ET.SubElement(game, "id").text = str(rom.igdb_id)

        # Add scraping info
        scrap = ET.SubElement(game, "scrap")
        scrap.set("name", "RomM")
        scrap.set("date", datetime.now().strftime("%Y%m%dT%H%M%S"))

        return game

    def export_platform(
        self, platform_id: int, rom_ids: Optional[List[int]] = None
    ) -> str:
        """Export a platform's ROMs to gamelist.xml format

        Args:
            platform_id: Platform ID to export
            rom_ids: Optional list of specific ROM IDs to export

        Returns:
            XML string in gamelist.xml format
        """
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        # Get ROMs for the platform
        if rom_ids:
            roms = [db_rom_handler.get_rom(rom_id) for rom_id in rom_ids]
            roms = [rom for rom in roms if rom and rom.platform_id == platform_id]
        else:
            roms = db_rom_handler.get_roms_scalar(platform_id=platform_id)

        # Create root element
        root = ET.Element("gameList")

        # Platform directory for relative paths
        platform_dir = os.path.join(self.base_path, "roms", platform.fs_slug)

        # Add games
        for rom in roms:
            if rom and not rom.missing_from_fs:
                game_element = self._create_game_element(rom, platform_dir)
                root.append(game_element)

        # Convert to XML string
        ET.indent(root, space="  ", level=0)
        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

        log.info(f"Exported {len(roms)} ROMs for platform {platform.name}")
        return xml_str

    def export_multiple_platforms(
        self, platform_ids: List[int], rom_ids: Optional[List[int]] = None
    ) -> Dict[str, str]:
        """Export multiple platforms to separate gamelist.xml files

        Args:
            platform_ids: List of platform IDs to export
            rom_ids: Optional list of specific ROM IDs to export

        Returns:
            Dictionary mapping platform names to XML strings
        """
        results = {}

        for platform_id in platform_ids:
            try:
                platform = db_platform_handler.get_platform(platform_id)
                if platform:
                    xml_content = self.export_platform(platform_id, rom_ids)
                    results[platform.fs_slug] = xml_content
            except Exception as e:
                log.error(f"Failed to export platform {platform_id}: {e}")

        return results

    def export_roms_to_file(
        self, platform_id: int, output_path: str, rom_ids: Optional[List[int]] = None
    ) -> bool:
        """Export platform ROMs to a gamelist.xml file

        Args:
            platform_id: Platform ID to export
            output_path: Path where to save the gamelist.xml file
            rom_ids: Optional list of specific ROM IDs to export

        Returns:
            True if successful, False otherwise
        """
        try:
            xml_content = self.export_platform(platform_id, rom_ids)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(xml_content)

            log.info(f"Exported gamelist.xml to {output_path}")
            return True

        except Exception as e:
            log.error(f"Failed to export gamelist.xml to {output_path}: {e}")
            return False
