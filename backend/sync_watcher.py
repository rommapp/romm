"""Sync folder watcher for File Transfer mode.

This module is invoked by watchfiles when changes are detected in the sync
folder. It processes incoming save files from devices that use file_transfer
sync mode.

The watcher is configured to run as a separate watchfiles process monitoring
the sync base path. When files appear in a device's incoming/ directory, they
are matched to ROMs and processed as save uploads.
"""

import asyncio
import json
import os
import shutil
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import cast

import sentry_sdk

from config import ENABLE_SYNC_FOLDER_WATCHER, SENTRY_DSN
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_platform_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.filesystem import fs_asset_handler, fs_sync_handler
from handler.sync.comparison import compare_save_state
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import SyncMode
from models.sync_session import SyncSessionStatus
from utils import get_version

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

Change = tuple[str, str]


def _extract_device_and_platform(path: str) -> tuple[str, str, str] | None:
    """Extract device_id, platform_slug, and filename from a sync incoming path.

    Expected path format: {SYNC_BASE_PATH}/{device_id}/incoming/{platform_slug}/filename.ext
    """
    try:
        rel_path = os.path.relpath(path, start=str(fs_sync_handler.base_path))
        parts = rel_path.split(os.sep)
        if len(parts) < 4 or parts[1] != "incoming":
            return None
        device_id = parts[0]
        platform_slug = parts[2]
        filename = parts[-1]
        return (device_id, platform_slug, filename)
    except (ValueError, IndexError):
        return None


def _ensure_conflicts_dir(device_id: str, platform_slug: str) -> str:
    conflicts_dir = str(
        fs_sync_handler.base_path
        / fs_sync_handler.build_conflicts_path(device_id, platform_slug)
    )
    os.makedirs(conflicts_dir, exist_ok=True)
    return conflicts_dir


def process_sync_changes(changes: Sequence[Change]) -> None:
    """Process file changes detected in the sync folder."""
    if not ENABLE_SYNC_FOLDER_WATCHER:
        return

    # Only process added/modified files in incoming directories
    added_files: list[tuple[str, str, str, str]] = (
        []
    )  # (device_id, platform_slug, filename, full_path)
    for _event_type, change_path in changes:
        src_path = os.fsdecode(change_path)

        # Only process files (not directories)
        if not os.path.isfile(src_path):
            continue

        parsed = _extract_device_and_platform(src_path)
        if not parsed:
            continue

        device_id, platform_slug, filename = parsed
        added_files.append((device_id, platform_slug, filename, src_path))

    if not added_files:
        return

    # Group by device
    by_device: dict[str, list[tuple[str, str, str]]] = {}
    for device_id, platform_slug, filename, full_path in added_files:
        by_device.setdefault(device_id, []).append((platform_slug, filename, full_path))

    for device_id, files in by_device.items():
        _process_device_incoming(device_id, files)


def _process_device_incoming(
    device_id: str,
    files: list[tuple[str, str, str]],  # (platform_slug, filename, full_path)
) -> None:
    """Process incoming files for a single device."""
    from endpoints.sockets.sync import (
        emit_sync_completed,
        emit_sync_error,
        emit_sync_started,
    )

    # Look up device - try all users since file transfer is server-side
    device = db_device_handler.get_device_by_id(device_id)
    if not device:
        log.warning(f"Sync watcher: unknown device {device_id}, skipping")
        return

    if device.sync_mode != SyncMode.FILE_TRANSFER:
        log.warning(
            f"Sync watcher: device {device_id} is not in file_transfer mode, skipping"
        )
        return

    if not device.sync_enabled:
        log.info(f"Sync watcher: device {device_id} sync is disabled, skipping")
        return

    # Create a sync session
    sync_session = db_sync_session_handler.create_session(
        device_id=device.id, user_id=device.user_id
    )
    db_sync_session_handler.update_session(
        session_id=sync_session.id,
        data={
            "status": SyncSessionStatus.IN_PROGRESS,
            "operations_planned": len(files),
        },
    )

    asyncio.run(
        emit_sync_started(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            sync_mode="file_transfer",
        )
    )

    completed = 0
    failed = 0

    for platform_slug, filename, full_path in files:
        try:
            _process_incoming_file(
                device, sync_session.id, platform_slug, filename, full_path
            )
            completed += 1
        except Exception:
            log.error(
                f"Sync watcher: failed to process {filename} for device {device_id}",
                exc_info=True,
            )
            failed += 1

    # Complete the session
    db_sync_session_handler.complete_session(
        session_id=sync_session.id,
        operations_completed=completed,
        operations_failed=failed,
    )

    if failed > 0:
        asyncio.run(
            emit_sync_error(
                user_id=device.user_id,
                device_id=device.id,
                session_id=sync_session.id,
                error_message=f"{failed} file(s) failed to process",
            )
        )

    asyncio.run(
        emit_sync_completed(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            operations_completed=completed,
            operations_failed=failed,
        )
    )

    log.info(
        f"Sync watcher: device {device_id} processed {completed} files, {failed} failures"
    )


def _process_incoming_file(
    device, session_id: int, platform_slug: str, filename: str, full_path: str
) -> None:
    """Process a single incoming file from a device's sync folder."""
    from endpoints.sockets.sync import emit_sync_conflict

    # Look up platform
    platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
    if not platform:
        log.warning(f"Sync watcher: unknown platform slug {platform_slug}")
        return

    # Compute hash of incoming file
    file_hash = fs_sync_handler.compute_file_hash(full_path)
    file_size = os.path.getsize(full_path)
    file_mtime = datetime.fromtimestamp(os.path.getmtime(full_path), tz=timezone.utc)

    # Try to find matching saves on this platform for this user
    saves_on_platform = db_save_handler.get_saves(
        user_id=device.user_id,
        platform_id=platform.id,
    )

    matched_save = None
    for save in saves_on_platform:
        if save.file_name == filename:
            matched_save = save
            break

    if matched_save:
        # Compare with existing save
        device_sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=matched_save.id
        )
        result = compare_save_state(
            client_hash=file_hash,
            client_updated_at=file_mtime,
            server_hash=matched_save.content_hash,
            server_updated_at=matched_save.updated_at,
            device_last_synced_at=device_sync.last_synced_at if device_sync else None,
        )

        if result.action == "no_op":
            log.debug(f"Sync watcher: {filename} is already in sync, skipping")
            fs_sync_handler.remove_incoming_file(full_path)
            return

        if result.action == "upload":
            # Client file is newer - update server save
            log.info(
                f"Sync watcher: updating save {hl(filename)} from device {device.id}"
            )
            with open(full_path, "rb") as f:
                file_data = f.read()
            asyncio.run(
                fs_asset_handler.write_file(
                    file=file_data,
                    path=matched_save.file_path,
                    filename=matched_save.file_name,
                )
            )
            db_save_handler.update_save(
                matched_save.id,
                {
                    "file_size_bytes": file_size,
                    "content_hash": file_hash,
                },
            )
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=matched_save.id,
                synced_at=datetime.now(timezone.utc),
            )
            fs_sync_handler.remove_incoming_file(full_path)

        elif result.action == "conflict":
            log.warning(
                f"Sync watcher: conflict detected for {filename} "
                f"on device {device.id}: {result.reason}"
            )
            # Move conflicting file to conflicts directory
            conflicts_dir = _ensure_conflicts_dir(device.id, platform_slug)
            conflict_path = os.path.join(conflicts_dir, filename)
            shutil.move(full_path, conflict_path)
            log.info(f"Sync watcher: moved conflicting file to {conflict_path}")

            # Emit socket notification for conflict
            asyncio.run(
                emit_sync_conflict(
                    user_id=device.user_id,
                    device_id=device.id,
                    session_id=session_id,
                    file_name=filename,
                    rom_id=matched_save.rom_id,
                    reason=result.reason,
                )
            )

        elif result.action == "download":
            # Server is newer - write server save to device's outgoing directory
            log.info(
                f"Sync watcher: server save is newer for {filename}, "
                f"writing to outgoing"
            )
            server_file_path = f"{matched_save.file_path}/{matched_save.file_name}"
            server_full_path = fs_asset_handler.validate_path(server_file_path)
            with open(str(server_full_path), "rb") as f:
                server_data = f.read()
            fs_sync_handler.write_outgoing_file(
                device_id=device.id,
                platform_slug=platform_slug,
                file_name=filename,
                data=server_data,
            )
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=matched_save.id,
                synced_at=datetime.now(timezone.utc),
            )
            fs_sync_handler.remove_incoming_file(full_path)
    else:
        log.info(
            f"Sync watcher: new file {hl(filename)} from device {device.id} "
            f"on platform {platform_slug} - no matching save found, skipping"
        )


if __name__ == "__main__":
    changes = cast(list[Change], json.loads(os.getenv("WATCHFILES_CHANGES", "[]")))
    if changes:
        process_sync_changes(changes)
