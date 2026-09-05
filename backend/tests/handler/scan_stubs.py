"""Scaffolding shared by the tests that drive `scan_rom` end to end."""

from typing import Any

from handler.database import db_platform_handler, db_rom_handler
from handler.scan_handler import ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom
from utils.context import initialize_context


def add_n64_platform(**overrides: Any) -> Platform:
    """Persist the N64 platform the scan tests match against."""
    return db_platform_handler.add_platform(
        Platform(id=1, slug="n64", fs_slug="n64", name="Nintendo 64", **overrides)
    )


def add_rom(platform: Platform, fs_name: str, title: str, **overrides: Any) -> Rom:
    """Persist a single-file ROM whose filename tags are already split out."""
    stem, _, extension = fs_name.rpartition(".")
    attrs: dict[str, Any] = {
        "platform_id": platform.id,
        "fs_name": fs_name,
        "fs_name_no_tags": title,
        "fs_name_no_ext": stem,
        "fs_extension": extension,
        "fs_path": platform.fs_slug,
        "name": title,
        "fs_size_bytes": 1024,
        "tags": [],
    }
    return db_rom_handler.add_rom(Rom(**{**attrs, **overrides}))


async def run_scan(
    platform: Platform,
    rom: Rom,
    *,
    scan_type: ScanType,
    metadata_sources: list[str],
) -> Rom:
    """Scan `rom` with no files on disk, so only the name-based lookups run."""
    async with initialize_context():
        return await scan_rom(
            platform=platform,
            scan_type=scan_type,
            rom=rom,
            fs_rom={
                "fs_name": rom.fs_name,
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=metadata_sources,
            newly_added=False,
        )
