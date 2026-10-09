"""Retention: prune snapshots, then remove the files of the rows only they held."""

import uuid
from datetime import datetime, timedelta, timezone

from config import SNAPSHOT_BRANCH_LIFETIME_DAYS, SNAPSHOT_RETENTION
from handler.asset_store import remove_asset_file
from handler.database import db_deleted_asset_handler, db_snapshot_handler
from handler.database.snapshots_handler import ReleasedContent
from logger.logger import log

BRANCH_LIFETIME = timedelta(days=SNAPSHOT_BRANCH_LIFETIME_DAYS)


def _record_slot_losses(released: ReleasedContent) -> None:
    """Record the slotted versions the deletion took, so negotiate never offers
    them back."""
    losses: dict[tuple[int, int, str], list[str]] = {}
    for save in sorted(released.saves, key=lambda s: s.id):
        if save.slot and save.content_hash and save.rom_id is not None:
            losses.setdefault((save.user_id, save.rom_id, save.slot), []).append(
                save.content_hash
            )
    for (user_id, rom_id, slot), hashes in sorted(losses.items()):
        db_deleted_asset_handler.record_deletions(user_id, rom_id, slot, hashes)


async def discard_content(released: ReleasedContent) -> None:
    """Record the slot losses of rows already deleted, then remove their files."""
    _record_slot_losses(released)
    for row in [*released.saves, *released.states]:
        log.info(
            f"Removed {type(row).__name__.lower()} {row.id} "
            f"{row.full_path} {row.content_hash}"
        )
        await remove_asset_file(row.full_path, "Snapshot content")
    for shot in released.screenshots:
        await remove_asset_file(shot.full_path, "Snapshot screenshot")


async def prune(channel_id: uuid.UUID) -> None:
    """Apply the channel's retention limit after a push."""
    await discard_content(
        db_snapshot_handler.prune_channel(channel_id, keep=SNAPSHOT_RETENTION)
    )


async def prune_branches() -> int:
    """Drop branches older than `BRANCH_LIFETIME`.

    Returns:
        How many content rows went with them.
    """
    return await _discard_counted(
        db_snapshot_handler.prune_branches(datetime.now(timezone.utc) - BRANCH_LIFETIME)
    )


async def prune_unreachable() -> int:
    """Drop archival snapshots that lost their ROM and carry no hash to find it by.

    Returns:
        How many content rows went with them.
    """
    return await _discard_counted(db_snapshot_handler.prune_unreachable_archival())


async def _discard_counted(released: ReleasedContent) -> int:
    await discard_content(released)
    return len(released.saves) + len(released.states)
