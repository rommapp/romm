"""Background task for Push-Pull sync mode.

Connects to devices via SSH/SFTP, scans their save directories,
and performs bidirectional sync operations.
"""

import os
from datetime import datetime, timezone
from typing import Any

from anyio import Path as AnyioPath
from anyio import open_file

from config import ENABLE_SYNC_PUSH_PULL, SYNC_PUSH_PULL_CRON
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_platform_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.filesystem import fs_asset_handler
from handler.sync.comparison import compare_save_state
from handler.sync.ssh_handler import ssh_sync_handler
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import Device, SyncMode
from models.sync_session import SyncSessionStatus
from tasks.tasks import PeriodicTask, TaskType


async def run_push_pull_sync(
    device_id: str | None = None,
    session_id: int | None = None,
    force: bool = False,
) -> dict:
    """Execute push-pull sync for one or all push_pull devices."""
    if not ENABLE_SYNC_PUSH_PULL and not force:
        log.info("Push-pull sync not enabled, skipping")
        return {"status": "disabled"}

    if device_id:
        device = db_device_handler.get_device_by_id(device_id)
        if not device:
            return {"status": "error", "message": f"Device {device_id} not found"}
        devices = [device]
    else:
        devices = list(
            db_device_handler.get_all_devices_by_sync_mode(SyncMode.PUSH_PULL)
        )

    if not devices:
        log.info("No push_pull devices found")
        return {"status": "no_devices"}

    results = []
    for device in devices:
        if not device.sync_enabled:
            continue
        result = await _sync_device(device, session_id=session_id)
        results.append(result)

    return {"status": "completed", "device_results": results}


async def _sync_device(device: Device, session_id: int | None = None) -> dict:
    """Perform push-pull sync for a single device."""
    sync_config = device.sync_config or {}
    if not sync_config.get("ssh_host"):
        log.warning(f"Push-pull device {device.id} has no ssh_host configured")
        return {"device_id": device.id, "status": "error", "message": "No ssh_host"}

    from endpoints.sockets.sync import (
        emit_sync_completed,
        emit_sync_conflict,
        emit_sync_error,
        emit_sync_progress,
        emit_sync_started,
    )

    if session_id:
        sync_session = db_sync_session_handler.get_session(
            session_id=session_id, user_id=device.user_id
        )
        if not sync_session:
            log.warning(
                f"Push-pull: session {session_id} not found, creating new session"
            )
            sync_session = db_sync_session_handler.create_session(
                device_id=device.id, user_id=device.user_id
            )
    else:
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=device.user_id
        )

    await emit_sync_started(
        user_id=device.user_id,
        device_id=device.id,
        session_id=sync_session.id,
        sync_mode="push_pull",
    )

    try:
        conn = await ssh_sync_handler.connect(sync_config, device_id=device.id)
    except Exception as e:
        log.error(f"Push-pull: failed to connect to device {device.id}: {e}")
        db_sync_session_handler.fail_session(
            session_id=sync_session.id, error_message=str(e)
        )
        await emit_sync_error(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            error_message=str(e),
        )
        return {"device_id": device.id, "status": "connection_failed", "error": str(e)}

    completed = 0
    failed = 0

    try:
        save_directories = sync_config.get("save_directories", [])
        if not save_directories:
            log.warning(
                f"Push-pull device {device.id} has no save_directories configured"
            )
            db_sync_session_handler.complete_session(session_id=sync_session.id)
            return {"device_id": device.id, "status": "no_directories"}

        remote_saves = await ssh_sync_handler.list_remote_saves(conn, save_directories)
        log.info(
            f"Push-pull: found {len(remote_saves)} remote saves on device {device.id}"
        )

        db_sync_session_handler.update_session(
            session_id=sync_session.id,
            data={
                "status": SyncSessionStatus.IN_PROGRESS,
                "operations_planned": len(remote_saves),
            },
        )

        operations_planned = len(remote_saves)

        for remote_save in remote_saves:
            try:
                action = await _process_remote_save(device, conn, remote_save)
                if action == "conflict":
                    await emit_sync_conflict(
                        user_id=device.user_id,
                        device_id=device.id,
                        session_id=sync_session.id,
                        file_name=remote_save.file_name,
                        rom_id=0,
                        reason=f"Conflict detected for {remote_save.file_name}",
                    )
                if action != "skipped":
                    completed += 1
            except Exception:
                log.error(
                    f"Push-pull: failed to process {remote_save.file_name} "
                    f"on device {device.id}",
                    exc_info=True,
                )
                failed += 1

            await emit_sync_progress(
                user_id=device.user_id,
                device_id=device.id,
                session_id=sync_session.id,
                operations_completed=completed + failed,
                operations_planned=operations_planned,
                current_file=remote_save.file_name,
            )

        push_count = await _push_missing_saves(
            device, conn, remote_saves, save_directories
        )
        completed += push_count

    except Exception as e:
        log.error(f"Push-pull sync failed for device {device.id}: {e}", exc_info=True)
        db_sync_session_handler.fail_session(
            session_id=sync_session.id, error_message=str(e)
        )
        await emit_sync_error(
            user_id=device.user_id,
            device_id=device.id,
            session_id=sync_session.id,
            error_message=str(e),
        )
        return {"device_id": device.id, "status": "failed", "error": str(e)}
    finally:
        conn.close()

    db_sync_session_handler.complete_session(
        session_id=sync_session.id,
        operations_completed=completed,
        operations_failed=failed,
    )
    db_device_handler.update_last_seen(device_id=device.id, user_id=device.user_id)

    await emit_sync_completed(
        user_id=device.user_id,
        device_id=device.id,
        session_id=sync_session.id,
        operations_completed=completed,
        operations_failed=failed,
    )

    log.info(
        f"Push-pull sync for device {device.id}: "
        f"{completed} completed, {failed} failed"
    )
    return {
        "device_id": device.id,
        "status": "completed",
        "completed": completed,
        "failed": failed,
    }


async def _process_remote_save(
    device: Device,
    conn,
    remote_save,
) -> str:
    """Process a single remote save file. Returns action taken."""
    # Look up platform
    platform = db_platform_handler.get_platform_by_fs_slug(remote_save.platform_slug)
    if not platform:
        log.debug(f"Unknown platform slug: {remote_save.platform_slug}")
        return "skipped"

    # Find matching server save
    saves = db_save_handler.get_saves(user_id=device.user_id, platform_id=platform.id)
    matched_save = None
    for save in saves:
        if save.file_name == remote_save.file_name:
            matched_save = save
            break

    if not matched_save:
        log.info(
            f"Push-pull: remote save {hl(remote_save.file_name)} "
            f"on platform {remote_save.platform_slug} - no matching server save, skipping"
        )
        return "skipped"

    # Compare with existing save
    device_sync = db_device_save_sync_handler.get_sync(
        device_id=device.id, save_id=matched_save.id
    )

    # Download remote file to get its hash
    local_path, remote_hash = await ssh_sync_handler.download_save(
        conn, remote_save.path
    )

    try:
        result = compare_save_state(
            client_hash=remote_hash,
            client_updated_at=remote_save.mtime,
            server_hash=matched_save.content_hash,
            server_updated_at=matched_save.updated_at,
            device_last_synced_at=device_sync.last_synced_at if device_sync else None,
        )

        if result.action == "no_op":
            # Update sync tracking even for no-ops
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=matched_save.id,
                synced_at=datetime.now(timezone.utc),
            )
            return "no_op"

        if result.action == "upload":
            # Remote is newer - pull to server
            log.info(
                f"Push-pull: pulling {hl(remote_save.file_name)} from device {device.id}"
            )
            async with await open_file(local_path, "rb") as f:
                file_data = await f.read()
            await fs_asset_handler.write_file(
                file=file_data,
                path=matched_save.file_path,
                filename=matched_save.file_name,
            )
            db_save_handler.update_save(
                matched_save.id,
                {
                    "file_size_bytes": remote_save.file_size,
                    "content_hash": remote_hash,
                },
            )
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=matched_save.id,
                synced_at=datetime.now(timezone.utc),
            )
            return "pulled"

        if result.action == "download":
            # Server is newer - push to device
            log.info(
                f"Push-pull: pushing {hl(matched_save.file_name)} to device {device.id}"
            )
            server_file_path = f"{matched_save.file_path}/{matched_save.file_name}"
            server_full_path = fs_asset_handler.validate_path(server_file_path)
            await ssh_sync_handler.upload_save(
                conn, str(server_full_path), remote_save.path
            )
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=matched_save.id,
                synced_at=datetime.now(timezone.utc),
            )
            return "pushed"

        if result.action == "conflict":
            log.warning(
                f"Push-pull: conflict for {remote_save.file_name} "
                f"on device {device.id}: {result.reason}"
            )
            return "conflict"

    finally:
        if await AnyioPath(local_path).exists():
            os.unlink(local_path)

    return "skipped"


async def _push_missing_saves(
    device: Device,
    conn,
    remote_saves,
    save_directories: list[dict],
) -> int:
    """Push server saves that are missing from the device."""
    pushed = 0

    # Build set of remote filenames per platform
    remote_files: dict[str, set[str]] = {}
    for rs in remote_saves:
        remote_files.setdefault(rs.platform_slug, set()).add(rs.file_name)

    # Build path lookup from save_directories config
    platform_paths: dict[str, str] = {}
    for dir_config in save_directories:
        platform_paths[dir_config["platform_slug"]] = dir_config["path"]

    # Check server saves for each configured platform
    for dir_config in save_directories:
        platform_slug = dir_config["platform_slug"]
        platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
        if not platform:
            continue

        server_saves = db_save_handler.get_saves(
            user_id=device.user_id, platform_id=platform.id
        )

        remote_set = remote_files.get(platform_slug, set())
        remote_dir = platform_paths.get(platform_slug, "")

        for save in server_saves:
            if save.file_name in remote_set:
                continue

            # Check if device has synced this before (intentional delete)
            device_sync = db_device_save_sync_handler.get_sync(
                device_id=device.id, save_id=save.id
            )
            if device_sync and device_sync.is_untracked:
                continue

            # Push to device
            if remote_dir:
                try:
                    server_file_path = f"{save.file_path}/{save.file_name}"
                    server_full_path = fs_asset_handler.validate_path(server_file_path)
                    remote_path = f"{remote_dir}/{save.file_name}"
                    await ssh_sync_handler.upload_save(
                        conn, str(server_full_path), remote_path
                    )
                    db_device_save_sync_handler.upsert_sync(
                        device_id=device.id,
                        save_id=save.id,
                        synced_at=datetime.now(timezone.utc),
                    )
                    pushed += 1
                    log.info(
                        f"Push-pull: pushed missing save {hl(save.file_name)} "
                        f"to device {device.id}"
                    )
                except Exception:
                    log.error(
                        f"Push-pull: failed to push {save.file_name} to device {device.id}",
                        exc_info=True,
                    )

    return pushed


class SyncPushPullTask(PeriodicTask):
    """Periodic task to run push-pull sync for all configured devices."""

    def __init__(self) -> None:
        super().__init__(
            title="Push-Pull Sync",
            description="Sync saves with devices via SSH/SFTP",
            task_type=TaskType.SYNC,
            enabled=ENABLE_SYNC_PUSH_PULL,
            cron_string=SYNC_PUSH_PULL_CRON,
            func="tasks.sync_push_pull_task.run_push_pull_sync",
        )

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await run_push_pull_sync(**kwargs)


sync_push_pull_task = SyncPushPullTask()
