"""Keeps legacy slot uploads and snapshot pushes on one line per channel."""

import zipfile

from handler.database import (
    db_save_handler,
    db_screenshot_handler,
    db_snapshot_handler,
)
from handler.filesystem import fs_asset_handler
from handler.snapshots.file_key import FileKey
from handler.snapshots.legacy import may_load
from handler.snapshots.manifest import Manifest, SaveEntry
from handler.snapshots.write import (
    ChannelTarget,
    SnapshotWrite,
    SnapshotWriteError,
    write_snapshot,
)
from logger.logger import log
from models.assets import Save, SaveFormat, SaveShape
from models.rom import Rom
from models.user import User


async def hold_legacy_upload(
    save: Save, user: User, rom: Rom, device_id: str | None
) -> None:
    """Make a legacy slot upload the current of its channel when a snapshot
    client keeps that channel, carrying the current's states forward.

    A hardcore channel, a neutral current save, or a current the upload's core
    or emulator rules out (`may_load`) keeps the upload as a legacy save: the
    legacy API can neither approve a downgrade nor send the neutral form, and
    another core's files may not load.
    """
    if save.channel_id is None or not save.content_hash:
        return
    channel = db_snapshot_handler.get_channel(save.channel_id)
    if channel is None or channel.current_snapshot_id is None or channel.is_hardcore:
        return
    current = db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
    if current is None:
        return
    held = db_snapshot_handler.get_stored_content(current).save
    if held is not None and (
        held.format == SaveFormat.NEUTRAL
        or not may_load(held, [save.emulator], [save.core])
    ):
        return
    channel_key = FileKey.of_channel(channel)
    rom_file = next(
        (f for f in rom.files if channel_key.matches(FileKey.of_file(f))), None
    )
    if rom_file is None:
        return

    path = fs_asset_handler.validate_path(save.full_path)
    shape = SaveShape.MULTI if zipfile.is_zipfile(path) else SaveShape.SINGLE
    save = db_save_handler.update_save(
        save.id,
        {
            "shape": shape,
            "format": SaveFormat.NATIVE,
            "identity_hash": save.content_hash,
        },
        touch=False,
    )
    # Legacy uploads match their screenshot by file name; snapshots look it up by row.
    shot = save.screenshot
    if shot is not None and shot.save_id is None and shot.state_id is None:
        db_screenshot_handler.update_screenshot(shot.id, {"save_id": save.id})
    try:
        await write_snapshot(
            SnapshotWrite(
                author=user,
                rom=rom,
                rom_file=rom_file,
                manifest=Manifest(
                    save=SaveEntry(
                        hash=save.content_hash or "",
                        shape=shape,
                        format=SaveFormat.NATIVE,
                    ),
                    emulator=save.emulator,
                ),
                channel=ChannelTarget(expected_current_id=current.id, id=channel.id),
                device_id=device_id,
                adopt_save=save,
            )
        )
    except SnapshotWriteError as exc:
        log.warning(f"Kept legacy save {save.id} out of channel {channel.id}: {exc}")
