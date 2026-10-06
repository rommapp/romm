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

import hashlib
import http.client
import json
import time
import urllib.error
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote, urlencode

from fastapi import HTTPException
from redis.exceptions import RedisError

from config import STREAMING_LAUNCH_TIMEOUT, STREAMING_SAVE_TIMEOUT
from handler.redis_handler import sync_cache
from handler.streaming import broker
from handler.streaming.config import ResolvedContainer
from handler.streaming.protocol import ACK_TIMEOUT, WebstationProtocol
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


# Per container and core. A 404 or 422 expires so a broker upgrade is seen
# without a RomM restart; a fallback answer only spans one claim's checks.
_IMPORT_SPEC_TTL = 30.0
_IMPORT_SPEC_MISSING_TTL = 300.0
_IMPORT_SPEC_FALLBACK_TTL = 10.0
_ImportSpecKey = tuple[str, str, str, str | None, bool]
_import_spec_cache: dict[_ImportSpecKey, tuple[float, ImportSpec | None]] = {}

# Shared across web workers, so one that never reached the broker still has it.
_LAST_GOOD_KEY_PREFIX = "romm:streaming:import-spec:"
_LAST_GOOD_TTL_SECONDS = 7 * 24 * 60 * 60


class ImportSpecUnavailable(HTTPException):
    """The broker can't be asked and no earlier answer stands in, so retry later."""

    def __init__(self) -> None:
        detail = "Couldn't reach the streaming container to check this pick, try again"
        super().__init__(status_code=503, detail=detail)


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
    try:
        return require_import_spec(container, emulator, platform)
    except ImportSpecUnavailable:
        return None


def require_import_spec(
    container: ResolvedContainer, emulator: str, platform: str
) -> ImportSpec | None:
    """What this broker accepts as a declared import, or None when nothing.

    Raises ImportSpecUnavailable when the broker can't be asked and no earlier
    answer stands in, so a launch can tell "try again" from "never".
    """
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
        if code == 404:
            # A broker that answered before is likelier restarting behind a
            # proxy than downgraded, so its last answer stands in.
            try:
                return _last_good_import_spec(cache_key)
            except ImportSpecUnavailable:
                pass
            # Once per worker, not at every expiry of the cached answer.
            if cached is None or cached[1] is not None:
                log.warning(
                    "import-spec not found on %s, the broker predates imports",
                    container.key,
                )
            _no_imports(cache_key, _IMPORT_SPEC_MISSING_TTL)
            return None
        if code == 422:
            # A refused core is fixed by upgrading the broker, so that answer
            # expires sooner than an emulator the broker doesn't know.
            ttl = _IMPORT_SPEC_TTL if container.core else _IMPORT_SPEC_MISSING_TTL
            _forget_last_good(cache_key)
            _no_imports(cache_key, ttl)
            return None
        if code >= 500 or code == 429:
            log.warning("import-spec check failed with HTTP %d", code)
            return _last_good_import_spec(cache_key)
        log.error("import-spec check on %s refused with HTTP %d", container.key, code)
        _no_imports(cache_key, _IMPORT_SPEC_TTL)
        return None
    except urllib.error.URLError, OSError, http.client.HTTPException:
        log.warning("import-spec check unreachable on %s", container.key)
        return _last_good_import_spec(cache_key)
    except ValueError as exc:
        log.error("import-spec response from %s was not JSON, %s", container.key, exc)
        _no_imports(cache_key, _IMPORT_SPEC_TTL)
        return None
    spec = _parse_import_spec(resp) if isinstance(resp, dict) else None
    if spec is None:
        log.error("import-spec response from %s was unreadable", container.key)
        _no_imports(cache_key, _IMPORT_SPEC_TTL)
        return None
    _import_spec_cache[cache_key] = (time.monotonic() + _IMPORT_SPEC_TTL, spec)
    _remember_last_good(cache_key, resp)
    return spec


def _no_imports(cache_key: _ImportSpecKey, ttl: float) -> None:
    # Retrying can't change this answer, so it is cached, not a 503.
    _import_spec_cache[cache_key] = (time.monotonic() + ttl, None)


def _last_good_key(cache_key: _ImportSpecKey) -> str:
    digest = hashlib.sha256(json.dumps(cache_key).encode()).hexdigest()
    return f"{_LAST_GOOD_KEY_PREFIX}{digest}"


def _remember_last_good(cache_key: _ImportSpecKey, body: dict[str, Any]) -> None:
    # The broker's own body, so reading it back runs the same checks.
    try:
        sync_cache.set(
            _last_good_key(cache_key), json.dumps(body), ex=_LAST_GOOD_TTL_SECONDS
        )
    except RedisError:
        log.warning("import-spec answer could not be cached")


def _forget_last_good(cache_key: _ImportSpecKey) -> None:
    try:
        sync_cache.delete(_last_good_key(cache_key))
    except RedisError:
        log.warning("import-spec answer could not be forgotten")


def _last_good_import_spec(cache_key: _ImportSpecKey) -> ImportSpec:
    """The broker's last answer, which a failed check doesn't overturn."""
    try:
        raw = sync_cache.get(_last_good_key(cache_key))
    except RedisError:
        raw = None
    if raw is None:
        raise ImportSpecUnavailable
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    spec = _parse_import_spec(body) if isinstance(body, dict) else None
    if spec is None:
        # Written by another RomM version, or cut short: no answer at all.
        raise ImportSpecUnavailable
    log.info("import-spec check failed, using the broker's last answer")
    _import_spec_cache[cache_key] = (
        time.monotonic() + _IMPORT_SPEC_FALLBACK_TTL,
        spec,
    )
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
    except urllib.error.URLError, OSError, http.client.HTTPException, ValueError:
        log.warning("retroarch cores check unreachable, not filtering states by core")
        return None
    else:
        value = resp.get("default") if isinstance(resp, dict) else None
        core = value if isinstance(value, str) and value else None
    _default_core_cache[cache_key] = (time.monotonic() + _DEFAULT_CORE_TTL, core)
    return core


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
