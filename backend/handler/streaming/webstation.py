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

import http.client
import math
import time
import urllib.error
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote, urlencode

from fastapi import HTTPException

from config import STREAMING_LAUNCH_TIMEOUT, STREAMING_SAVE_TIMEOUT
from handler.ra_login import clear_ra_login, ra_login_for_activate, store_ra_login
from handler.streaming import broker
from handler.streaming.config import ResolvedContainer
from handler.streaming.protocol import ACK_TIMEOUT, WebstationProtocol
from handler.streaming.session_store import broker_session_id, session_is_desktop
from logger.logger import log
from models.user import User


@dataclass(frozen=True)
class ImportSpec:
    """What one (emulator, platform) pair accepts through a declared import."""

    kinds: frozenset[str]
    state_channel: Literal["archive", "push", "none"]
    state_slot: int | None

    def accepts(self, kind: str) -> bool:
        return kind in self.kinds

    def resume_slot(self) -> int | None:
        """The slot an imported state resumes through, or None when it cannot."""
        if self.accepts("state") and self.state_channel != "none":
            return self.state_slot
        return None

    def pickable_kinds(self) -> list[Literal["save", "state"]]:
        """The launch picks a foreign save or state can resume through here."""
        kinds: list[Literal["save", "state"]] = []
        if self.accepts("save"):
            kinds.append("save")
        if self.resume_slot() is not None:
            kinds.append("state")
        return kinds


# Per container and core. A 404 or 422 holds for the worker's life, an answer
# or a refused core for one claim's checks, a failure not at all.
_IMPORT_SPEC_TTL = 30.0
_import_spec_cache: dict[
    tuple[str, str, str, str | None, bool], tuple[float, ImportSpec | None]
] = {}


def _parse_import_spec(body: dict[str, Any]) -> ImportSpec | None:
    raw_kinds = body.get("kinds")
    if not isinstance(raw_kinds, list):
        log.warning("import-spec response has no kinds list, treating as unknown")
        return None
    if not all(
        isinstance(entry, dict) and isinstance(entry.get("kind"), str)
        for entry in raw_kinds
    ):
        log.warning("import-spec response has a malformed kind entry, %r", raw_kinds)
        return None
    state_channel = body.get("state_channel")
    if state_channel not in ("archive", "push", "none"):
        log.warning(
            "import-spec response has an unrecognized state_channel, %r",
            state_channel,
        )
        return None
    state_slot = body.get("state_slot")
    return ImportSpec(
        kinds=frozenset(entry["kind"] for entry in raw_kinds),
        state_channel=state_channel,
        state_slot=state_slot if isinstance(state_slot, int) else None,
    )


def import_spec(
    container: ResolvedContainer, emulator: str, platform: str
) -> ImportSpec | None:
    """What this broker accepts as a declared import, or None when nothing or unknown."""
    if not container.is_webstation:
        return None
    # The core is part of the key, so a config edit that changes the core is
    # asked about afresh rather than read from the old core's answer.
    cache_key = (
        container.key,
        emulator,
        platform,
        container.core,
        container.experimental_cores,
    )
    cached = _import_spec_cache.get(cache_key)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]
    params = {"emulator": emulator, "platform": platform}
    if container.core:
        # Discovery has to answer for the core activate will boot.
        params["core"] = container.core
        if container.experimental_cores:
            params["experimental_cores"] = "1"
    path = container.protocol.session_route(f"/import-spec?{urlencode(params)}")
    try:
        resp = broker.request(container, path, method="GET", timeout=ACK_TIMEOUT)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code in (404, 422):
            # A refused core is fixed by upgrading the broker, so that answer
            # expires like any other rather than lasting until a restart.
            refused_core = code == 422 and container.core is not None
            expires = time.monotonic() + _IMPORT_SPEC_TTL if refused_core else math.inf
            _import_spec_cache[cache_key] = (expires, None)
            return None
        log.warning("import-spec check failed with HTTP %d, treating as unknown", code)
        return None
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        log.warning("import-spec check unreachable, treating as unknown")
        return None
    except ValueError as exc:
        log.warning("import-spec response was not valid JSON, %s", exc)
        return None
    if not isinstance(resp, dict):
        log.warning("import-spec response was not a JSON object, treating as unknown")
        return None
    spec = _parse_import_spec(resp)
    if spec is not None:
        _import_spec_cache[cache_key] = (time.monotonic() + _IMPORT_SPEC_TTL, spec)
    return spec


# Short-lived, 404s included: a broker upgrade adds the route and a restart can
# change the default, and neither should need a RomM restart to be seen.
_DEFAULT_CORE_TTL = 60.0
_default_core_cache: dict[tuple[str, str], tuple[float, str | None]] = {}


def default_core(container: ResolvedContainer) -> str | None:
    """The core this broker boots for the platform when config names none.

    None when it can't say: not RetroArch, a broker too old, or unreachable.
    """
    protocol = container.protocol
    if (
        not isinstance(protocol, WebstationProtocol)
        or container.emulator.lower() != "retroarch"
    ):
        return None
    cache_key = (container.key, container.platform)
    cached = _default_core_cache.get(cache_key)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]
    path = protocol.api_route(
        f"/retroarch/cores?platform={quote(container.platform, safe='')}"
    )
    core: str | None = None
    try:
        resp = broker.request(container, path, method="GET", timeout=ACK_TIMEOUT)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code != 404:
            log.warning("retroarch cores check failed with HTTP %d", code)
            return None
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
        log.warning("retroarch cores check unreachable, not filtering states by core")
        return None
    else:
        value = resp.get("default") if isinstance(resp, dict) else None
        core = value if isinstance(value, str) and value else None
    _default_core_cache[cache_key] = (time.monotonic() + _DEFAULT_CORE_TTL, core)
    return core


def _with_ra_login(body: dict[str, Any], user: User) -> dict[str, Any]:
    """`body` plus the user's stored login when it activates a game.

    Every game session gets it, whatever the emulator: the broker pins it where
    it can and ignores it elsewhere. Kept out of `user`, which the broker's
    status route echoes, and out of activate's locals, which a traceback keeps.
    """
    if "rom" not in body:
        return body
    login = ra_login_for_activate(user)
    return body if login is None else {**body, "retroachievements": login}


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
    # The core belongs to the platform's emulator; the desktop boots none.
    core = (
        container.core if rom is not None and emulator == container.emulator else None
    )
    if rom is not None:
        # Only a configured core goes out, so an unconfigured platform's body is
        # what a broker without core support has always read.
        body["rom"] = {**rom, "core": core} if core else rom
        if core and container.experimental_cores:
            body["rom"]["experimental_cores"] = True
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
    failure: Exception | None = None
    try:
        resp = broker.request(
            container,
            path,
            body=_with_ra_login(body, user),
            timeout=STREAMING_LAUNCH_TIMEOUT,
        )
    except urllib.error.HTTPError as exc:
        failure = broker.http_error(exc)
    except (urllib.error.URLError, OSError) as exc:
        failure = broker.unreachable_error(
            exc,
            "the webstation broker",
            broker.broker_url(container, path),
            "Check that the container is running and its broker port is "
            "reachable from the RomM host.",
        )
    except HTTPException as exc:
        failure = HTTPException(
            status_code=exc.status_code, detail=exc.detail, headers=exc.headers
        )
    except Exception as exc:  # noqa: BLE001 - a non-JSON or oversized reply
        log.error("webstation broker activate failed, %s", type(exc).__name__)
        failure = HTTPException(
            status_code=502,
            detail="The webstation broker answered activate with an unreadable reply.",
        )
    if failure is not None:
        # Raised fresh, outside the handler: the request's frames hold the
        # login, and Sentry reads the locals of every frame in the chain.
        raise failure from None

    resp = resp if isinstance(resp, dict) else {}
    log.info("broker activated session, %s", resp)
    if not isinstance(resp.get("core_tier"), str):
        resp.pop("core_tier", None)
    if core and resp.get("core") != core:
        # An older broker drops the field and boots its default; a dump at exit
        # would file that core's saves under this platform, so ask for none.
        log.warning(
            "broker booted core %s, not the configured %s, ending the session",
            resp.get("core"),
            core,
        )
        # The broker refuses every activate while this game runs, and releasing
        # the claim leaves nothing behind to stop it, so one lost exit is retried.
        if exit_session(container, 0, save=False) is None and (
            exit_session(container, 0, save=False) is None
        ):
            log.error("wrong-core game on %s is still running", container.key)
        raise HTTPException(
            status_code=502,
            detail=(
                "This broker doesn't support `core:`. Upgrade the container, "
                f"or remove `core: {core}` from the "
                f"{container.platform} platform in config.yml."
            ),
        )
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


def collect_ra_login(container: ResolvedContainer, session: dict[str, Any]) -> None:
    """POST /retroachievements/collect: file the login change the session ended with.

    Runs while the claim still holds the container: the broker drops the
    change at its next activate, and releasing the claim is what allows one.
    Best-effort like exit_session; nothing here raises out of a teardown. The
    token is only ever in the reply and the sealed column, never in a log.
    """
    session_id = broker_session_id(session)
    user_id = session.get("user_id")
    if (
        session_is_desktop(session)
        or session_id is None
        or not isinstance(user_id, int)
    ):
        return
    try:
        reply = broker.request_safe(
            container,
            container.protocol.session_route("/retroachievements/collect"),
            "ra login collect",
            body={"session_id": session_id},
            timeout=STREAMING_SAVE_TIMEOUT,
            missing_ok=True,
        )
        if reply is None:
            # request_safe logged the failure, status code included.
            return
        if reply == {}:
            # The 204: nothing pending.
            return
        if not isinstance(reply, dict) or "change" not in reply:
            log.warning(
                "session %s: ra login collect answered something unexpected", session_id
            )
            return
        if reply.get("session_id") != session_id:
            log.warning(
                "session %s: ra login collect answered for session %s, discarded",
                session_id,
                reply.get("session_id"),
            )
            return
        change = reply.get("change")
        login = reply.get("retroachievements")
        if change == "set":
            username = login.get("username") if isinstance(login, dict) else None
            token = login.get("token") if isinstance(login, dict) else None
            if not (
                isinstance(username, str)
                and username
                and isinstance(token, str)
                and token
            ):
                log.warning(
                    "session %s: ra login collect answered a set change without a login",
                    session_id,
                )
                return
            filed = store_ra_login(user_id, username, token)
        elif change == "cleared":
            filed = clear_ra_login(user_id)
        else:
            log.warning(
                "session %s: ra login collect answered an unknown change", session_id
            )
            return
        if filed:
            log.info(
                "session %s: ra login %s collected for user %s",
                session_id,
                change,
                user_id,
            )
    except Exception as exc:  # noqa: BLE001 - a teardown finishes whatever this did
        # The type alone: the message or a traceback could carry the reply.
        log.warning(
            "session %s: ra login collect failed, %s",
            session_id,
            type(exc).__name__,
            exc_info=False,
        )


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
