"""Copying an existing save into a snapshot, without the client sending its bytes."""

import asyncio

from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import save_shape_of
from handler.snapshots.manifest import SaveEntry
from handler.snapshots.write import UploadPart, copied_part
from models.assets import Save, SaveFormat, SaveShape


async def copy_part(
    save: Save, shape: SaveShape | None, format: SaveFormat | None
) -> tuple[SaveEntry, UploadPart]:
    """A push part holding a copy of `save`, with its screenshot.

    The copy becomes a new row, so a legacy writer that overwrites `save` in
    place never touches the snapshot's bytes.
    """
    content_hash = await fs_asset_handler.compute_content_hash(save.full_path)
    if content_hash is None:
        raise FileNotFoundError(save.full_path)
    path = fs_asset_handler.validate_path(save.full_path)
    entry = SaveEntry(
        hash=content_hash,
        shape=shape or await asyncio.to_thread(save_shape_of, path),
        format=format or SaveFormat.NATIVE,
    )
    return entry, await copied_part(save)
