"""The text of a notification that leaves RomM, in English until it can be translated."""

from dataclasses import dataclass
from typing import Any

from endpoints.responses.notification import NotificationSchema
from models.notification import NotificationKind
from utils.urls import get_public_base_url


@dataclass(frozen=True)
class OutboundMessage:
    notification: NotificationSchema
    title: str
    body: str | None
    # Absolute, or None when ROMM_BASE_URL doesn't point anywhere shareable.
    url: str | None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def _describe(n: NotificationSchema) -> tuple[str, str | None, str | None]:
    """Title, body and in-app path, mirroring the client's describers."""
    data = n.data
    match n.kind:
        case NotificationKind.SCAN_COMPLETED:
            new_roms = _count(data.get("new_roms"))
            body = (
                f"{new_roms} new game{'' if new_roms == 1 else 's'}"
                if new_roms
                else "No new games"
            )
            return "Scan completed", body, "/scan"
        case NotificationKind.SCAN_FAILED:
            return "Scan failed", _text(data.get("error")), "/scan"
        case NotificationKind.TASK_COMPLETED:
            task = _text(data.get("title")) or "A task"
            return f"{task} finished", None, "/administration"
        case NotificationKind.TASK_FAILED:
            task = _text(data.get("title")) or "A task"
            return f"{task} failed", _text(data.get("error")), "/administration"
        case NotificationKind.STREAMING_SESSION_ENDED:
            game = _text(data.get("rom_name"))
            rom_id = _count(data.get("rom_id"))
            title = (
                f"Your stream of {game} was ended"
                if game
                else "Your streaming session was ended"
            )
            return (
                title,
                _text(data.get("reason")),
                f"/rom/{rom_id}" if rom_id else None,
            )
        case NotificationKind.ROLE_CHANGED:
            role = _text(data.get("role"))
            title = (
                f"Your role is now {role.capitalize()}" if role else "Your role changed"
            )
            return title, None, None
        case NotificationKind.CHANNEL_DISABLED:
            name = _text(data.get("name")) or "A notification channel"
            return (
                f"{name} was turned off",
                _text(data.get("error")),
                "/notifications?tab=channels",
            )
        case _:
            return n.title or "New notification", n.body, n.link


def render(notification: NotificationSchema) -> OutboundMessage:
    title, body, path = _describe(notification)
    base_url = get_public_base_url()
    return OutboundMessage(
        notification=notification,
        title=title,
        body=body,
        url=f"{base_url}{path}" if base_url and path else None,
    )
