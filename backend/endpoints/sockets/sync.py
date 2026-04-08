"""WebSocket events for sync progress notifications.

Emits events:
- sync:started   - when a sync session begins
- sync:progress  - periodic updates during sync
- sync:completed - when a sync session finishes
- sync:conflict  - when a conflict is detected
- sync:error     - when a sync operation fails

Uses AsyncRedisManager in write-only mode so these can be called from
RQ background workers (push-pull task, folder watcher) that don't have
access to the main socket server instance.
"""

import socketio  # type: ignore

from config import REDIS_URL


def _get_socket_manager() -> socketio.AsyncRedisManager:
    """Create a write-only Redis manager for emitting from background tasks."""
    return socketio.AsyncRedisManager(REDIS_URL, write_only=True)


async def emit_sync_started(
    user_id: int,
    device_id: str,
    session_id: int,
    sync_mode: str,
) -> None:
    """Notify that a sync session has started."""
    sm = _get_socket_manager()
    await sm.emit(
        "sync:started",
        {
            "device_id": device_id,
            "session_id": session_id,
            "sync_mode": sync_mode,
        },
        room=f"user:{user_id}",
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
    sm = _get_socket_manager()
    await sm.emit(
        "sync:progress",
        {
            "device_id": device_id,
            "session_id": session_id,
            "operations_completed": operations_completed,
            "operations_planned": operations_planned,
            "current_file": current_file,
        },
        room=f"user:{user_id}",
    )


async def emit_sync_completed(
    user_id: int,
    device_id: str,
    session_id: int,
    operations_completed: int,
    operations_failed: int,
) -> None:
    """Notify that a sync session has completed."""
    sm = _get_socket_manager()
    await sm.emit(
        "sync:completed",
        {
            "device_id": device_id,
            "session_id": session_id,
            "operations_completed": operations_completed,
            "operations_failed": operations_failed,
        },
        room=f"user:{user_id}",
    )


async def emit_sync_conflict(
    user_id: int,
    device_id: str,
    session_id: int,
    file_name: str,
    rom_id: int,
    reason: str,
) -> None:
    """Notify that a sync conflict was detected."""
    sm = _get_socket_manager()
    await sm.emit(
        "sync:conflict",
        {
            "device_id": device_id,
            "session_id": session_id,
            "file_name": file_name,
            "rom_id": rom_id,
            "reason": reason,
        },
        room=f"user:{user_id}",
    )


async def emit_sync_error(
    user_id: int,
    device_id: str,
    session_id: int,
    error_message: str,
) -> None:
    """Notify that a sync error occurred."""
    sm = _get_socket_manager()
    await sm.emit(
        "sync:error",
        {
            "device_id": device_id,
            "session_id": session_id,
            "error": error_message,
        },
        room=f"user:{user_id}",
    )
