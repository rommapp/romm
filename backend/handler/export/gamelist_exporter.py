import os
from datetime import datetime
from typing import Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from config import YOUTUBE_BASE_URL
from handler.database import db_platform_handler, db_rom_handler
from logger.logger import log
from models.rom import Rom


class GamelistExporter:
    """Export RomM collections to EmulationStation gamelist.xml format"""

    def __init__(self):
        self.base_path = "/romm/library"  # Base path for ROM files

    def _format_release_date(self, date_str: int) -> str:
        """Format release date to YYYYMMDDTHHMMSS format"""
        return f"{date_str // 10000:04d}{date_str % 10000:02d}T000000"

    def _create_game_element(
        self, rom: Rom, platform_dir: str, request=None
    ) -> Element:
        """Create a <game> element for a ROM"""
        game = Element("game")

        # Basic game info
        if request:
            SubElement(game, "path").text = str(
                request.url_for(
                    "get_rom_content",
                    id=rom.id,
                    file_name=rom.fs_name,
                )
            )
        else:
            SubElement(game, "path").text = f"./{rom.fs_name}"
        SubElement(game, "name").text = rom.name or rom.fs_name

        if rom.summary:
            SubElement(game, "desc").text = rom.summary

        # Media files
        if rom.url_cover:
            SubElement(game, "image").text = rom.url_cover

        if rom.youtube_video_id:
            SubElement(game, "video").text = (
                f"{YOUTUBE_BASE_URL}/embed/{rom.youtube_video_id}"
            )

        # Additional metadata
        if rom.metadatum.companies and len(rom.metadatum.companies) > 0:
            SubElement(game, "developer").text = rom.metadatum.companies[0]

        if rom.metadatum.companies and len(rom.metadatum.companies) > 1:
            SubElement(game, "publisher").text = rom.metadatum.companies[1]

        if rom.metadatum.genres and len(rom.metadatum.genres) > 0:
            SubElement(game, "genre").text = rom.metadatum.genres[0]

        if rom.gamelist_metadata and rom.gamelist_metadata["players"]:
            SubElement(game, "players").text = rom.gamelist_metadata["players"]

        if rom.languages and len(rom.languages) > 0:
            SubElement(game, "lang").text = rom.languages[0]

        if rom.regions and len(rom.regions) > 0:
            SubElement(game, "region").text = rom.regions[0]

        if rom.metadatum.first_release_date is not None:
            SubElement(game, "releasedate").text = self._format_release_date(
                rom.metadatum.first_release_date
            )

        if rom.metadatum.average_rating is not None:
            SubElement(game, "rating").text = f"{rom.metadatum.average_rating:.2f}"

        if rom.gamelist_id:
            SubElement(game, "id").text = str(rom.gamelist_id)

        # Add scraping info
        scrap = SubElement(game, "scrap")
        scrap.set("name", "RomM")
        scrap.set("date", datetime.now().strftime("%Y%m%dT%H%M%S"))

        return game

    def export_platform(
        self, platform_id: int, rom_ids: Optional[List[int]] = None, request=None
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
            roms = db_rom_handler.get_roms_by_ids(rom_ids)
        else:
            roms = db_rom_handler.get_roms_scalar(platform_id=platform_id)

        # Create root element
        root = Element("gameList")

        # Platform directory for relative paths
        platform_dir = os.path.join(self.base_path, "roms", platform.fs_slug)

        # Add games
        for rom in roms:
            if rom and not rom.missing_from_fs:
                game_element = self._create_game_element(rom, platform_dir, request)
                root.append(game_element)

        # Convert to XML string
        indent(root, space="  ", level=0)
        xml_str = tostring(root, encoding="unicode", xml_declaration=True)

        log.info(f"Exported {len(roms)} ROMs for platform {platform.name}")
        return xml_str

    def export_multiple_platforms(
        self, platform_ids: List[int], rom_ids: Optional[List[int]] = None, request=None
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
                    xml_content = self.export_platform(platform_id, rom_ids, request)
                    results[platform.fs_slug] = xml_content
            except Exception as e:
                log.error(f"Failed to export platform {platform_id}: {e}")

        return results

    def export_roms_to_file(
        self,
        platform_id: int,
        output_path: str,
        rom_ids: Optional[List[int]] = None,
        request=None,
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
            xml_content = self.export_platform(platform_id, rom_ids, request)

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
