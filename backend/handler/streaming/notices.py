"""Telling a player what happened to their streaming session.

Kept apart from session_store because delivery loads the socket server and the
database, which the streaming worker's parent must not hold.
"""

from datetime import datetime, timezone
from typing import Any

from handler.notification_handler import notify
from handler.socket_handler import socket_handler
from handler.streaming.session_store import (
    StreamingSession,
    save_termination,
    session_is_desktop,
)
from models.notification import NotificationKind, NotificationLevel


async def record_termination(
    session: StreamingSession,
    session_key: str,
    *,
    ended_by: str | None,
    reason: str | None,
    ended_by_user_id: int | None = None,
) -> None:
    """Leave a note for the player whose session was taken away, and push it
    over the socket so the poll isn't the only way that tab finds out. No-op
    when the session records no owner, since there is nobody to notify."""
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return
    notice = {
        "ended_by": ended_by,
        "reason": reason or None,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "platform": session.get("platform"),
        "rom_id": session.get("rom_id"),
        "rom_name": session.get("rom_name"),
        # Which claim ended: a user can hold one per container, plus a desktop,
        # and only the tab that holds this one should act on the notice.
        "container": session_key,
        # A re-claim of the container keeps its key, so the stamp names the claim.
        "claimed_at": session.get("claimed_at"),
        "desktop": session_is_desktop(session),
    }
    await save_termination(session_key, user_id, notice)
    await push_to_user(user_id, "streaming:session-ended", notice)

    if ended_by_user_id is not None and ended_by_user_id != user_id:
        await notify(
            user_id,
            NotificationKind.STREAMING_SESSION_ENDED,
            NotificationLevel.WARNING,
            {
                "rom_id": notice["rom_id"],
                "rom_name": notice["rom_name"],
                "platform": notice["platform"],
                "reason": notice["reason"],
            },
            actor_id=ended_by_user_id,
        )


async def push_to_user(user_id: Any, event: str, payload: dict[str, Any]) -> None:
    """Tell one user's open tabs something happened to their session.

    Best-effort by design: every event pushed here also has a poll behind it,
    so a dropped socket costs latency rather than correctness.
    """
    if isinstance(user_id, int):
        await socket_handler.emit_to_user(user_id, event, payload)
