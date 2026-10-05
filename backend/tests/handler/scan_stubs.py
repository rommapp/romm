"""Scaffolding shared by the tests that drive `scan_rom` end to end."""

import os
from typing import Any

from tests.factories import make_platform, make_rom

from handler.scan_handler import ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom
from utils.context import initialize_context


def add_n64_platform(**overrides: Any) -> Platform:
    """Persist the N64 platform the scan tests match against."""
    return make_platform("n64", id=1, name="Nintendo 64", **overrides)


def add_rom(platform: Platform, fs_name: str, title: str, **overrides: Any) -> Rom:
    """Persist a single-file ROM whose filename tags are already split out."""
    stem, extension = os.path.splitext(fs_name)
    attrs: dict[str, Any] = {
        "fs_name_no_tags": title,
        "fs_path": platform.fs_slug,
        "fs_size_bytes": 1024,
        "tags": [],
    }
    return make_rom(
        platform,
        title,
        fs_stem=stem,
        fs_extension=extension.removeprefix("."),
        **(attrs | overrides),
    )


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
                "fs_path": rom.fs_path,
                "flat": True,
                "files": [],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=metadata_sources,
            newly_added=False,
        )
