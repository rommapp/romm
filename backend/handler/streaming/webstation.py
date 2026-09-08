"""The webstation broker protocol.

One webstation container replaces the per-emulator mods, and its contract
differs enough to need translating. It hosts a single session behind a
subfolder; activate carries the user, the rom and the save data in one body;
and exit does the save state, the teardown and the save dump together.

The awkward part is save transfer. Activate names the restore archive by
container path, but RomM holds bytes and runs on another host, so an archive
is uploaded first and the path it returns is what activate gets. On the way
out the broker pushes to a callback, which is unreachable in dev mode and
lost on a failed push, so RomM pulls from the export list instead and deletes
what it stored.

Save states round-trip through the same /state-file routes as the other
brokers, just under the subfolder, so RomM holds the library either way. The
difference is that this broker keeps one working slot instead of ten: a slot
sent to it resolves to that one, and a pushed state is only accepted while a
session is up. Reads outlive the session, because exit captures a state and
RomM can only come back for it once the teardown has answered. What is still
missing here is volume, mute and whole-card sync.
"""

import urllib.error
from typing import Any
from urllib.parse import quote

from config import STREAMING_LAUNCH_TIMEOUT, STREAMING_SAVE_TIMEOUT
from handler.streaming import broker
from handler.streaming.config import ResolvedContainer
from handler.streaming.protocol import ACK_TIMEOUT
from logger.logger import log
from models.user import User


def activate(
    container: ResolvedContainer,
    *,
    session_id: str,
    user: User,
    emulator: str,
    rom: dict[str, Any] | None = None,
    gui_language: str | None = None,
    archive_path: str | None = None,
    resume_slot: int | None = None,
    memory_card_synced: bool = False,
    multiplayer: bool = False,
) -> dict[str, Any]:
    """POST /activate. Raises HTTPException the same way commands.launch does.

    `rom` is omitted for emulators the broker registers with requires_rom
    False, the desktop being the one that matters here.
    """
    body: dict[str, Any] = {
        "session_id": session_id,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.username,
        },
        "emulator": emulator,
        "multiplayer": multiplayer,
    }
    if rom is not None:
        body["rom"] = rom
    if gui_language:
        # Describes the player, not the rom, so it goes alongside `rom` rather
        # than inside it and is sent for a romless launch too.
        body["gui_language"] = gui_language
    save: dict[str, Any] = {}
    if archive_path:
        save["archive"] = archive_path
    if resume_slot is not None:
        save["resume_slot"] = resume_slot
    if memory_card_synced:
        # The card travels on its own routes, so the broker leaves it out of
        # both the archive it restores and the one it dumps at exit.
        save["memory_card_synced"] = True
    if save:
        body["save"] = save

    path = container.protocol.session_route("/activate")
    try:
        resp = broker.request(
            container, path, body=body, timeout=STREAMING_LAUNCH_TIMEOUT
        )
    except urllib.error.HTTPError as exc:
        broker.raise_http_error(exc)
    except (urllib.error.URLError, OSError) as exc:
        broker.raise_unreachable(
            exc,
            "the webstation broker",
            broker.broker_url(container, path),
            "Check that the container is running and its broker port is "
            "reachable from the RomM host.",
        )

    resp = resp if isinstance(resp, dict) else {}
    log.info("broker activated session, %s", resp)
    return resp


def launch_phase(container: ResolvedContainer) -> str | None:
    """GET /api/session/status, reduced to the extraction phase it reports.

    The broker sets this while it unpacks a pkg or archive, which is the part
    of an activate long enough that the player needs to see something. None
    covers every other answer: no session, a launch already past extraction,
    or a broker that did not reply.
    """
    body = broker.request_safe(
        container,
        container.protocol.session_route("/status"),
        "status",
        method="GET",
        timeout=ACK_TIMEOUT,
    )
    if not isinstance(body, dict):
        return None
    phase = body.get("extraction_phase")
    return phase if isinstance(phase, str) else None


def join(container: ResolvedContainer, user: User) -> dict[str, Any] | None:
    """POST /api/session/join. The broker's answer, or None if it refused.

    The broker mints the seat and replies with a landing URL carrying the new
    viewer's own token. Nothing here grants control of the container: every
    control route still goes through access.assert_session_owner.
    """
    body = broker.request_safe(
        container,
        container.protocol.session_route("/join"),
        "join",
        body={
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.username,
            },
            "permission": "participant",
        },
        timeout=ACK_TIMEOUT,
    )
    return body if isinstance(body, dict) else None


def exit_session(
    container: ResolvedContainer, slot: int, save: bool = True
) -> dict[str, Any] | None:
    """POST /exit. Best-effort, the caller is already tearing the session down.

    Slot 0 is a real slot on this broker (it keeps one working slot), so the
    request carries it like any other and the save flag, not the number, is
    what says whether a state is wanted at all.
    """
    query = f"?slot={slot}" + ("" if save else "&save=0")
    body = broker.request_safe(
        container,
        container.protocol.session_route(f"/exit{query}"),
        "exit",
        timeout=STREAMING_SAVE_TIMEOUT,
    )
    return body if isinstance(body, dict) else None


def upload_archive(
    container: ResolvedContainer, name: str, content: bytes
) -> str | None:
    """PUT a save archive and return the container path activate wants."""
    body = broker.put_binary_json(
        container,
        container.protocol.session_route(f"/imports/{quote(name, safe='')}"),
        content,
        "archive upload",
        content_type="application/zip",
        timeout=broker.TRANSFER_TIMEOUT,
    )
    if not body or not body.get("path"):
        return None
    return str(body["path"])


def exports(container: ResolvedContainer) -> list[dict[str, Any]]:
    """Save archives waiting on the container, newest first."""
    body = broker.request_safe(
        container,
        container.protocol.session_route("/exports"),
        "export list",
        method="GET",
        timeout=ACK_TIMEOUT,
    )
    exports = body.get("exports") if isinstance(body, dict) else None
    return exports if isinstance(exports, list) else []


def collect_export(container: ResolvedContainer, name: str) -> bytes | None:
    """Download one archive and drop the container's copy once it is in hand.

    The name comes from the broker's own listing, so it is escaped whole: a
    slash or a `..` in it would otherwise address a different broker route.
    """
    result = broker.get_binary_safe(
        container,
        container.protocol.session_route(f"/exports/{quote(name, safe='')}"),
        "export download",
        max_bytes=broker.SAVE_FILE_MAX_BYTES,
        timeout=broker.TRANSFER_TIMEOUT,
    )
    if result is None:
        return None
    broker.request_safe(
        container,
        container.protocol.session_route(f"/exports/{quote(name, safe='')}"),
        "export delete",
        method="DELETE",
        timeout=ACK_TIMEOUT,
    )
    return result[1]
