import os
import stat
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from config import FRONTEND_RESOURCES_PATH
from config.config_manager import MetadataMediaType
from handler.filesystem import fs_resource_handler
from handler.scan_handler import MEDIA_PROVIDERS
from models.rom import Rom, RomFile
from utils.media_types import is_allowed_image_file, is_allowed_video_file

# Sources beside the metadata providers: RomM's own cover, manual and
# screenshot slots, and media files sitting next to the rom in the library.
ROMM_MEDIA_SOURCE = "romm"
LIBRARY_MEDIA_SOURCE = "library"


@dataclass(frozen=True)
class RomMedia:
    """A stored media file of a rom, as a client copying it needs it."""

    type: str
    source: str
    path: str
    size_bytes: int
    format: str | None
    disc: int | None = None
    index: int | None = None
    file_id: int | None = None
    md5: str | None = None
    shadowed: bool = False


def _file_format(name: str) -> str | None:
    return os.path.splitext(name)[1].lstrip(".").lower() or None


def _stored_size(relative_path: str, resolve: Callable[[str], Path]) -> int | None:
    try:
        st = os.stat(resolve(relative_path))
    except (OSError, ValueError):
        return None
    return st.st_size if stat.S_ISREG(st.st_mode) else None


def _resource_media(
    media_type: str,
    source: str,
    relative_path: str,
    resolve: Callable[[str], Path],
    **fields: Any,
) -> RomMedia | None:
    size = _stored_size(relative_path, resolve)
    if size is None:
        return None
    return RomMedia(
        type=media_type,
        source=source,
        path=f"{FRONTEND_RESOURCES_PATH}/{relative_path}",
        size_bytes=size,
        format=_file_format(relative_path),
        **fields,
    )


def _resources(rom: Rom, resolve: Callable[[str], Path]) -> list[RomMedia]:
    slots = [
        _resource_media(media_type, ROMM_MEDIA_SOURCE, path, resolve)
        for media_type, path in (
            ("cover_large", rom.path_cover_l),
            ("cover_small", rom.path_cover_s),
            (MetadataMediaType.MANUAL.value, rom.path_manual),
        )
        if path
    ]
    slots += [
        _resource_media(
            MetadataMediaType.SCREENSHOT.value,
            ROMM_MEDIA_SOURCE,
            path,
            resolve,
            index=i,
        )
        for i, path in enumerate(rom.path_screenshots or [])
        if path
    ]
    resources = [media for media in slots if media]

    claimed_paths: set[str] = set()
    resolved: set[tuple[MetadataMediaType, int | None]] = set()
    for column, source, _ in MEDIA_PROVIDERS:
        metadata: dict[str, Any] = getattr(rom, column) or {}
        for media in fs_resource_handler.recorded_media(metadata, MetadataMediaType):
            # A shared path holds the file of the first provider recording it.
            if media.path in claimed_paths:
                continue
            claimed_paths.add(media.path)
            is_main = media.owner is metadata
            disc = (
                metadata.get(f"{media.media_type.value}_disc")
                if is_main
                else media.owner.get("disc")
            )
            # A provider's main file competes with the others' main files
            # whatever disc it shows, so SS disc 1 outranks an undisced gamelist.
            slot = (media.media_type, None if is_main else disc)
            stored = _resource_media(
                media.media_type.value,
                source,
                media.path,
                resolve,
                disc=disc,
                shadowed=slot in resolved,
            )
            # Only a copy on disk can hide the lower-priority ones.
            if stored:
                resources.append(stored)
                resolved.add(slot)
    return resources


def describe_rom_media(
    rom: Rom,
    files: Sequence[RomFile],
    resolve: Callable[[str], Path] | None = None,
) -> list[RomMedia]:
    """Every media file of a rom on disk, highest priority first per kind and disc.

    Args:
        rom: The rom, holding its cover, manual, screenshot and provider paths.
        files: The rom's files; top-level images and videos count as media.
        resolve: A ``lexical_path_validator`` to share across a page of roms.

    Returns:
        One entry per stored file; a copy a higher-priority source hides is
        ``shadowed``, and a recorded path whose file is gone is left out.
    """
    resolve = resolve or fs_resource_handler.lexical_path_validator()
    media = _resources(rom, resolve)

    for file in files:
        if not file.is_top_level or file.missing_from_fs:
            continue
        if is_allowed_image_file(file.file_name):
            media_type = "image"
        elif is_allowed_video_file(file.file_name):
            media_type = "video"
        else:
            continue
        media.append(
            RomMedia(
                type=media_type,
                source=LIBRARY_MEDIA_SOURCE,
                path=f"/api/roms/{file.id}/files/content/{quote(file.file_name)}",
                size_bytes=file.file_size_bytes,
                format=_file_format(file.file_name),
                file_id=file.id,
                md5=file.md5_hash,
            )
        )
    return media
