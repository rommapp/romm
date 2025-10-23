from datetime import datetime
from xml.etree.ElementTree import (  # trunk-ignore(bandit/B405)
    Element,
    SubElement,
    indent,
    tostring,
)

from config import FRONTEND_RESOURCES_PATH, YOUTUBE_BASE_URL
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler
from logger.logger import log
from models.rom import Rom


class GamelistExporter:
    """Export RomM collections to ES-DE gamelist.xml format"""

    def _format_release_date(self, timestamp: int) -> str:
        """Format release date to YYYYMMDDTHHMMSS format"""
        return datetime.fromtimestamp(timestamp).strftime("%Y%m%dT%H%M%S")

    def _create_game_element(self, rom: Rom, request=None) -> Element:
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
        if rom.path_cover_large:
            SubElement(game, "cover").text = (
                f"{FRONTEND_RESOURCES_PATH}/{rom.path_cover_large}"
            )

        if rom.youtube_video_id:
            SubElement(game, "video").text = (
                f"{YOUTUBE_BASE_URL}/embed/{rom.youtube_video_id}"
            )

        if rom.path_screenshots:
            SubElement(game, "screenshot").text = (
                f"{FRONTEND_RESOURCES_PATH}/{rom.path_screenshots[0]}"
            )

        if rom.path_manual:
            SubElement(game, "manual").text = (
                f"{FRONTEND_RESOURCES_PATH}/{rom.path_manual}"
            )

        # Additional metadata
        if rom.metadatum.companies and len(rom.metadatum.companies) > 0:
            SubElement(game, "developer").text = rom.metadatum.companies[0]

        if rom.metadatum.companies and len(rom.metadatum.companies) > 1:
            SubElement(game, "publisher").text = rom.metadatum.companies[1]

        if rom.metadatum.genres and len(rom.metadatum.genres) > 0:
            SubElement(game, "genre").text = rom.metadatum.genres[0]

        if rom.languages and len(rom.languages) > 0:
            SubElement(game, "lang").text = rom.languages[0]

        if rom.regions and len(rom.regions) > 0:
            SubElement(game, "region").text = rom.regions[0]

        if rom.metadatum.first_release_date is not None:
            SubElement(game, "releasedate").text = self._format_release_date(
                rom.metadatum.first_release_date
            )

        if rom.metadatum.average_rating is not None:
            # average_rating in is on a 0-10 scale, but gamelist.xml expects a 0-1 scale
            SubElement(game, "rating").text = f"{rom.metadatum.average_rating / 10:.2f}"

        if rom.gamelist_id:
            SubElement(game, "id").text = str(rom.gamelist_id)

        # Provider specific metadata
        if rom.ss_metadata:
            if rom.ss_metadata.get("box3d"):
                SubElement(game, "box3d").text = rom.ss_metadata["box3d"]
            if rom.ss_metadata.get("box2d_back"):
                SubElement(game, "backcover").text = rom.ss_metadata["box2d_back"]
            if rom.ss_metadata.get("fanart"):
                SubElement(game, "fanart").text = rom.ss_metadata["fanart"]
            if rom.ss_metadata.get("marquee"):
                SubElement(game, "marquee").text = rom.ss_metadata["marquee"]
            if rom.ss_metadata.get("miximage"):
                SubElement(game, "miximage").text = rom.ss_metadata["miximage"]
            if rom.ss_metadata.get("physical"):
                SubElement(game, "physicalmedia").text = rom.ss_metadata["physical"]
            if rom.ss_metadata.get("title_screen"):
                SubElement(game, "title_screen").text = rom.ss_metadata["title_screen"]

        if rom.gamelist_metadata:
            if rom.gamelist_metadata.get("box3d"):
                SubElement(game, "box3d").text = rom.gamelist_metadata["box3d"]
            if rom.gamelist_metadata.get("box2d_back"):
                SubElement(game, "backcover").text = rom.gamelist_metadata["box2d_back"]
            if rom.gamelist_metadata.get("fanart"):
                SubElement(game, "fanart").text = rom.gamelist_metadata["fanart"]
            if rom.gamelist_metadata.get("marquee"):
                SubElement(game, "marquee").text = rom.gamelist_metadata["marquee"]
            if rom.gamelist_metadata.get("miximage"):
                SubElement(game, "miximage").text = rom.gamelist_metadata["miximage"]
            if rom.gamelist_metadata.get("player_count"):
                SubElement(game, "players").text = rom.gamelist_metadata["player_count"]
            if rom.gamelist_metadata.get("physical"):
                SubElement(game, "physicalmedia").text = rom.gamelist_metadata[
                    "physical"
                ]
            if rom.gamelist_metadata.get("title_screen"):
                SubElement(game, "title_screen").text = rom.gamelist_metadata[
                    "title_screen"
                ]

        # Add scraping info
        scrap = SubElement(game, "scrap")
        scrap.set("name", "RomM")
        scrap.set("date", datetime.now().strftime("%Y%m%dT%H%M%S"))

        return game

    def export_platform_to_xml(self, platform_id: int, request=None) -> str:
        """Export a platform's ROMs to gamelist.xml format

        Args:
            platform_id: Platform ID to export

        Returns:
            XML string in gamelist.xml format
        """
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        roms = db_rom_handler.get_roms_scalar(platform_id=platform_id)

        # Create root element
        root = Element("gameList")

        for rom in roms:
            if rom and not rom.missing_from_fs:
                game_element = self._create_game_element(rom, request=request)
                root.append(game_element)

        # Convert to XML string
        indent(root, space="  ", level=0)
        xml_str = tostring(root, encoding="unicode", xml_declaration=True)

        log.info(f"Exported {len(roms)} ROMs for platform {platform.name}")
        return xml_str

    async def export_platform_to_file(
        self,
        platform_id: int,
        request=None,
    ) -> bool:
        """Export platform ROMs to gamelist.xml file in the platform's directory

        Args:
            platform_id: Platform ID to export
            request: FastAPI request object for URL generation

        Returns:
            True if successful, False otherwise
        """
        try:
            platform = db_platform_handler.get_platform(platform_id)
            if not platform:
                log.error(f"Platform with ID {platform_id} not found")
                return False

            platform_fs_structure = fs_platform_handler.get_plaform_fs_structure(
                platform.fs_slug
            )

            xml_content = self.export_platform_to_xml(platform_id, request=request)
            await fs_platform_handler.write_file(
                xml_content.encode("utf-8"), platform_fs_structure, "gamelist.xml"
            )

            log.info(f"Exported gamelist.xml to {platform_fs_structure}/gamelist.xml")
            return True
        except Exception as e:
            log.error(f"Failed to export gamelist.xml for platform {platform_id}: {e}")
            return False
