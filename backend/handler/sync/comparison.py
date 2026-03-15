from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple

from utils.datetime import to_utc

SyncAction = Literal["upload", "download", "conflict", "no_op"]


class SyncComparisonResult(NamedTuple):
    action: SyncAction
    reason: str


def compare_save_state(
    *,
    client_hash: str | None,
    client_updated_at: datetime,
    server_hash: str | None,
    server_updated_at: datetime,
    device_last_synced_at: datetime | None,
) -> SyncComparisonResult:
    """Compare client and server save state to determine the sync action.

    Returns a (action, reason) tuple where action is one of:
    - upload: client save should be uploaded to server
    - download: server save should be downloaded to client
    - conflict: both sides changed, needs resolution
    - no_op: saves are in sync
    """
    client_ts = to_utc(client_updated_at)
    server_ts = to_utc(server_updated_at)

    # If hashes match, saves are identical
    if client_hash and server_hash and client_hash == server_hash:
        return SyncComparisonResult("no_op", "Content is identical")

    # If we have a last sync timestamp, use it to determine which side changed
    if device_last_synced_at:
        synced_ts = to_utc(device_last_synced_at)
        client_changed = client_ts > synced_ts
        server_changed = server_ts > synced_ts

        if client_changed and server_changed:
            return SyncComparisonResult(
                "conflict", "Both sides changed since last sync"
            )

        if client_changed:
            return SyncComparisonResult("upload", "Client save is newer than last sync")

        if server_changed:
            return SyncComparisonResult(
                "download", "Server save is newer than last sync"
            )

        return SyncComparisonResult("no_op", "No changes since last sync")

    # No sync history: fall back to timestamp comparison
    if client_ts > server_ts:
        return SyncComparisonResult("upload", "Client save is newer (no sync history)")

    if server_ts > client_ts:
        return SyncComparisonResult(
            "download", "Server save is newer (no sync history)"
        )

    # Same timestamp, different hashes (or missing hashes)
    if client_hash != server_hash:
        return SyncComparisonResult("conflict", "Same timestamp but different content")

    return SyncComparisonResult("no_op", "Saves appear identical")
