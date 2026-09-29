"""WebSocket events for sync progress notifications.

Emits events:
- sync:started   - when a sync session begins
- sync:progress  - periodic updates during sync
- sync:completed - when a sync session finishes
- sync:conflict  - when a conflict is detected
- sync:error     - when a sync operation fails

Emits go through the write-only manager, so these can be called from RQ
workers (push-pull task, folder watcher), and a failed emit is logged
rather than raised.
"""

from handler.socket_handler import socket_handler


async def emit_sync_started(
    user_id: int,
    device_id: str,
    session_id: int,
    sync_mode: str,
) -> None:
    """Notify that a sync session has started."""
    await socket_handler.emit_to_user(
        user_id,
        "sync:started",
        {
            "device_id": device_id,
            "session_id": session_id,
            "sync_mode": sync_mode,
        },
    )


async def emit_sync_progress(
    user_id: int,
    device_id: str,
    session_id: int,
    operations_completed: int,
    operations_planned: int,
    current_file: str | None = None,
) -> None:
    """Notify sync progress update."""
    await socket_handler.emit_to_user(
        user_id,
        "sync:progress",
        {
            "device_id": device_id,
            "session_id": session_id,
            "operations_completed": operations_completed,
            "operations_planned": operations_planned,
            "current_file": current_file,
        },
    )


async def emit_sync_completed(
    user_id: int,
    device_id: str,
    session_id: int,
    operations_completed: int,
    operations_failed: int,
) -> None:
    """Notify that a sync session has completed."""
    await socket_handler.emit_to_user(
        user_id,
        "sync:completed",
        {
            "device_id": device_id,
            "session_id": session_id,
            "operations_completed": operations_completed,
            "operations_failed": operations_failed,
        },
    )


async def emit_sync_conflict(
    user_id: int,
    device_id: str,
    session_id: int,
    file_name: str,
    rom_id: int,
    rom_name: str,
    reason: str,
) -> None:
    """Notify that a sync conflict was detected."""
    await socket_handler.emit_to_user(
        user_id,
        "sync:conflict",
        {
            "device_id": device_id,
            "session_id": session_id,
            "file_name": file_name,
            "rom_id": rom_id,
            "rom_name": rom_name,
            "reason": reason,
        },
    )


async def emit_sync_error(
    user_id: int,
    device_id: str,
    session_id: int,
    error_message: str,
) -> None:
    """Notify that a sync error occurred."""
    await socket_handler.emit_to_user(
        user_id,
        "sync:error",
        {
            "device_id": device_id,
            "session_id": session_id,
            "error": error_message,
        },
    )
