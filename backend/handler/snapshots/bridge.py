"""Keeps legacy slot uploads and snapshot pushes on one line per channel."""

from handler.database import (
    db_save_handler,
    db_screenshot_handler,
    db_snapshot_handler,
)
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import save_shape_of
from handler.snapshots.hashing import identity_hash_of_file
from handler.snapshots.legacy import may_load
from handler.snapshots.manifest import Manifest, SaveEntry
from handler.snapshots.write import (
    ChannelTarget,
    SnapshotWrite,
    SnapshotWriteError,
    write_snapshot,
)
from logger.logger import log
from models.assets import Save, SaveFormat
from models.rom import Rom
from models.user import User


async def hold_legacy_upload(
    save: Save, user: User, rom: Rom, device_id: str | None
) -> None:
    """Make a legacy slot upload its channel's current, carrying the states
    forward. A hardcore channel, a neutral current, or one `may_load` rules out
    keeps the upload as a legacy save, since the legacy API cannot resolve them."""
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
    rom_file = db_snapshot_handler.get_channel_file(channel)
    if rom_file is None:
        return

    path = fs_asset_handler.validate_path(save.full_path)
    save = db_save_handler.update_save(
        save.id,
        {
            "shape": save_shape_of(path),
            "format": SaveFormat.NATIVE,
            "identity_hash": await identity_hash_of_file(path),
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
                        shape=save.shape or save_shape_of(path),
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
