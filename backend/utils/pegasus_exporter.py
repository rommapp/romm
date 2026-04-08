import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request

from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_platform_handler, fs_resource_handler
from logger.logger import log
from models.rom import Rom

# Map Pegasus asset keys to subdirectory names inside assets/
ASSET_DIRS: dict[str, str] = {
    "box_front": "covers",
    "box_back": "backcovers",
    "box_full": "boxes",
    "screenshot": "screenshots",
    "titlescreen": "titlescreens",
    "video": "videos",
    "marquee": "marquees",
    "cartridge": "cartridges",
    "logo": "logos",
    "background": "backgrounds",
    "bezel": "bezels",
}


class PegasusExporter:
    """Export RomM collections to Pegasus Frontend metadata.pegasus.txt format"""

    def __init__(self, local_export: bool = False):
        self.local_export = local_export

    def _format_release_date(self, timestamp: int) -> str:
        """Format release date to YYYY-MM-DD format"""
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime("%Y-%m-%d")

    def _format_rating(self, average_rating: float) -> str:
        """Format rating as percentage (0-100%). Input is on 0-10 scale."""
        clamped_rating = max(0, min(100, average_rating))
        return f"{int(clamped_rating)}%"

    def _escape_multiline(self, text: str) -> str:
        """Indent continuation lines for multi-line values in Pegasus format"""
        lines = text.strip().splitlines()
        if len(lines) <= 1:
            return text.strip()
        return (
            lines[0]
            + "\n"
            + "\n".join(f"  {line}" if line.strip() else "  ." for line in lines[1:])
        )

    def _collect_assets(self, rom: Rom) -> dict[str, Path]:
        """Collect available media assets for a ROM using model properties.

        Returns a dict mapping Pegasus asset key to the absolute source file path.
        """
        assets: dict[str, Path] = {}

        if rom.path_cover_l:
            assets["box_front"] = fs_resource_handler.validate_path(rom.path_cover_l)

        if rom.path_screenshots:
            assets["screenshot"] = fs_resource_handler.validate_path(
                rom.path_screenshots[0]
            )

        if rom.path_video:
            assets["video"] = fs_resource_handler.validate_path(rom.path_video)

        # Extended media from screenscraper / gamelist metadata
        ss = rom.ss_metadata or {}
        gl = rom.gamelist_metadata or {}

        extended: dict[str, list[str]] = {
            "box_full": [ss.get("box3d_path", ""), gl.get("box3d_path", "")],
            "box_back": [ss.get("box2d_back_path", ""), gl.get("box2d_back_path", "")],
            "logo": [ss.get("logo_path", "")],
            "marquee": [gl.get("marquee_path", "")],
            "cartridge": [ss.get("physical_path", ""), gl.get("physical_path", "")],
            "background": [ss.get("fanart_path", ""), gl.get("fanart_path", "")],
            "titlescreen": [
                ss.get("title_screen_path", ""),
                gl.get("title_screen_path", ""),
            ],
            "bezel": [ss.get("bezel_path", "")],
        }

        for pegasus_key, candidates in extended.items():
            if pegasus_key in assets:
                continue
            for candidate in candidates:
                if candidate:
                    assets[pegasus_key] = fs_resource_handler.validate_path(candidate)
                    break

        return assets

    def _create_game_entry(
        self,
        rom: Rom,
        request: Request | None,
        exported_assets: dict[str, str] | None = None,
    ) -> str:
        """Create a game entry for a ROM in Pegasus metadata format"""
        lines: list[str] = []

        # Game title (required)
        lines.append(f"game: {rom.name or rom.fs_name}")

        # File path
        if self.local_export:
            lines.append(f"file: {rom.fs_name}")
        else:
            if request is None:
                raise ValueError(
                    "Request object must be provided for non-local exports"
                )
            lines.append(
                f"file: {request.url_for('get_rom_content', id=rom.id, file_name=rom.fs_name)}"
            )

        # Sort title (use fs_name_no_tags if different from name)
        if rom.name and rom.fs_name_no_tags and rom.name != rom.fs_name_no_tags:
            lines.append(f"sort-by: {rom.fs_name_no_tags}")

        # Developers and publishers
        if rom.metadatum and rom.metadatum.companies:
            if len(rom.metadatum.companies) > 0:
                lines.append(f"developer: {rom.metadatum.companies[0]}")
            if len(rom.metadatum.companies) > 1:
                lines.append(f"publisher: {rom.metadatum.companies[1]}")

        # Genres
        if rom.metadatum and rom.metadatum.genres:
            for genre in rom.metadatum.genres:
                lines.append(f"genre: {genre}")

        # Tags (rom tags like region, language info)
        if rom.tags:
            for tag in rom.tags:
                lines.append(f"tag: {tag}")

        # Player count
        if rom.metadatum and rom.metadatum.player_count:
            lines.append(f"players: {rom.metadatum.player_count}")

        # Summary / description
        if rom.summary:
            lines.append(f"description: {self._escape_multiline(rom.summary)}")

        # Release date
        if rom.metadatum and rom.metadatum.first_release_date is not None:
            lines.append(
                f"release: {self._format_release_date(rom.metadatum.first_release_date)}"
            )

        # Rating
        if rom.metadatum and rom.metadatum.average_rating is not None:
            lines.append(f"rating: {self._format_rating(rom.metadatum.average_rating)}")

        # Asset references (relative paths to asset files)
        if exported_assets:
            for asset_key, rel_path in exported_assets.items():
                lines.append(f"assets.{asset_key}: {rel_path}")

        # RomM-specific extensions (x-* fields)
        if rom.regions:
            lines.append(f"x-region: {', '.join(rom.regions)}")

        if rom.languages:
            lines.append(f"x-language: {', '.join(rom.languages)}")

        lines.append(f"x-romm-id: {rom.id}")

        return "\n".join(lines)

    def _copy_asset(self, source: Path, dest: Path) -> bool:
        """Copy a file from source to dest using raw read/write. Returns True on success."""
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

    def export_platform_to_pegasus(
        self, platform_id: int, request: Request | None
    ) -> str:
        """Export a platform's ROMs to metadata.pegasus.txt format

        Args:
            platform_id: Platform ID to export
            request: FastAPI request object for URL generation

        Returns:
            String content in Pegasus metadata format
        """
        platform = db_platform_handler.get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform with ID {platform_id} not found")

        roms = db_rom_handler.get_roms_scalar(platform_ids=[platform_id])

        lines: list[str] = []

        # Collection header
        lines.append(f"collection: {platform.custom_name or platform.name}")
        lines.append(f"shortname: {platform.slug}")
        lines.append("")

        # Game entries
        game_count = 0
        for rom in roms:
            if not rom.missing_from_fs:
                if game_count > 0:
                    lines.append("")
                lines.append(self._create_game_entry(rom, request=request))
                game_count += 1

        log.info(f"Exported {game_count} ROMs for platform {platform.name}")
        return "\n".join(lines) + "\n"

    async def export_platform_to_file(
        self,
        platform_id: int,
        request: Request | None,
    ) -> bool:
        """Export platform ROMs to metadata.pegasus.txt file in the platform's directory,
        including media assets copied into a local assets/ folder.

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
            platform_dir = fs_platform_handler.base_path / platform_fs_structure

            roms = db_rom_handler.get_roms_scalar(platform_ids=[platform_id])

            lines: list[str] = []

            # Collection header
            lines.append(f"collection: {platform.custom_name or platform.name}")
            lines.append(f"shortname: {platform.slug}")
            lines.append("")

            game_count = 0
            for rom in roms:
                if rom.missing_from_fs:
                    continue

                exported_assets: dict[str, str] = {}

                if self.local_export:
                    assets = self._collect_assets(rom)

                    for asset_key, source_path in assets.items():
                        subdir = ASSET_DIRS.get(asset_key, asset_key)
                        dest_name = f"{rom.fs_name_no_ext}{source_path.suffix}"
                        dest_path = platform_dir / "assets" / subdir / dest_name

                        if self._copy_asset(source_path, dest_path):
                            exported_assets[asset_key] = f"assets/{subdir}/{dest_name}"

                if game_count > 0:
                    lines.append("")

                lines.append(
                    self._create_game_entry(
                        rom,
                        request=request,
                        exported_assets=exported_assets if exported_assets else None,
                    )
                )
                game_count += 1

            content = "\n".join(lines) + "\n"
            await fs_platform_handler.write_file(
                content.encode("utf-8"),
                platform_fs_structure,
                "metadata.pegasus.txt",
            )

            log.info(
                f"Exported metadata.pegasus.txt with {game_count} ROMs for platform {platform.name}"
            )
            return True
        except Exception as e:
            log.error(
                f"Failed to export metadata.pegasus.txt for platform {platform_id}: {e}"
            )
            return False
