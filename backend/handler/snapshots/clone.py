"""Copying an existing save into a snapshot, without the client sending its bytes."""

import asyncio
import zipfile

from handler.filesystem import fs_asset_handler
from handler.snapshots.manifest import SaveEntry
from handler.snapshots.write import UploadPart
from models.assets import Save, SaveFormat, SaveShape
from utils.uploads import DATETIME_TAG_PATTERN


def _untagged(file_name: str) -> str:
    """The name the save carried before the server tagged it with its upload time."""
    stem, dot, extension = file_name.rpartition(".")
    if not dot:
        return DATETIME_TAG_PATTERN.sub("", file_name)
    return f"{DATETIME_TAG_PATTERN.sub('', stem)}.{extension}"


async def copy_part(
    save: Save, shape: SaveShape | None, format: SaveFormat | None
) -> tuple[SaveEntry, UploadPart]:
    """A push part holding a copy of `save`, with its screenshot.

    The copy becomes a new row, so a legacy writer that overwrites `save` in
    place never touches the snapshot's bytes.
    """
    path = fs_asset_handler.validate_path(save.full_path)
    content = await asyncio.to_thread(path.read_bytes)
    content_hash = await fs_asset_handler.compute_content_hash(save.full_path)
    if content_hash is None:
        raise FileNotFoundError(save.full_path)
    is_zip = await asyncio.to_thread(zipfile.is_zipfile, path)

    screenshot = save.screenshot
    shot_bytes = None
    shot_name = None
    if screenshot is not None:
        shot_path = fs_asset_handler.validate_path(screenshot.full_path)
        if shot_path.is_file():
            shot_bytes = await asyncio.to_thread(shot_path.read_bytes)
            shot_name = screenshot.file_name

    entry = SaveEntry(
        hash=content_hash,
        shape=shape or (SaveShape.MULTI if is_zip else SaveShape.SINGLE),
        format=format or SaveFormat.NATIVE,
    )
    part = UploadPart(
        content=content,
        file_name=_untagged(save.file_name),
        screenshot=shot_bytes,
        screenshot_name=shot_name,
    )
    return entry, part
