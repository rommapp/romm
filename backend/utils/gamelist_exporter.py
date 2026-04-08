from datetime import UTC, datetime
from xml.etree.ElementTree import (  # trunk-ignore(bandit/B405)
    Element,
    SubElement,
    indent,
    tostring,
)

from fastapi import Request

from config import FRONTEND_RESOURCES_PATH, YOUTUBE_BASE_URL
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler
from logger.logger import log
from models.rom import Rom


def get_media_options_for_export() -> tuple[str, str]:
    """Get media options for export from config"""
    config = cm.get_config()

    return config.GAMELIST_MEDIA_IMAGE, config.GAMELIST_MEDIA_THUMBNAIL


class GamelistExporter:
    """Export RomM collections to ES-DE gamelist.xml format"""

    def __init__(self, local_export: bool = False):
        self.local_export = local_export

    def _format_release_date(self, timestamp: int) -> str:
        """Format release date to YYYYMMDDTHHMMSS format"""
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime(
            "%Y%m%dT%H%M%S"
        )

    def _create_game_element(
        self, rom: Rom, request: Request | None, media_image: str, media_thumbnail: str
    ) -> Element:
        """Create a <game> element for a ROM"""
        game = Element("game")

        # Basic game info
        if self.local_export:
            SubElement(game, "path").text = f"./{rom.fs_name}"
        else:
            if request is None:
                raise ValueError(
                    "Request object must be provided for non-local exports"
                )
            SubElement(game, "path").text = str(
                request.url_for(
                    "get_rom_content",
                    id=rom.id,
                    file_name=rom.fs_name,
                )
            )

        SubElement(game, "name").text = rom.name or rom.fs_name

        if rom.summary:
            SubElement(game, "desc").text = rom.summary

        # Media files
        thumbnail_path: str | None = None
        match media_thumbnail:
            case "box3d":
                if rom.ss_metadata and rom.ss_metadata.get("box3d_path"):
                    thumbnail_path = (
                        f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['box3d_path']}"
                    )
                elif rom.gamelist_metadata and rom.gamelist_metadata.get("box3d_path"):
                    thumbnail_path = f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['box3d_path']}"
            case "miximage":
                if rom.ss_metadata and rom.ss_metadata.get("miximage_path"):
                    thumbnail_path = (
                        f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['miximage_path']}"
                    )
                elif rom.gamelist_metadata and rom.gamelist_metadata.get(
                    "miximage_path"
                ):
                    thumbnail_path = f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['miximage_path']}"
            case "physical":
                if rom.ss_metadata and rom.ss_metadata.get("physical_path"):
                    thumbnail_path = (
                        f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['physical_path']}"
                    )
                elif rom.gamelist_metadata and rom.gamelist_metadata.get(
                    "physical_path"
                ):
                    thumbnail_path = f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['physical_path']}"

        # "cover" and "box2d" both map to path_cover_l
        if thumbnail_path is None and rom.path_cover_l:
            thumbnail_path = f"{FRONTEND_RESOURCES_PATH}/{rom.path_cover_l}"
        if thumbnail_path:
            SubElement(game, "thumbnail").text = thumbnail_path

        if path_video := rom.path_video:
            SubElement(game, "video").text = f"{FRONTEND_RESOURCES_PATH}/{path_video}"
        elif rom.youtube_video_id:
            SubElement(game, "video").text = (
                f"{YOUTUBE_BASE_URL}/embed/{rom.youtube_video_id}"
            )

        if rom.path_screenshots:
            SubElement(game, "screenshot").text = (
                f"{FRONTEND_RESOURCES_PATH}/{rom.path_screenshots[0]}"
            )

        image_path: str | None = None
        match media_image:
            case "title_screen":
                if rom.ss_metadata and rom.ss_metadata.get("title_screen_path"):
                    image_path = f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['title_screen_path']}"
                elif rom.gamelist_metadata and rom.gamelist_metadata.get(
                    "title_screen_path"
                ):
                    image_path = f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['title_screen_path']}"
            case "miximage":
                if rom.ss_metadata and rom.ss_metadata.get("miximage_path"):
                    image_path = (
                        f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['miximage_path']}"
                    )
                elif rom.gamelist_metadata and rom.gamelist_metadata.get(
                    "miximage_path"
                ):
                    image_path = f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['miximage_path']}"
            case "box2d":
                if rom.path_cover_l:
                    image_path = f"{FRONTEND_RESOURCES_PATH}/{rom.path_cover_l}"

        # "screenshot" (default) and anything else falls through to path_screenshots
        if image_path is None and rom.path_screenshots:
            image_path = f"{FRONTEND_RESOURCES_PATH}/{rom.path_screenshots[0]}"
        if image_path:
            SubElement(game, "image").text = image_path

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

        if rom.metadatum.franchises and len(rom.metadatum.franchises) > 0:
            SubElement(game, "family").text = rom.metadatum.franchises[0]

        if rom.metadatum.player_count:
            SubElement(game, "players").text = rom.metadatum.player_count

        if rom.languages and len(rom.languages) > 0:
            SubElement(game, "lang").text = rom.languages[0]

        if rom.regions and len(rom.regions) > 0:
            SubElement(game, "region").text = rom.regions[0]

        if rom.metadatum.first_release_date is not None:
            SubElement(game, "releasedate").text = self._format_release_date(
                rom.metadatum.first_release_date
            )

        if rom.metadatum.average_rating is not None:
            # average_rating is on a 0-100 scale (DB view averages all scrapers on that scale)
            # gamelist.xml expects a 0-1 scale
            gamelist_rating = rom.metadatum.average_rating / 100
            SubElement(game, "rating").text = f"{gamelist_rating:.2f}"

        if rom.gamelist_id:
            SubElement(game, "id").text = str(rom.gamelist_id)

        # Provider specific metadata
        if rom.ss_metadata:
            if rom.ss_metadata.get("box3d_path"):
                SubElement(game, "box3d").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['box3d_path']}"
                )
            if rom.ss_metadata.get("box2d_back_path"):
                SubElement(game, "boxback").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['box2d_back_path']}"
                )
            if rom.ss_metadata.get("fanart_path"):
                SubElement(game, "fanart").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['fanart_path']}"
                )
            if rom.ss_metadata.get("logo_path"):
                SubElement(game, "marquee").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['logo_path']}"
                )
            if rom.ss_metadata.get("miximage_path"):
                SubElement(game, "miximage").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['miximage_path']}"
                )
            if rom.ss_metadata.get("physical_path"):
                SubElement(game, "physicalmedia").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['physical_path']}"
                )
            if rom.ss_metadata.get("title_screen_path"):
                SubElement(game, "title_screen").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['title_screen_path']}"
                )
            if rom.ss_metadata.get("bezel_path"):
                SubElement(game, "bezel").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.ss_metadata['bezel_path']}"
                )

        if rom.gamelist_metadata:
            if rom.gamelist_metadata.get("box3d_path"):
                SubElement(game, "box3d").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['box3d_path']}"
                )
            if rom.gamelist_metadata.get("box2d_back_path"):
                SubElement(game, "boxback").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['box2d_back_path']}"
                )
            if rom.gamelist_metadata.get("fanart_path"):
                SubElement(game, "fanart").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['fanart_path']}"
                )
            if rom.gamelist_metadata.get("marquee_path"):
                SubElement(game, "marquee").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['marquee_path']}"
                )
            if rom.gamelist_metadata.get("miximage_path"):
                SubElement(game, "miximage").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['miximage_path']}"
                )
            if rom.gamelist_metadata.get("physical_path"):
                SubElement(game, "physicalmedia").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['physical_path']}"
                )
            if rom.gamelist_metadata.get("title_screen_path"):
                SubElement(game, "title_screen").text = (
                    f"{FRONTEND_RESOURCES_PATH}/{rom.gamelist_metadata['title_screen_path']}"
                )

        # Add scraping info
        scrap = SubElement(game, "scrap")
        scrap.set("name", "RomM")
        scrap.set("date", datetime.now().strftime("%Y%m%dT%H%M%S"))

        return game

    def export_platform_to_xml(self, platform_id: int, request: Request | None) -> str:
        """Export a platform's ROMs to gamelist.xml format

        Args:
            platform_id: Platform ID to export

        Returns:
            XML string in gamelist.xml format
        """
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        roms = db_rom_handler.get_roms_scalar(platform_ids=[platform_id])

        # Create root element
        root = Element("gameList")

        media_image, media_thumbnail = get_media_options_for_export()

        for rom in roms:
            if rom and not rom.missing_from_fs and rom.fs_name != "gamelist.xml":
                game_element = self._create_game_element(
                    rom,
                    request=request,
                    media_image=media_image,
                    media_thumbnail=media_thumbnail,
                )
                root.append(game_element)

        # Convert to XML string
        indent(root, space="  ", level=0)
        xml_str = tostring(root, encoding="unicode", xml_declaration=True)

        log.info(f"Exported {len(roms)} ROMs for platform {platform.name}")
        return xml_str

    async def export_platform_to_file(
        self,
        platform_id: int,
        request: Request | None,
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

            platform_fs_structure = fs_platform_handler.get_platform_fs_structure(
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
