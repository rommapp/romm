from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Literal, NamedTuple, Protocol

from utils.datetime import to_utc

SyncAction = Literal["upload", "download", "conflict", "no_op", "delete"]


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
    device_last_sync_hash: str | None = None,
    device_last_sync_server_hash: str | None = None,
    removed_at: Mapping[str, datetime] | None = None,
) -> SyncComparisonResult:
    """Compare client and server save state to determine the sync action.

    `removed_at` maps versions the server's slot lost to when they were lost, so
    a client still holding one from before then is behind the server.

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

    if _held_since_removal(client_hash, client_ts, removed_at):
        return SyncComparisonResult(
            "download", "Client holds a version removed on the server"
        )

    # If we have a last sync timestamp, use it to determine which side changed
    if device_last_synced_at:
        synced_ts = to_utc(device_last_synced_at)
        # A baseline match proves a side is unchanged; a mismatch proves nothing,
        # so baselines can only ever remove a conflict, never create one.
        client_unchanged = bool(
            client_hash
            and device_last_sync_hash
            and client_hash == device_last_sync_hash
        )
        server_unchanged = bool(
            server_hash
            and device_last_sync_server_hash
            and server_hash == device_last_sync_server_hash
        )
        client_changed = client_ts > synced_ts and not client_unchanged
        server_changed = server_ts > synced_ts and not server_unchanged

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


def compare_missing_server_save(
    client_hash: str | None,
    client_updated_at: datetime,
    removed_at: Mapping[str, datetime],
) -> SyncComparisonResult:
    """Decide a client save whose slot has no server save, matched by identity.

    Args:
        client_hash: The digest the client reported, when it reported one.
        client_updated_at: When the client last wrote its copy.
        removed_at: What the slot is known to have lost, and when.

    Returns:
        `delete` when the client holds a version the slot lost since the client
        wrote it, else `upload`.
    """
    if _held_since_removal(client_hash, to_utc(client_updated_at), removed_at):
        return SyncComparisonResult("delete", "Save was deleted on the server")
    return SyncComparisonResult("upload", "Save exists on client but not on server")


def _held_since_removal(
    client_hash: str | None,
    client_ts: datetime,
    removed_at: Mapping[str, datetime] | None,
) -> bool:
    """Whether the client's copy is a removed version it wrote before the removal."""
    # Written after the removal, the same bytes are progress made on the device.
    removed = (removed_at or {}).get(client_hash) if client_hash else None
    return removed is not None and client_ts <= to_utc(removed)


class _SlotVersion(Protocol):
    @property
    def rom_id(self) -> int: ...

    @property
    def slot(self) -> str | None: ...

    @property
    def content_hash(self) -> str | None: ...


def roms_to_check_for_removals(
    client_saves: Iterable[_SlotVersion],
    current: Mapping[tuple[int, str | None], _SlotVersion],
) -> set[int]:
    """ROMs whose slotted client saves differ from the current version, so may hold a lost one."""
    return {
        save.rom_id
        for save in client_saves
        if save.slot
        and (
            (version := current.get((save.rom_id, save.slot))) is None
            or version.content_hash != save.content_hash
        )
    }
