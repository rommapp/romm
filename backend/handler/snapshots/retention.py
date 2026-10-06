"""Retention: prune snapshots, then remove the files of the rows only they held."""

import uuid
from datetime import datetime, timedelta, timezone

from config import SNAPSHOT_BRANCH_LIFETIME_DAYS, SNAPSHOT_RETENTION
from handler.asset_store import remove_asset_file
from handler.database import db_snapshot_handler
from handler.database.snapshots_handler import ReleasedContent
from logger.logger import log

BRANCH_LIFETIME = timedelta(days=SNAPSHOT_BRANCH_LIFETIME_DAYS)


async def discard_content(released: ReleasedContent) -> None:
    """Remove the files of rows already deleted, logging each one."""
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
    released = db_snapshot_handler.prune_branches(
        datetime.now(timezone.utc) - BRANCH_LIFETIME
    )
    await discard_content(released)
    return len(released.saves) + len(released.states)
