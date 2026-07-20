import asyncio
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict
from urllib.parse import urlparse, urlunparse

from fastapi import Body, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import LIBRARY_BASE_PATH, STREAMING_BROKER_SECRET, STREAMING_SAVE_TIMEOUT
from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.redis_handler import async_cache
from models.user import Role
from utils.router import APIRouter

log = logging.getLogger("romm")

router = APIRouter(prefix="/streaming", tags=["streaming"])

# Sessions are stored in Redis so they are shared across uvicorn workers and
# survive backend restarts (the emulator container keeps running either way).
# Claiming uses SET NX, which is atomic in Redis. Two concurrent claims for
# the same container cannot both succeed, with no in-process locking needed.
_SESSION_KEY_PREFIX = "romm:streaming:session:"

# An active session is long-lived (a game can run for hours), but the key
# must not live forever: if the broker container dies or the backend
# crashes mid-session, the TTL ensures the container is eventually
# reclaimable instead of wedged until an admin force-releases. Control
# calls (save-state / volume / mute / save-and-exit) refresh the TTL so a
# session in active use never expires.
SESSION_TTL_SECONDS = 6 * 60 * 60

# When save-and-exit runs with wait=false the broker is still killing the
# emulator in the background when the route returns. A short drain TTL
# keeps the key briefly so a concurrent new claim can't /launch on top of
# a not-yet-dead emulator (which would lose the in-flight save). The key
# expires on its own; no explicit DELETE.
SESSION_DRAIN_SECONDS = 5


def _session_redis_key(session_key: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{session_key}"


async def _get_session(session_key: str) -> dict[str, Any] | None:
    raw = await async_cache.get(_session_redis_key(session_key))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        # Corrupt entry, drop it rather than wedging the container forever.
        await async_cache.delete(_session_redis_key(session_key))
        return None


async def _refresh_session(session_key: str) -> None:
    """Reset the session TTL back to the full window. Called after every
    successful control op so a session in active use never expires; only an
    abandoned one (broker dead / backend crashed) ages out."""
    await async_cache.expire(_session_redis_key(session_key), SESSION_TTL_SECONDS)


def _assert_session_owner(session: dict[str, Any], request: Request) -> None:
    """Only the user who claimed a session (or an admin) may control it."""
    if session.get("user_id") == request.user.id:
        return
    if request.user.role == Role.ADMIN:
        return
    raise HTTPException(status_code=403, detail="Session is claimed by another user")


def _parse_host_url(host: str) -> str | None:
    """Validate a configured host/broker_host string and return it stripped,
    or None when it has no scheme (urlparse yields hostname=None for a bare
    'host:port', which would produce the broken '//None:8000/...' string).
    Operators must write a scheme, matching the documented config examples."""
    host = host.strip().rstrip("/")
    if not host:
        return None
    parsed = urlparse(host)
    if not parsed.scheme or not parsed.hostname:
        return None
    return host


def _derive_broker_host(container: dict[str, Any]) -> str | None:
    """Resolve the broker API host for a container: broker_host if set,
    otherwise the stream host with its port swapped to 8000. Returns None
    when neither resolves to a usable scheme-bearing URL."""
    broker_host = _parse_host_url(container.get("broker_host", ""))
    if broker_host:
        return broker_host.rstrip("/")
    stream_host = _parse_host_url(container.get("host", ""))
    if not stream_host:
        return None
    parsed = urlparse(stream_host)
    return urlunparse(parsed._replace(netloc=f"{parsed.hostname}:8000")).rstrip("/")


def _container_key(container: dict[str, Any]) -> str:
    """Stable unique key for a container, derived the same way as the broker URL."""
    return _derive_broker_host(container) or ""


# Per-platform save-state capabilities, the single source of truth for how
# many save slots each emulator exposes. The broker enforces its own ceiling;
# this table lets RomM reject an out-of-range slot before calling the broker
# (a clean 422 instead of a broker 502) and ships the same numbers to the
# frontend via /config, so the slot selector is not a second hardcoded copy.


class PlatformCapabilities(TypedDict):
    max_slots: int  # manual save slots, selectable as 1..max_slots
    has_autosave: bool  # whether a dedicated autosave slot can be loaded
    autosave_slot: int  # that slot's index (loadable, not savable), 0 if none


# Keyed by platform slug (lowercase). A platform absent here gets no save-state
# UI until its broker's slot semantics are known.
_PLATFORM_CAPABILITIES: dict[str, PlatformCapabilities] = {
    # Dolphin (ngc, wii, wiiu): slots 1-7 manual, slot 8 autosave.
    "ngc": {"max_slots": 7, "has_autosave": True, "autosave_slot": 8},
    "wii": {"max_slots": 7, "has_autosave": True, "autosave_slot": 8},
    "wiiu": {"max_slots": 7, "has_autosave": True, "autosave_slot": 8},
    # PCSX2 (ps2) and xemu (xbox): slots 1-9 manual, slot 10 autosave.
    "ps2": {"max_slots": 9, "has_autosave": True, "autosave_slot": 10},
    "xbox": {"max_slots": 9, "has_autosave": True, "autosave_slot": 10},
}

_NO_CAPABILITIES: PlatformCapabilities = {
    "max_slots": 0,
    "has_autosave": False,
    "autosave_slot": 0,
}


def platform_capabilities(platform: str) -> PlatformCapabilities:
    """Save-state capabilities for a platform slug, or a no-slots default."""
    return _PLATFORM_CAPABILITIES.get(platform.lower(), _NO_CAPABILITIES)


# Coarse request-body bounds, derived from the table so the slot ranges live in
# exactly one place. The per-platform check in the routes is the tighter,
# authoritative guard; these just reject obviously out-of-range input up front.
_MAX_SAVE_SLOT = max(
    (c["max_slots"] for c in _PLATFORM_CAPABILITIES.values()), default=1
)
_MAX_LOAD_SLOT = max(
    (max(c["max_slots"], c["autosave_slot"]) for c in _PLATFORM_CAPABILITIES.values()),
    default=1,
)


def _assert_valid_slot(platform: str, slot: int, *, allow_autosave: bool) -> None:
    """Reject a slot the platform does not expose before hitting the broker."""
    caps = platform_capabilities(platform)
    valid = 1 <= slot <= caps["max_slots"]
    if allow_autosave and caps["has_autosave"] and slot == caps["autosave_slot"]:
        valid = True
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"Slot {slot} is not available for platform '{platform}'",
        )


class ClaimSessionRequest(BaseModel):
    rom_id: Annotated[int, Field(ge=1)]


class SaveAndExitRequest(BaseModel):
    slot: Annotated[int, Field(ge=0, le=10)] = 0
    wait: bool = True


class VolumeRequest(BaseModel):
    level: Annotated[int, Field(ge=0, le=100)]


class MuteRequest(BaseModel):
    mute: bool | None = None  # None = toggle, True/False = explicit set


class SaveStateRequest(BaseModel):
    # Coarse union bound; the route validates the exact per-platform ceiling
    # against _PLATFORM_CAPABILITIES.
    slot: Annotated[int, Field(ge=1, le=_MAX_SAVE_SLOT)] = 1


class LoadStateRequest(BaseModel):
    # Coarse union bound (widest is the autosave slot); the route validates the
    # exact per-platform ceiling against _PLATFORM_CAPABILITIES.
    slot: Annotated[int, Field(ge=1, le=_MAX_LOAD_SLOT)] = 1


def _get_streaming_config() -> dict[str, Any]:
    """Extract streaming config from the parsed Config object"""
    cfg = cm.get_config()

    return {"enabled": cfg.STREAMING_ENABLED, "containers": cfg.STREAMING_CONTAINERS}


# ── Routes ────────────────────────────────────────────────────────────────────


def _container_for_platform(platform: str) -> dict[str, Any] | None:
    cfg = _get_streaming_config()
    if not cfg.get("enabled", False):
        return None
    lower = platform.lower()
    for entry in cfg.get("containers", []):
        if not isinstance(entry, dict):
            continue
        # An entry needs both a platform and a scheme-bearing host.
        # Skipping a malformed entry here means claim / control routes raise
        # a clean 404 instead of a 500 on container["host"].
        if entry.get("platform", "").lower() != lower:
            continue
        if not _parse_host_url(entry.get("host", "")):
            log.warning(
                "container for platform '%s' missing a scheme-bearing "
                "host, skipping: %s",
                platform,
                entry,
            )
            continue
        return entry
    return None


async def _resolve_owned_session(
    platform: str, request: Request
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Map platform → container, fetch its active session, verify ownership.

    Returns (container, session_key, session). Raises 404 when the platform has
    no configured container or no active session, 403 when the session belongs
    to a different user.
    """
    container = _container_for_platform(platform)
    if container is None:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )
    session_key = _container_key(container)
    session = await _get_session(session_key)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )
    _assert_session_owner(session, request)
    return container, session_key, session


# ── Broker communication ────────────────────────────────────────────────────────────────────


def _broker_url(container: dict[str, Any], path: str) -> str:
    """
    Build the URL for the ROM broker API.

    The broker runs inside the emulator container on BROKER_PORT (default 8000).
    `broker_host` in config.yml is the host:port of the broker endpoint -
    separate from `host` which is the browser-facing stream URL.

    If broker_host is not set, we assume it is on the same host and swap the port.
    Example:
      host:         http://192.168.1.51:3000   (Selkies web UI, browser-facing)
      broker_host:  http://192.168.1.51:8000   (broker API, server-to-server)
    """
    broker_host = _derive_broker_host(container)
    if not broker_host:
        # No usable broker host, raise a 502 with a clear cause so the
        # operator sees the misconfiguration instead of an opaque KeyError.
        raise HTTPException(
            status_code=502,
            detail=(
                "Streaming container has no usable broker_host/host. "
                "Set broker_host (or host with a scheme, e.g. http://...) "
                "in the streaming.containers config."
            ),
        )

    return f"{broker_host}{path}"


def _broker_secret(container: dict[str, Any]) -> str:
    return STREAMING_BROKER_SECRET or container.get("broker_secret", "")


def _broker_request(
    container: dict[str, Any],
    path: str,
    *,
    method: str = "POST",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    """
    Send a signed request to the broker and return its parsed JSON body (an
    empty dict when the broker replies with no content). Uses only Python
    stdlib urllib, no extra dependencies. Raises the underlying urllib/OS
    error; callers decide whether to surface or swallow it.
    """
    url = _broker_url(container, path)
    secret = _broker_secret(container)
    headers = {"X-Broker-Secret": secret} if secret else {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        raw = resp.read()
    return json.loads(raw) if raw else {}


def _broker_request_safe(
    container: dict[str, Any],
    path: str,
    label: str,
    *,
    method: str = "POST",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any | None:
    """
    Best-effort variant of _broker_request: returns the parsed body, or None if
    the broker is unreachable or errors. Never raises, control ops must not 500
    on a broker hiccup.
    """
    try:
        return _broker_request(
            container, path, method=method, body=body, timeout=timeout
        )
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        return None


def _call_broker(container: dict[str, Any], rom_path: str, rom_name: str) -> None:
    """
    POST to the broker's /launch endpoint to tell the emulator container to
    load a ROM.

    Raises HTTPException if the broker is unreachable or returns an error.
    """
    url = _broker_url(container, "/launch")
    try:
        body = _broker_request(
            container,
            "/launch",
            body={"rom_path": rom_path, "rom_name": rom_name},
            timeout=10,
        )
        log.info("broker launched ROM, %s", body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        log.error("broker HTTP error %d: %s", exc.code, error_body)
        try:
            detail = json.loads(error_body)
        except Exception:
            detail = error_body
        raise HTTPException(
            status_code=502,
            detail=f"Broker returned {exc.code}: {detail}",
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        log.error("broker unreachable at %s: %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not reach ROM broker at {url}. "
                "Check that broker.py is running inside the emulator container "
                "and that port 8000 is reachable from the RomM host."
            ),
        ) from exc


def _save_and_exit_broker(
    container: dict[str, Any], slot: int = 0, wait: bool = True
) -> bool:
    """
    POST /save-and-exit to the broker. Best-effort, logs but never raises.
    With wait=True the call blocks until save+kill completes (use for button press).
    With wait=False the broker fires save+kill in the background (use for navigation away).
    Returns True if the broker reported a successful save.
    """
    # Waiting brokers can legitimately block for a while: rpcs3 polls the
    # savestate write for up to SAVE_WAIT (30s default) and xemu's QMP
    # save + reset path can approach that too. Time out past the slowest
    # broker so a slow-but-successful save is not reported as saved=False.
    # Overridable for operators who raise SAVE_WAIT on a broker.
    body = _broker_request_safe(
        container,
        "/save-and-exit",
        "save-and-exit",
        body={"slot": slot, "wait": wait},
        timeout=STREAMING_SAVE_TIMEOUT if wait else 5,
    )
    saved = bool(body and body.get("saved", False))
    log.info("broker save-and-exit, saved=%s slot=%d wait=%s", saved, slot, wait)
    return saved


def _volume_broker(container: dict[str, Any], level: int) -> bool:
    """POST /volume to the broker. Best-effort, logs but never raises."""
    body = _broker_request_safe(
        container, "/volume", "volume", body={"level": level}, timeout=5
    )
    return bool(body and body.get("status") == "ok")


def _mute_broker(container: dict[str, Any], mute: bool | None) -> bool | None:
    """POST /mute to the broker. Returns confirmed mute state, or None on error."""
    body = _broker_request_safe(
        container,
        "/mute",
        "mute",
        body={} if mute is None else {"mute": mute},
        timeout=5,
    )
    return body.get("mute") if body is not None else None


def _save_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /save-state to the broker. Returns True if the request was accepted."""
    body = _broker_request_safe(
        container, "/save-state", "save-state", body={"slot": slot}, timeout=5
    )
    return bool(body and body.get("status") == "saving")


def _load_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /load-state to the broker. Returns True if broker confirmed success."""
    # Timeout covers the worst case: 9 slot cycles x ~5s xdotool timeout.
    body = _broker_request_safe(
        container, "/load-state", "load-state", body={"slot": slot}, timeout=60
    )
    return bool(body and body.get("loaded", False))


def _stop_broker(container: dict[str, Any]) -> None:
    """Tell the broker to stop emulator. Best-effort, don't raise on failure."""
    _broker_request_safe(container, "/launch", "stop", method="DELETE", timeout=5)


# ── Routes ────────────────────────────────────────────────────────────────────


@protected_route(router.get, "/config", [Scope.ROMS_READ])
async def get_config(request: Request) -> JSONResponse:
    """Return streaming configuration to the frontend"""
    cfg = _get_streaming_config()

    safe_containers = []
    for c in cfg.get("containers", []):
        if not c.get("platform") or not c.get("host"):
            log.warning("container missing platform/host, skipping: %s", c)
            continue

        platform = c.get("platform", "")
        safe_containers.append(
            {
                "platform": platform,
                "host": c.get("host"),
                "label": c.get("label") or platform.upper(),
                # Ship slot capabilities so the frontend selector reads them
                # instead of keeping its own hardcoded per-platform copy.
                "capabilities": platform_capabilities(platform),
            }
        )

    return JSONResponse(
        {
            "enabled": cfg.get("enabled", False),
            "containers": safe_containers,
        }
    )


@protected_route(router.post, "/sessions", [Scope.ROMS_READ])
async def claim_session(
    request: Request, req: Annotated[ClaimSessionRequest, Body()]
) -> JSONResponse:
    """
    Claim a streaming session and tell the broker to load the ROM.

    The ROM's filesystem path is derived server-side from its database row -
    the client only supplies a ROM id, never a path.
    Returns 404 if the ROM doesn't exist or no container serves its platform.
    Returns 409 if the container is already occupied.
    Returns 502/503 if the broker rejects the launch or is unreachable.
    """
    rom = db_rom_handler.get_rom(req.rom_id)
    if rom is None:
        raise HTTPException(status_code=404, detail="ROM not found")

    container = _container_for_platform(rom.platform_slug)
    if container is None:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{rom.platform_slug}'",
        )

    # The emulator containers mount the RomM library at the same path the
    # backend uses (LIBRARY_BASE_PATH, /romm/library by default), so the
    # backend-side path is valid inside the broker container too.
    rom_path = f"{LIBRARY_BASE_PATH}/{rom.full_path}"
    rom_name = rom.name or rom.fs_name_no_ext

    session_key = _container_key(container)
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "rom_id": rom.id,
        "rom_name": rom_name,
        "claimed_at": now,
        "user_id": request.user.id,
    }

    # SET NX is atomic: exactly one concurrent claim wins the key. The TTL
    # bounds how long an abandoned session (broker dead / backend crashed)
    # can hold the container; control calls refresh it while in active use.
    claimed = await async_cache.set(
        _session_redis_key(session_key),
        json.dumps(session),
        nx=True,
        ex=SESSION_TTL_SECONDS,
    )
    if not claimed:
        existing = await _get_session(session_key) or {}
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Session in use",
                "rom_name": existing.get("rom_name"),
                "claimed_at": existing.get("claimed_at"),
            },
        )

    try:
        # Tell the broker to load the ROM, raises HTTPException on failure.
        # Wrapped in asyncio.to_thread because urllib is synchronous.
        await asyncio.to_thread(_call_broker, container, rom_path, rom_name)
    except Exception:
        # Launch failed, free the claim so the container isn't wedged.
        await async_cache.delete(_session_redis_key(session_key))
        raise

    log.info("session claimed, platform=%s rom=%s", rom.platform_slug, rom_name)

    return JSONResponse(
        {
            "platform": rom.platform_slug,
            "host": container.get("host", ""),
            "label": container.get("label", rom.platform_slug.upper()),
            "rom_name": rom_name,
            "claimed_at": now,
        }
    )


@protected_route(router.post, "/sessions/{platform}/save-and-exit", [Scope.ROMS_READ])
async def save_and_exit_session(
    request: Request, platform: str, req: Annotated[SaveAndExitRequest, Body()]
) -> JSONResponse:
    """
    Save game state then release the session.
    wait=true (default): blocks until broker confirms save+kill complete.
    wait=false: broker fires save+kill in background, returns immediately.
    """
    container, session_key, _ = await _resolve_owned_session(platform, request)

    saved = await asyncio.to_thread(
        _save_and_exit_broker, container, slot=req.slot, wait=req.wait
    )

    if req.wait:
        # Broker confirmed the save+kill is done, the key can go now.
        await async_cache.delete(_session_redis_key(session_key))
    else:
        # Broker is still killing the emulator in the background. Drop the
        # key to a short drain TTL instead of deleting it outright: a
        # concurrent new claim is briefly blocked so it can't /launch on
        # top of a not-yet-dead emulator (which would lose the in-flight
        # save). The marker is JSON so _get_session leaves it in place
        # (a bare string would parse as corrupt and be deleted, ending
        # the drain early). The key expires on its own once the window passes.
        await async_cache.set(
            _session_redis_key(session_key),
            json.dumps({"draining": True}),
            ex=SESSION_DRAIN_SECONDS,
        )
    log.info("save-and-exit, platform=%s saved=%s", platform, saved)
    return JSONResponse({"status": "ok", "saved": saved, "platform": platform})


@protected_route(router.post, "/sessions/{platform}/volume", [Scope.ROMS_READ])
async def set_volume(
    request: Request, platform: str, req: Annotated[VolumeRequest, Body()]
) -> JSONResponse:
    """Set emulator audio volume (0-100)."""
    container, session_key, _ = await _resolve_owned_session(platform, request)

    ok = await asyncio.to_thread(_volume_broker, container, req.level)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to set volume")

    await _refresh_session(session_key)
    return JSONResponse({"status": "ok", "level": req.level, "platform": platform})


@protected_route(router.post, "/sessions/{platform}/mute", [Scope.ROMS_READ])
async def set_mute(
    request: Request, platform: str, req: Annotated[MuteRequest, Body()]
) -> JSONResponse:
    """Toggle or explicitly set mute state. Omit body to toggle."""
    container, session_key, _ = await _resolve_owned_session(platform, request)

    confirmed = await asyncio.to_thread(_mute_broker, container, req.mute)
    if confirmed is None:
        raise HTTPException(status_code=502, detail="Broker failed to set mute state")

    await _refresh_session(session_key)
    return JSONResponse({"status": "ok", "mute": confirmed, "platform": platform})


@protected_route(router.post, "/sessions/{platform}/save-state", [Scope.ROMS_READ])
async def save_state(
    request: Request, platform: str, req: Annotated[SaveStateRequest, Body()]
) -> JSONResponse:
    """Save game state to a manual slot without stopping the emulator."""
    container, session_key, _ = await _resolve_owned_session(platform, request)
    _assert_valid_slot(platform, req.slot, allow_autosave=False)

    ok = await asyncio.to_thread(_save_state_broker, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to save state")

    await _refresh_session(session_key)
    return JSONResponse({"status": "saving", "slot": req.slot, "platform": platform})


@protected_route(router.post, "/sessions/{platform}/load-state", [Scope.ROMS_READ])
async def load_state(
    request: Request, platform: str, req: Annotated[LoadStateRequest, Body()]
) -> JSONResponse:
    """Load game state from a manual slot or the platform's autosave slot."""
    container, session_key, _ = await _resolve_owned_session(platform, request)
    _assert_valid_slot(platform, req.slot, allow_autosave=True)

    ok = await asyncio.to_thread(_load_state_broker, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to load state")

    await _refresh_session(session_key)
    return JSONResponse(
        {"status": "ok", "loaded": True, "slot": req.slot, "platform": platform}
    )


@protected_route(router.delete, "/sessions/{platform}", [Scope.ROMS_READ])
async def release_session(request: Request, platform: str) -> JSONResponse:
    """Release a session and tell the broker to stop the emulator."""
    container = _container_for_platform(platform)
    if container is None:
        # Streaming disabled or platform unconfigured, nothing to release.
        return JSONResponse({"status": "not_found", "platform": platform})

    session_key = _container_key(container)
    session = await _get_session(session_key)
    if session is None:
        return JSONResponse({"status": "not_found", "platform": platform})

    _assert_session_owner(session, request)
    await async_cache.delete(_session_redis_key(session_key))

    # Best-effort stop, don't block the user on broker errors.
    await asyncio.to_thread(_stop_broker, container)

    log.info("session released, platform=%s", platform)
    return JSONResponse({"status": "released", "platform": platform})


@protected_route(router.get, "/sessions", [Scope.ROMS_READ])
async def list_sessions(request: Request) -> JSONResponse:
    """Admin debug view, active sessions keyed by broker URL."""
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    sessions: dict[str, Any] = {}
    async for key in async_cache.scan_iter(match=f"{_SESSION_KEY_PREFIX}*"):
        raw = await async_cache.get(key)
        if raw is None:
            continue
        try:
            s = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        # scan_iter yields bytes unless the client decodes responses.
        key_str = key.decode() if isinstance(key, bytes) else key
        sessions[key_str.removeprefix(_SESSION_KEY_PREFIX)] = {
            "rom_name": s.get("rom_name"),
            "claimed_at": s.get("claimed_at"),
            "user_id": s.get("user_id"),
        }
    return JSONResponse(sessions)


@protected_route(router.delete, "/sessions", [Scope.ROMS_READ])
async def force_release_all(request: Request) -> JSONResponse:
    """Force-release all active sessions."""
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Map container keys back to configs so each broker can be told to stop -
    # deleting only the Redis keys would leave the games running.
    containers_by_key = {
        _container_key(c): c
        for c in _get_streaming_config().get("containers", [])
        if isinstance(c, dict)
    }

    released = []
    async for key in async_cache.scan_iter(match=f"{_SESSION_KEY_PREFIX}*"):
        await async_cache.delete(key)
        # scan_iter yields bytes unless the client decodes responses.
        key_str = key.decode() if isinstance(key, bytes) else key
        container_key = key_str.removeprefix(_SESSION_KEY_PREFIX)
        container = containers_by_key.get(container_key)
        if container is not None:
            # Best-effort stop; a broker error must not abort the sweep.
            await asyncio.to_thread(_stop_broker, container)
        released.append(container_key)
    log.info("all sessions force-released by admin, %s", released)
    return JSONResponse({"status": "released", "platforms": released})
