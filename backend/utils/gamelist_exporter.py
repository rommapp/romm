import shutil
from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import (  # trunk-ignore(bandit/B405)
    Element,
    SubElement,
    indent,
    tostring,
)

from fastapi import Request
from starlette.datastructures import URLPath

from config import FRONTEND_RESOURCES_PATH, YOUTUBE_BASE_URL
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler, fs_resource_handler
from logger.logger import log
from models.rom import Rom

# Map gamelist asset keys to subdirectory names inside assets/
ASSET_DIRS: dict[str, str] = {
    "box2d": "covers",
    "box3d": "boxes",
    "box2d_back": "backcovers",
    "fanart": "fanart",
    "marquee": "marquees",
    "miximage": "miximages",
    "physical": "physical",
    "screenshot": "screenshots",
    "title_screen": "titlescreens",
    "bezel": "bezels",
    "video": "videos",
    "manual": "manuals",
}


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

    def _collect_assets(self, rom: Rom) -> dict[str, Path]:
        """Collect available media assets for a ROM.

        Returns a dict mapping gamelist asset key to the absolute source file path.
        """
        assets: dict[str, Path] = {}

        if rom.path_cover_l:
            assets["box2d"] = fs_resource_handler.validate_path(rom.path_cover_l)

        if rom.path_screenshots:
            assets["screenshot"] = fs_resource_handler.validate_path(
                rom.path_screenshots[0]
            )

        if rom.path_video:
            assets["video"] = fs_resource_handler.validate_path(rom.path_video)

        if rom.path_manual:
            assets["manual"] = fs_resource_handler.validate_path(rom.path_manual)

        ss = rom.ss_metadata or {}
        gl = rom.gamelist_metadata or {}

        # Each gamelist asset key may be sourced from screenscraper or gamelist
        # metadata; preference order is screenscraper first, gamelist second.
        extended: dict[str, list[str]] = {
            "box3d": [ss.get("box3d_path", ""), gl.get("box3d_path", "")],
            "box2d_back": [
                ss.get("box2d_back_path", ""),
                gl.get("box2d_back_path", ""),
            ],
            "fanart": [ss.get("fanart_path", ""), gl.get("fanart_path", "")],
            "marquee": [ss.get("logo_path", ""), gl.get("marquee_path", "")],
            "miximage": [ss.get("miximage_path", ""), gl.get("miximage_path", "")],
            "physical": [ss.get("physical_path", ""), gl.get("physical_path", "")],
            "title_screen": [
                ss.get("title_screen_path", ""),
                gl.get("title_screen_path", ""),
            ],
            "bezel": [ss.get("bezel_path", "")],
        }

        for asset_key, candidates in extended.items():
            for candidate in candidates:
                if candidate:
                    assets[asset_key] = fs_resource_handler.validate_path(candidate)
                    break

        return assets

    def _build_asset_refs(
        self,
        rom: Rom,
        request: Request | None,
        assets: dict[str, Path],
        platform_dir: Path | None = None,
    ) -> dict[str, str]:
        """Build the asset references that will appear in gamelist.xml.

        For local exports, returns relative paths like ``assets/covers/<rom>.jpg``
        and, if ``platform_dir`` is provided, copies the source files into place.

        For non-local exports, returns absolute URLs built from ``request.base_url``.
        """
        refs: dict[str, str] = {}

        if self.local_export:
            for asset_key, source_path in assets.items():
                subdir = ASSET_DIRS.get(asset_key, asset_key)
                dest_name = f"{rom.fs_name_no_ext}{source_path.suffix}"
                rel_path = f"./assets/{subdir}/{dest_name}"

                if platform_dir is not None:
                    dest_path = platform_dir / rel_path
                    if not self._copy_asset(source_path, dest_path):
                        continue

                refs[asset_key] = rel_path
            return refs

        if request is None:
            raise ValueError("Request object must be provided for non-local exports")

        for asset_key, source_path in assets.items():
            resource_part = source_path.relative_to(
                Path(fs_resource_handler.base_path).resolve()
            )
            refs[asset_key] = str(
                URLPath(
                    f"{FRONTEND_RESOURCES_PATH}/{resource_part.as_posix()}"
                ).make_absolute_url(request.base_url)
            )

        return refs

    def _copy_asset(self, source: Path, dest: Path) -> bool:
        """Copy a file from source to dest. Returns True on success."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return True

        try:
            with open(source, "rb") as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return True
        except OSError as e:
            log.warning(f"Failed to copy {source} -> {dest}: {e}")
            return False

    def _create_game_element(
        self,
        rom: Rom,
        request: Request | None,
        asset_refs: dict[str, str],
        media_image: str,
        media_thumbnail: str,
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

        # Thumbnail: prefer media_thumbnail option, fall back to box2d (cover)
        thumbnail = asset_refs.get(media_thumbnail) or asset_refs.get("box2d")
        if thumbnail:
            SubElement(game, "thumbnail").text = thumbnail

        if "video" in asset_refs:
            SubElement(game, "video").text = asset_refs["video"]
        elif rom.youtube_video_id:
            SubElement(game, "video").text = (
                f"{YOUTUBE_BASE_URL}/embed/{rom.youtube_video_id}"
            )

        if "screenshot" in asset_refs:
            SubElement(game, "screenshot").text = asset_refs["screenshot"]

        # Image: prefer media_image option, fall back to screenshot
        image = asset_refs.get(media_image) or asset_refs.get("screenshot")
        if image:
            SubElement(game, "image").text = image

        if "manual" in asset_refs:
            SubElement(game, "manual").text = asset_refs["manual"]

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

        # Dedicated asset elements
        element_names: dict[str, str] = {
            "box3d": "box3d",
            "box2d_back": "boxback",
            "fanart": "fanart",
            "marquee": "marquee",
            "miximage": "miximage",
            "physical": "physicalmedia",
            "title_screen": "title_screen",
            "bezel": "bezel",
        }
        for asset_key, tag in element_names.items():
            if asset_key in asset_refs:
                SubElement(game, tag).text = asset_refs[asset_key]

        # Add scraping info
        scrap = SubElement(game, "scrap")
        scrap.set("name", "RomM")
        scrap.set("date", datetime.now().strftime("%Y%m%dT%H%M%S"))

        return game

    def _build_gamelist_xml(
        self,
        platform_id: int,
        request: Request | None,
        platform_dir: Path | None,
    ) -> tuple[str, int]:
        """Build gamelist XML, optionally copying assets into ``platform_dir/assets/``."""
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        roms = db_rom_handler.get_roms_scalar(platform_ids=[platform_id])

        root = Element("gameList")
        media_image, media_thumbnail = get_media_options_for_export()

        count = 0
        for rom in roms:
            if not rom or rom.missing_from_fs or rom.fs_name == "gamelist.xml":
                continue

            assets = self._collect_assets(rom)
            asset_refs = self._build_asset_refs(
                rom, request=request, assets=assets, platform_dir=platform_dir
            )

            game_element = self._create_game_element(
                rom,
                request=request,
                asset_refs=asset_refs,
                media_image=media_image,
                media_thumbnail=media_thumbnail,
            )
            root.append(game_element)
            count += 1

        indent(root, space="  ", level=0)
        xml_str = tostring(root, encoding="unicode", xml_declaration=True)
        log.info(f"Exported {count} ROMs for platform {platform.name}")
        return xml_str, count

    def export_platform_to_xml(self, platform_id: int, request: Request | None) -> str:
        """Export a platform's ROMs to gamelist.xml format (no asset files copied)."""
        xml_str, _ = self._build_gamelist_xml(
            platform_id, request=request, platform_dir=None
        )
        return xml_str

    async def export_platform_to_file(
        self,
        platform_id: int,
        request: Request | None,
    ) -> bool:
        """Export platform ROMs to gamelist.xml in the platform's directory,
        copying media assets into a local assets/ folder when local_export=True.

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
            platform_dir = (
                fs_platform_handler.base_path / platform_fs_structure
                if self.local_export
                else None
            )

            xml_content, _ = self._build_gamelist_xml(
                platform_id, request=request, platform_dir=platform_dir
            )
            await fs_platform_handler.write_file(
                xml_content.encode("utf-8"), platform_fs_structure, "gamelist.xml"
            )

            log.info(f"Exported gamelist.xml to {platform_fs_structure}/gamelist.xml")
            return True
        except Exception as e:
            log.error(f"Failed to export gamelist.xml for platform {platform_id}: {e}")
            return False
