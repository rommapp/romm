import asyncio
import base64
import io
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from email.message import Message
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, TypedDict
from urllib.parse import quote, urljoin, urlparse, urlunparse

from fastapi import Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from config import (
    LIBRARY_BASE_PATH,
    STREAMING_BROKER_SECRET,
    STREAMING_SAVE_TIMEOUT,
    STREAMING_STATE_HISTORY_LIMIT,
)
from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import (
    db_container_adoption_handler,
    db_memory_card_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from handler.filesystem import fs_asset_handler
from handler.play_session_handler import ingest_play_sessions
from handler.redis_handler import async_cache
from handler.scan_handler import scan_save, scan_screenshot, scan_state
from handler.socket_handler import socket_handler
from models.assets import MemoryCard, State
from models.rom import Rom
from models.user import Role, User
from utils.filesystem import sanitize_filename
from utils.memory_cards import (
    MEMORY_CARD_MAX_BYTES,
    content_hash_of_bytes,
    store_memory_card_version,
)
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
# calls (save-state / volume / mute / save-and-exit) and the heartbeat
# refresh the TTL so a session in active use never expires.
SESSION_TTL_SECONDS = 6 * 60 * 60

# When save-and-exit runs with wait=false the broker is still killing the
# emulator in the background when the route returns. A short drain TTL
# keeps the key briefly so a concurrent new claim can't /launch on top of
# a not-yet-dead emulator (which would lose the in-flight save). The key
# expires on its own; no explicit DELETE.
SESSION_DRAIN_SECONDS = 5

# A live player refreshes `last_seen` roughly every 30s (frontend heartbeat,
# piggybacked on the activity interval). A session whose stamp is older than
# this is abandoned (tab closed, browser crashed, network gone) and the next
# claim may tear it down and take the container over. Generous enough to ride
# out background-tab timer throttling (browsers wake timers at least once a
# minute).
_SESSION_STALE_SECONDS = 180


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


def _session_is_stale(session: dict[str, Any]) -> bool:
    """True when the owner's heartbeat stopped long enough ago that the session
    counts as abandoned. Sessions written before heartbeats existed carry no
    `last_seen`; their `claimed_at` stands in. An unparseable stamp counts as
    stale so a corrupt record cannot wedge the container."""
    stamp = session.get("last_seen") or session.get("claimed_at")
    if not isinstance(stamp, str):
        return True
    try:
        seen = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - seen).total_seconds()
    return age > _SESSION_STALE_SECONDS


# ── Termination notices ───────────────────────────────────────────────────────

# An admin force-release deletes the session key, but the displaced player's
# browser is still showing a stream that no longer exists. A tombstone keyed by
# container and displaced user lets their next poll say who ended it and why,
# instead of the picture simply stopping. Cleared when that user claims again;
# the TTL covers the case where they never come back.
_TERMINATION_KEY_PREFIX = "romm:streaming:terminated:"
_TERMINATION_TTL_SECONDS = 15 * 60


def _termination_redis_key(session_key: str, user_id: int) -> str:
    return f"{_TERMINATION_KEY_PREFIX}{session_key}:{user_id}"


async def _record_termination(
    session: dict[str, Any],
    session_key: str,
    *,
    ended_by: str | None,
    reason: str | None,
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
    }
    await async_cache.set(
        _termination_redis_key(session_key, user_id),
        json.dumps(notice),
        ex=_TERMINATION_TTL_SECONDS,
    )
    # Best-effort: the poll is the source of truth and covers a missed or
    # dropped push, so a socket error here must not fail the release itself.
    try:
        await socket_handler.socket_server.emit(
            "streaming:session-ended", notice, room=f"user:{user_id}"
        )
    except Exception:  # noqa: BLE001
        log.warning("Failed to push session-ended notice", exc_info=True)


async def _get_termination(session_key: str, user_id: int) -> dict[str, Any] | None:
    raw = await async_cache.get(_termination_redis_key(session_key, user_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        await async_cache.delete(_termination_redis_key(session_key, user_id))
        return None


async def _clear_termination(session_key: str, user_id: int) -> None:
    await async_cache.delete(_termination_redis_key(session_key, user_id))


async def _session_status(platform: str, request: Request) -> dict[str, Any]:
    """Whether the caller still holds this platform's session, and if not, why
    it ended. Read-only, so it is safe to poll."""
    candidates = _containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )
    if await _find_session_for_user(candidates, request.user.id) is not None:
        return {"status": "active", "platform": platform}
    # The tombstone is keyed per container, so with a pool the caller's notice
    # can sit under any of them.
    termination = None
    for candidate in candidates:
        termination = await _get_termination(_container_key(candidate), request.user.id)
        if termination is not None:
            break
    return {
        "status": "ended",
        "platform": platform,
        "termination": termination,
    }


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


def _parse_stream_host(host: str) -> str | None:
    """Validate a configured stream host: an absolute URL, or a path when the
    container is reverse proxied onto RomM's own origin (`/streaming`). The
    browser resolves a path against whatever origin it is already on, which is
    what makes the iframe same origin and its pointer events reachable."""
    host = host.strip()
    if host.startswith("/"):
        return host.rstrip("/") or "/"
    return _parse_host_url(host)


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
    autosave_slot: int  # that slot's index, 0 if none
    has_memory_card: bool  # whether the broker serves a whole-card /memory-card


# Keyed by platform slug (lowercase). A platform absent here gets no save-state
# UI until its broker's slot semantics are known.
_PLATFORM_CAPABILITIES: dict[str, PlatformCapabilities] = {
    # Dolphin (ngc, wii, wiiu): slots 1-7 manual, slot 8 autosave. Only the
    # GameCube side has a memory card; Wii and Wii U saves live in NAND and
    # round-trip through /save-file instead.
    "ngc": {
        "max_slots": 7,
        "has_autosave": True,
        "autosave_slot": 8,
        "has_memory_card": True,
    },
    "wii": {
        "max_slots": 7,
        "has_autosave": True,
        "autosave_slot": 8,
        "has_memory_card": False,
    },
    "wiiu": {
        "max_slots": 7,
        "has_autosave": True,
        "autosave_slot": 8,
        "has_memory_card": False,
    },
    # PCSX2 (ps2): slots 1-9 manual, slot 10 autosave.
    "ps2": {
        "max_slots": 9,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": True,
    },
    # xemu (xbox) keeps the emulated HDD in raw format so its FATX partition
    # can be read directly, and a raw image cannot hold QEMU snapshots. No
    # states at all, so the launch screen reports the save instead of
    # offering slots. Saves round-trip through /save-file, not /memory-card.
    "xbox": {
        "max_slots": 0,
        "has_autosave": False,
        "autosave_slot": 0,
        "has_memory_card": False,
    },
}

_NO_CAPABILITIES: PlatformCapabilities = {
    "max_slots": 0,
    "has_autosave": False,
    "autosave_slot": 0,
    "has_memory_card": False,
}

# Keyed by emulator, consulted when the platform itself is not listed above.
# RetroArch serves dozens of platforms from one container and the operator
# picks which in their config, so enumerating them here would be a second copy
# of the broker's core table that goes stale the moment the broker gains a
# platform.
_EMULATOR_CAPABILITIES: dict[str, PlatformCapabilities] = {
    # The webstation broker resolves every state route to a single working
    # slot, since RomM is the library of states. There is no grid to pick
    # from, just the one slot save and resume both land in.
    "retroarch": {
        "max_slots": 0,
        "has_autosave": True,
        "autosave_slot": 10,
        "has_memory_card": False,
    },
}


def _configured_emulator(platform: str) -> str:
    """The emulator a configured container serves this platform with, if any."""
    for container in _get_streaming_config().get("containers", []):
        if str(container.get("platform", "")).lower() == platform:
            return _emulator_for_container(container)
    return ""


def platform_capabilities(platform: str) -> PlatformCapabilities:
    """Save-state capabilities for a platform slug, or a no-slots default.

    A platform listed explicitly wins, so a platform served by more than one
    emulator keeps the semantics its own entry describes.
    """
    platform = platform.lower()
    if platform in _PLATFORM_CAPABILITIES:
        return _PLATFORM_CAPABILITIES[platform]
    return _EMULATOR_CAPABILITIES.get(_configured_emulator(platform), _NO_CAPABILITIES)


def _known_to_lack_memory_card(platform: str) -> bool:
    """True only for a platform listed above as having no memory card.

    An unlisted platform is unknown, not cardless. The operator opted in and
    their broker may well serve /memory-card, so the flag is honoured there.
    """
    capabilities = _PLATFORM_CAPABILITIES.get(platform.lower())
    return capabilities is not None and not capabilities["has_memory_card"]


# Coarse request-body bound, derived from the table so the slot range lives in
# exactly one place. The per-platform check in the routes is the tighter,
# authoritative guard; this just rejects obviously out-of-range input up front.
_MAX_SLOT = max(
    (
        max(c["max_slots"], c["autosave_slot"])
        for c in (*_PLATFORM_CAPABILITIES.values(), *_EMULATOR_CAPABILITIES.values())
    ),
    default=1,
)


def _assert_valid_slot(platform: str, slot: int) -> None:
    """Reject a slot the platform does not expose before hitting the broker."""
    caps = platform_capabilities(platform)
    valid = 1 <= slot <= caps["max_slots"]
    if caps["has_autosave"] and slot == caps["autosave_slot"]:
        valid = True
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"Slot {slot} is not available for platform '{platform}'",
        )


class ClaimSessionRequest(BaseModel):
    rom_id: Annotated[int, Field(ge=1)]
    # Optional state to resume from: the backend pushes its file to the broker
    # before launch and the broker loads its slot once the game is up. Must be
    # the claiming user's own state or a public one shared by another user.
    state_id: Annotated[int, Field(ge=1)] | None = None
    # Optional memory card to mount (whole-card sync containers only). Omitted =
    # the user's most-recently-used card for the emulator, or a fresh one on
    # first play. Must be one the claiming user owns.
    memory_card_id: Annotated[int, Field(ge=1)] | None = None
    # Answer to the one-time import prompt on a container whose pre-existing
    # card has never been adopted. "adopt" keeps it, "discard" wipes it, and
    # "discard" doubles as the override for a card that could not be read.
    card_import: Literal["adopt", "discard"] | None = None


class SaveAndExitRequest(BaseModel):
    slot: Annotated[int, Field(ge=0, le=10)] = 0
    wait: bool = True


class VolumeRequest(BaseModel):
    level: Annotated[int, Field(ge=0, le=100)]


class MuteRequest(BaseModel):
    mute: bool | None = None  # None = toggle, True/False = explicit set


class SaveStateRequest(BaseModel):
    # Coarse union bound (widest is the autosave slot); the route validates the
    # exact per-platform ceiling against _PLATFORM_CAPABILITIES.
    slot: Annotated[int, Field(ge=1, le=_MAX_SLOT)] = 1


class LoadStateRequest(BaseModel):
    # Coarse union bound (widest is the autosave slot); the route validates the
    # exact per-platform ceiling against _PLATFORM_CAPABILITIES.
    slot: Annotated[int, Field(ge=1, le=_MAX_SLOT)] = 1


class DesktopSessionRequest(BaseModel):
    # The container to open, named by the key GET /streaming/containers
    # reports. Named rather than pooled: an admin configuring a container
    # needs that one, not whichever is free.
    container: Annotated[str, Field(min_length=1, max_length=300)]


def _expand_containers(entries: Any) -> list[dict[str, Any]]:
    """One entry per (container, platform).

    A container declaring `platforms` yields a copy per platform with
    `platform` and `emulator` filled in; a flat entry yields itself. Every copy
    keeps the same host, so `_container_key` collapses them back into the one
    session the container can actually serve.
    """
    expanded: list[dict[str, Any]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue

        platforms = entry.get("platforms")
        if platforms is None:
            expanded.append(entry)
            continue
        if not isinstance(platforms, dict):
            log.warning(
                "container `platforms` must be a map of platform to emulator, "
                "skipping: %s",
                entry,
            )
            continue
        if entry.get("platform"):
            log.warning(
                "container declares both `platform` and `platforms`, "
                "serving `platforms` only: %s",
                entry,
            )

        base = {k: v for k, v in entry.items() if k != "platforms"}
        for platform, emulator in platforms.items():
            if not isinstance(platform, str) or not platform.strip():
                log.warning(
                    "container platform key is not a name, skipping: %r", platform
                )
                continue
            if not isinstance(emulator, str) or not emulator.strip():
                # The emulator names the state and card namespace, so guessing
                # one would file this platform's saves under another container.
                log.warning(
                    "container platform '%s' has no emulator, skipping", platform
                )
                continue
            expanded.append(
                {**base, "platform": platform.strip(), "emulator": emulator.strip()}
            )
    return expanded


def _get_streaming_config() -> dict[str, Any]:
    """Extract streaming config from the parsed Config object"""
    cfg = cm.get_config()

    return {
        "enabled": cfg.STREAMING_ENABLED,
        "containers": _expand_containers(cfg.STREAMING_CONTAINERS),
    }


def _interchangeable(first: dict[str, Any], other: dict[str, Any]) -> bool:
    """Whether two containers serving a platform are a pool rather than two
    different setups. The emulator names the state and card namespace, and
    whole-card sync decides whether cards are synced at all, so a player landing
    on either container has to find their saves in the same place."""
    return _emulator_for_container(first) == _emulator_for_container(
        other
    ) and _memory_card_sync_enabled(first) == _memory_card_sync_enabled(other)


def _containers_for_platform(platform: str) -> list[dict[str, Any]]:
    """Every container serving a platform, in config order.

    More than one entry is a pool and the claim takes the first free one.
    Config order is deliberate: the head of the list stays warm (shader caches,
    BIOS, memory cards) instead of players spreading across cold containers.
    """
    cfg = _get_streaming_config()
    if not cfg.get("enabled", False):
        return []
    lower = platform.lower()
    candidates: list[dict[str, Any]] = []
    for entry in cfg.get("containers", []):
        if not isinstance(entry, dict):
            continue
        # An entry needs a platform and a host that is either scheme bearing
        # or a proxied path. Skipping a malformed entry here means claim /
        # control routes raise a clean 404 instead of a 500 on container["host"].
        if entry.get("platform", "").lower() != lower:
            continue
        if not _parse_stream_host(entry.get("host", "")):
            log.warning(
                "container for platform '%s' missing a scheme-bearing host "
                "or a proxied path, skipping: %s",
                platform,
                entry,
            )
            continue
        if not _derive_broker_host(entry):
            # A proxied host carries no address RomM can call, so the broker
            # is only reachable if the operator named it.
            log.warning(
                "container for platform '%s' has no reachable broker, set "
                "broker_host, skipping: %s",
                platform,
                entry,
            )
            continue
        if entry.get("memory_card_sync", False) and _known_to_lack_memory_card(lower):
            log.warning(
                "container for platform '%s' sets memory_card_sync but that "
                "platform has no memory card, ignoring the flag and syncing "
                "individual save files instead",
                platform,
            )
        if candidates and not _interchangeable(candidates[0], entry):
            log.warning(
                "container for platform '%s' disagrees with the first one on "
                "emulator or memory card sync, so it is not a pool member, "
                "skipping: %s",
                platform,
                entry,
            )
            continue
        candidates.append(entry)
    return candidates


def _containers_by_key() -> dict[str, list[dict[str, Any]]]:
    """Configured containers grouped by key. A container serving several
    platforms expands into one entry per platform, all sharing one key."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in _get_streaming_config().get("containers", []):
        if isinstance(entry, dict):
            grouped.setdefault(_container_key(entry), []).append(entry)
    return grouped


def _container_for_session(
    grouped: dict[str, list[dict[str, Any]]], container_key: str, platform: Any
) -> dict[str, Any] | None:
    """The config entry a session was claimed under. Entries sharing a key
    differ in the platform-keyed fields (emulator, card sync), so picking an
    arbitrary one would file the session's saves under another platform."""
    entries = grouped.get(container_key)
    if not entries:
        return None
    if isinstance(platform, str):
        lower = platform.lower()
        for entry in entries:
            if entry.get("platform", "").lower() == lower:
                return entry
    return entries[0]


async def _find_session_for_user(
    candidates: list[dict[str, Any]], user_id: int
) -> tuple[dict[str, Any], str, dict[str, Any]] | None:
    """The candidate holding this user's session, as (container, key, session).

    With a pool the platform no longer identifies the container, the session
    does. A drain marker records no user, so it never matches.
    """
    for candidate in candidates:
        session_key = _container_key(candidate)
        session = await _get_session(session_key)
        if session is not None and session.get("user_id") == user_id:
            return candidate, session_key, session
    return None


async def _resolve_named_container(
    platform: str, container_key: str
) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    """One named container serving a platform, plus whatever session it holds.

    Returns (container, session_key, session), the session being None when the
    container is free or draining. Raises 404 when the key names no container
    serving this platform.
    """
    for candidate in _containers_for_platform(platform):
        session_key = _container_key(candidate)
        if session_key != container_key:
            continue
        session = await _get_session(session_key)
        if session is not None and session.get("draining"):
            session = None
        return candidate, session_key, session
    raise HTTPException(
        status_code=404,
        detail=f"No streaming container '{container_key}' for platform '{platform}'",
    )


async def _resolve_owned_session(
    platform: str, request: Request
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Find the caller's session among the platform's containers.

    Returns (container, session_key, session). Raises 404 when the platform has
    no configured container or nothing is active, 403 when every active session
    belongs to someone else, 409 when an admin's fallback is ambiguous.
    """
    candidates = _containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )

    others: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for candidate in candidates:
        session_key = _container_key(candidate)
        session = await _get_session(session_key)
        if session is None or session.get("draining"):
            continue
        if session.get("user_id") == request.user.id:
            return candidate, session_key, session
        others.append((candidate, session_key, session))

    if not others:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )
    # An admin may control a session they do not own, but the scan found none of
    # theirs, so fall back to the platform's active session. A pool can hold
    # several and the path does not say which, so the caller has to name one.
    if request.user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403, detail="Session is claimed by another user"
        )
    if len(others) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{len(others)} sessions are active on platform '{platform}', "
                "name a container instead"
            ),
        )
    return others[0]


# ── Broker communication ──────────────────────────────────────────────────────

# Broker HTTP deadlines, grouped by what the call actually waits on:
#   ACK        - the broker only acknowledges; the work runs async on its side
#   LAUNCH     - process spawn + config patch + window setup
#   LOAD_STATE - worst case 9 slot cycles x ~5s xdotool timeout
#   TRANSFER   - save archive and memory card transfers; state transfers use
#     their own per-emulator deadline, see _STATE_TRANSFER_LIMITS
#   CARD_HYDRATE / CARD_TEARDOWN - whole-card push at claim / pull at exit;
#     hydration may wait on a slow first-run card format, teardown must not
#     hold a closing session hostage for two minutes
_BROKER_ACK_TIMEOUT = 5
_BROKER_LAUNCH_TIMEOUT = 10
_BROKER_LOAD_STATE_TIMEOUT = 60
_BROKER_TRANSFER_TIMEOUT = 60
_CARD_HYDRATE_TIMEOUT = 120
_CARD_TEARDOWN_TIMEOUT = 30


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


def _broker_headers(container: dict[str, Any]) -> dict[str, str]:
    """Auth headers for a broker call, empty when no secret is configured.
    Returns a fresh dict so callers can add their own headers to it."""
    secret = _broker_secret(container)
    return {"X-Broker-Secret": secret} if secret else {}


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
    headers = _broker_headers(container)
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


def _broker_get_binary(
    container: dict[str, Any],
    path: str,
    *,
    max_bytes: int,
    timeout: float,
) -> tuple[Message, bytes]:
    """
    GET a binary body from the broker, returning (response headers, content).
    Headers come back because some routes carry metadata there. Raises the
    underlying urllib/OS error, or ValueError for an empty or oversized body.
    """
    req = urllib.request.Request(
        _broker_url(container, path),
        method="GET",
        headers=_broker_headers(container),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        headers = resp.headers
        content = resp.read(max_bytes + 1)
    if not content:
        raise ValueError("broker returned an empty body")
    if len(content) > max_bytes:
        raise ValueError("broker response exceeds size limit")
    return headers, content


def _broker_get_binary_safe(
    container: dict[str, Any],
    path: str,
    label: str,
    *,
    max_bytes: int,
    timeout: float,
) -> tuple[Message, bytes] | None:
    """
    Best-effort variant of _broker_get_binary: returns None instead of raising.
    A 404 is a normal answer on these routes (no state in the slot, no new
    saves, no captured frame), so it is not logged.
    """
    try:
        return _broker_get_binary(container, path, max_bytes=max_bytes, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            log.warning("broker %s failed, HTTP %d", label, exc.code)
        return None
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        return None


def _broker_put_binary_json(
    container: dict[str, Any],
    path: str,
    content: bytes,
    label: str,
    *,
    content_type: str,
    timeout: float,
) -> dict[str, Any] | None:
    """
    PUT a binary body to the broker and return its parsed JSON reply, or None
    on failure. Best-effort, logs but never raises.
    """
    req = urllib.request.Request(
        _broker_url(container, path),
        data=content,
        method="PUT",
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
            **_broker_headers(container),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = json.loads(resp.read())
        return body if isinstance(body, dict) else {}
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        return None


def _broker_put_binary(
    container: dict[str, Any],
    path: str,
    content: bytes,
    label: str,
    *,
    content_type: str,
    timeout: float,
) -> bool:
    """PUT a binary body to the broker, reporting whether it acked with ok."""
    body = _broker_put_binary_json(
        container, path, content, label, content_type=content_type, timeout=timeout
    )
    return bool(body and body.get("status") == "ok")


def _call_broker(
    container: dict[str, Any],
    rom_path: str,
    rom_name: str,
    load_slot: int | None = None,
) -> dict[str, Any]:
    """
    POST to the broker's /launch endpoint to tell the emulator container to
    load a ROM.

    With load_slot set the broker loads that save-state slot once the game
    is up (resume-from-state). Raises HTTPException if the broker is
    unreachable or returns an error. Returns the parsed launch response body.
    """
    url = _broker_url(container, "/launch")
    body: dict[str, Any] = {"rom_path": rom_path, "rom_name": rom_name}
    if load_slot is not None:
        body["load_slot"] = load_slot
    try:
        resp = _broker_request(
            container, "/launch", body=body, timeout=_BROKER_LAUNCH_TIMEOUT
        )
        log.info("broker launched ROM, %s", resp)
        return resp if isinstance(resp, dict) else {}
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
) -> tuple[bool, int]:
    """
    POST /save-and-exit to the broker. Best-effort, logs but never raises.
    With wait=True the call blocks until save+kill completes (use for button press).
    With wait=False the broker fires save+kill in the background (use for navigation away).
    Returns (saved, slot). Brokers resolve slot 0 to their default autosave
    slot and echo the effective slot back, which the state sync needs to pull
    the right file afterwards.
    """
    # Waiting brokers can legitimately block for a while: rpcs3 polls the
    # savestate write for up to SAVE_WAIT (30s default) and xemu's QMP
    # save + reset path can approach that too. Time out past the slowest
    # broker so a slow-but-successful save is not reported as saved=False.
    # Overridable for operators who raise SAVE_WAIT on a broker.
    if _is_webstation(container):
        # No background variant on this protocol: exit always runs the save,
        # the teardown and the save dump together before it answers.
        report = _webstation_exit(container, slot)
        saved = bool(report and report.get("state_saved", False))
        effective_slot = slot
        if report is not None and isinstance(report.get("state_slot"), int):
            effective_slot = report["state_slot"]
        log.info("broker exit, saved=%s slot=%d", saved, effective_slot)
        return saved, effective_slot

    body = _broker_request_safe(
        container,
        "/save-and-exit",
        "save-and-exit",
        body={"slot": slot, "wait": wait},
        timeout=STREAMING_SAVE_TIMEOUT if wait else _BROKER_ACK_TIMEOUT,
    )
    saved = bool(body and body.get("saved", False))
    effective_slot = slot
    if body is not None and isinstance(body.get("slot"), int):
        effective_slot = body["slot"]
    log.info(
        "broker save-and-exit, saved=%s slot=%d wait=%s", saved, effective_slot, wait
    )
    return saved, effective_slot


def _volume_broker(container: dict[str, Any], level: int) -> bool:
    """POST /volume to the broker. Best-effort, logs but never raises."""
    body = _broker_request_safe(
        container,
        "/volume",
        "volume",
        body={"level": level},
        timeout=_BROKER_ACK_TIMEOUT,
    )
    return bool(body and body.get("status") == "ok")


def _mute_broker(container: dict[str, Any], mute: bool | None) -> bool | None:
    """POST /mute to the broker. Returns confirmed mute state, or None on error."""
    body = _broker_request_safe(
        container,
        "/mute",
        "mute",
        body={} if mute is None else {"mute": mute},
        timeout=_BROKER_ACK_TIMEOUT,
    )
    return body.get("mute") if body is not None else None


def _save_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /save-state to the broker. Returns True if the request was accepted."""
    if _is_webstation(container):
        # Synchronous on this protocol: the broker answers once the emulator
        # acked the write, so it needs the same budget as the exit save.
        body = _broker_request_safe(
            container,
            _webstation_path(container, "/save-state"),
            "save-state",
            body={"slot": slot},
            timeout=STREAMING_SAVE_TIMEOUT,
        )
        return bool(body and body.get("saved", False))

    body = _broker_request_safe(
        container,
        "/save-state",
        "save-state",
        body={"slot": slot},
        timeout=_BROKER_ACK_TIMEOUT,
    )
    return bool(body and body.get("status") == "saving")


def _load_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /load-state to the broker. Returns True if broker confirmed success."""
    if _is_webstation(container):
        body = _broker_request_safe(
            container,
            _webstation_path(container, "/load-state"),
            "load-state",
            body={"slot": slot},
            timeout=_BROKER_LOAD_STATE_TIMEOUT,
        )
        return bool(body and body.get("loaded", False))

    # Timeout covers the worst case: 9 slot cycles x ~5s xdotool timeout.
    body = _broker_request_safe(
        container,
        "/load-state",
        "load-state",
        body={"slot": slot},
        timeout=_BROKER_LOAD_STATE_TIMEOUT,
    )
    return bool(body and body.get("loaded", False))


def _stop_broker(container: dict[str, Any]) -> int | None:
    """Tell the broker to stop emulator. Best-effort, don't raise on failure.

    Returns the slot a state was captured in, or None when none was. Stopping
    the webstation broker runs its exit, which saves, so the caller is left
    holding the only reference to that state. The others stop without saving.
    """
    if _is_webstation(container):
        report = _webstation_exit(container, slot=0)
        if report and report.get("state_saved"):
            slot = report.get("state_slot")
            return slot if isinstance(slot, int) else None
        return None
    _broker_request_safe(
        container, "/launch", "stop", method="DELETE", timeout=_BROKER_ACK_TIMEOUT
    )
    return None


# ── Webstation broker protocol ────────────────────────────────────────────────
#
# One webstation container replaces the per-emulator mods, and its contract
# differs enough to need translating. It hosts a single session behind a
# subfolder; activate carries the user, the rom and the save data in one body;
# and exit does the save state, the teardown and the save dump together.
#
# The awkward part is save transfer. Activate names the restore archive by
# container path, but RomM holds bytes and runs on another host, so an archive
# is uploaded first and the path it returns is what activate gets. On the way
# out the broker pushes to a callback, which is unreachable in dev mode and
# lost on a failed push, so RomM pulls from the export list instead and deletes
# what it stored.
#
# Save states round-trip through the same /state-file routes as the other
# brokers, just under the subfolder, so RomM holds the library either way. The
# difference is that this broker keeps one working slot instead of ten: a slot
# sent to it resolves to that one, and a pushed state is only accepted while a
# session is up. Reads outlive the session, because exit captures a state and
# RomM can only come back for it once the teardown has answered. What is still
# missing here is volume, mute and whole-card sync.


def _is_webstation(container: dict[str, Any]) -> bool:
    return str(container.get("protocol", "")).strip().lower() == "webstation"


def _broker_session_id(session: dict[str, Any]) -> str | None:
    """The id activate gave the broker, absent on sessions claimed before it."""
    value = session.get("broker_session_id")
    return str(value) if value else None


def _webstation_path(container: dict[str, Any], path: str) -> str:
    """Prefix a session route with the container's SUBFOLDER."""
    subfolder = str(container.get("subfolder", "/streaming")).strip()
    if not subfolder.startswith("/"):
        subfolder = f"/{subfolder}"
    return f"{subfolder.rstrip('/')}/api/session{path}"


def _container_capabilities(container: dict[str, Any]) -> PlatformCapabilities:
    """The save-state controls the frontend may offer for this container."""
    return platform_capabilities(str(container.get("platform", "")))


def _webstation_activate(
    container: dict[str, Any],
    *,
    session_id: str,
    user: User,
    emulator: str,
    rom: dict[str, Any] | None = None,
    archive_path: str | None = None,
    resume_slot: int | None = None,
    memory_card_synced: bool = False,
) -> dict[str, Any]:
    """POST /activate. Raises HTTPException the same way _call_broker does.

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
    }
    if rom is not None:
        body["rom"] = rom
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

    path = _webstation_path(container, "/activate")
    try:
        resp = _broker_request(
            container, path, body=body, timeout=_BROKER_LAUNCH_TIMEOUT
        )
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        log.error("broker HTTP error %d: %s", exc.code, error_body)
        try:
            detail = json.loads(error_body)
        except Exception:
            detail = error_body
        raise HTTPException(
            status_code=502, detail=f"Broker returned {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        url = _broker_url(container, path)
        log.error("broker unreachable at %s: %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not reach the webstation broker at {url}. "
                "Check that the container is running and its broker port is "
                "reachable from the RomM host."
            ),
        ) from exc

    resp = resp if isinstance(resp, dict) else {}
    log.info("broker activated session, %s", resp)
    return resp


def _webstation_exit(container: dict[str, Any], slot: int) -> dict[str, Any] | None:
    """POST /exit. Best-effort, the caller is already tearing the session down.

    Slot 0 means the caller has no opinion, so the broker's own default stands.
    """
    query = f"?slot={slot}" if slot else ""
    body = _broker_request_safe(
        container,
        _webstation_path(container, f"/exit{query}"),
        "exit",
        timeout=STREAMING_SAVE_TIMEOUT,
    )
    return body if isinstance(body, dict) else None


def _webstation_upload_archive(
    container: dict[str, Any], name: str, content: bytes
) -> str | None:
    """PUT a save archive and return the container path activate wants."""
    body = _broker_put_binary_json(
        container,
        _webstation_path(container, f"/imports/{quote(name)}"),
        content,
        "archive upload",
        content_type="application/zip",
        timeout=_BROKER_TRANSFER_TIMEOUT,
    )
    if not body or not body.get("path"):
        return None
    return str(body["path"])


def _webstation_exports(container: dict[str, Any]) -> list[dict[str, Any]]:
    """Save archives waiting on the container, newest first."""
    body = _broker_request_safe(
        container,
        _webstation_path(container, "/exports"),
        "export list",
        method="GET",
        timeout=_BROKER_ACK_TIMEOUT,
    )
    exports = body.get("exports") if isinstance(body, dict) else None
    return exports if isinstance(exports, list) else []


def _webstation_collect_export(container: dict[str, Any], name: str) -> bytes | None:
    """Download one archive and drop the container's copy once it is in hand."""
    result = _broker_get_binary_safe(
        container,
        _webstation_path(container, f"/exports/{quote(name)}"),
        "export download",
        max_bytes=_SAVE_FILE_MAX_BYTES,
        timeout=_BROKER_TRANSFER_TIMEOUT,
    )
    if result is None:
        return None
    _broker_request_safe(
        container,
        _webstation_path(container, f"/exports/{quote(name)}"),
        "export delete",
        method="DELETE",
        timeout=_BROKER_ACK_TIMEOUT,
    )
    return result[1]


# ── Save-state sync ───────────────────────────────────────────────────────────
#
# Emulator save states are centralized through RomM's states asset store so
# they survive container rebuilds and roam across containers. The backend is
# the only file mover: after a save it pulls the state file from the broker
# and stores it under the session user's assets; on claim it pushes the user's
# stored states back down so the container slots always reflect the central
# copy (last write wins, central copy is the source of truth).
#
# Broker file API (secret-protected, stdlib on the broker side):
#   GET /state-file?slot=N   - newest state file for slot N. Blocks while a
#                              save is in flight, so no clock coupling between
#                              hosts. Returns raw bytes + X-State-Filename.
#   PUT /state-file?filename=NAME - write NAME into the emulator's state dir.

# State transfer limits, keyed by emulator. Most savestates are a RAM plus VRAM
# snapshot of tens of MB, but xemu's state is the whole Xbox hard disk image and
# zips to hundreds of MB even after trimming. Size and deadline live together so
# a state that clears one is not rejected by the other.


class StateTransferLimits(TypedDict):
    max_bytes: int  # largest state body exchanged with the broker
    timeout: int  # seconds allowed for that body, in either direction


_DEFAULT_STATE_TRANSFER: StateTransferLimits = {
    "max_bytes": 256 * 1024 * 1024,
    "timeout": _BROKER_TRANSFER_TIMEOUT,
}

# Keyed by emulator name as _emulator_for_container returns it (lowercase).
_STATE_TRANSFER_LIMITS: dict[str, StateTransferLimits] = {
    # The xemu broker caps its expanded hard disk image at 2 GiB, and transfers
    # run around 18 MB/s, so a full-size archive needs minutes, not seconds.
    "xemu": {"max_bytes": 2 * 1024 * 1024 * 1024, "timeout": 240},
}


def _state_transfer_limits(container: dict[str, Any]) -> StateTransferLimits:
    return _STATE_TRANSFER_LIMITS.get(
        _emulator_for_container(container), _DEFAULT_STATE_TRANSFER
    )


# Pull retries cover the window between the broker accepting a save and the
# emulator finishing the write (PINE/xdotool waits run up to ~15s per broker).
_STATE_PULL_ATTEMPTS = 5
_STATE_PULL_RETRY_DELAY = 3.0

# Strong references to fire-and-forget sync tasks so the event loop does not
# garbage-collect them mid-flight.
_sync_tasks: set[asyncio.Task] = set()


def _spawn_sync_task(coro: Any) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _sync_tasks.add(task)
    task.add_done_callback(_sync_tasks.discard)


def _emulator_for_container(container: dict[str, Any]) -> str:
    """Namespace for stored states, e.g. 'pcsx2'.

    An explicit `emulator` key on the container config wins; otherwise the
    label (or platform slug) lowercased. Keeps streaming states separate from
    EmulatorJS states for the same ROM.
    """
    emulator = (
        container.get("emulator")
        or container.get("label")
        or container.get("platform")
        or ""
    )
    return str(emulator).strip().lower()


def _transfer_route(container: dict[str, Any], path: str) -> str:
    """Where a state or memory card transfer lives on this container's broker.

    The webstation broker serves the same routes, only under its subfolder.
    """
    return _webstation_path(container, path) if _is_webstation(container) else path


def _fetch_state_file(container: dict[str, Any], slot: int) -> tuple[str, bytes] | None:
    """GET /state-file from the broker. Returns (filename, content) or None.

    The broker blocks while a save is in flight, so a generous timeout stands
    in for save-completion polling. 404 means no state exists for the slot.
    """
    limits = _state_transfer_limits(container)
    result = _broker_get_binary_safe(
        container,
        _transfer_route(container, f"/state-file?slot={slot}"),
        "state-file GET",
        max_bytes=limits["max_bytes"],
        timeout=limits["timeout"],
    )
    if result is None:
        return None
    headers, content = result
    filename = headers.get("X-State-Filename", "")
    if not filename:
        log.warning("broker state-file response missing a filename")
        return None
    return filename, content


def _push_state_file(container: dict[str, Any], filename: str, content: bytes) -> bool:
    """PUT /state-file to the broker. Best-effort, logs but never raises."""
    return _broker_put_binary(
        container,
        _transfer_route(container, f"/state-file?filename={quote(filename, safe='')}"),
        content,
        "state-file PUT",
        content_type="application/octet-stream",
        timeout=_state_transfer_limits(container)["timeout"],
    )


# PCSX2 embeds a PNG of the moment of save inside every .p2s savestate zip
# under this entry name (pcsx2/SaveState.cpp: EntryFilename_Screenshot).
# Extracting it gives each pulled state a thumbnail with no broker round-trip,
# mirroring how in-browser EmulatorJS states carry a screenshot.
_STATE_SCREENSHOT_ZIP_ENTRY = "Screenshot.png"
_STATE_SCREENSHOT_MAX_BYTES = 16 * 1024 * 1024
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _extract_state_screenshot(emulator: str, state_content: bytes) -> bytes | None:
    """Pull the embedded frame PNG out of a savestate archive, or None when the
    format carries no embedded screenshot. Only PCSX2 (.p2s zip) embeds one;
    the others write the frame as its own file, served by /state-screenshot."""
    if emulator != "pcsx2":
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(state_content)) as zf:
            with zf.open(_STATE_SCREENSHOT_ZIP_ENTRY) as entry:
                data = entry.read(_STATE_SCREENSHOT_MAX_BYTES + 1)
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        # No screenshot entry, or the state is not a readable zip. Not fatal:
        # the state still syncs, it just has no thumbnail.
        log.warning("could not extract state screenshot, %s", exc)
        return None
    if not data or len(data) > _STATE_SCREENSHOT_MAX_BYTES:
        return None
    return data


_STATE_FRAME_KEY_PREFIX = "romm:streaming:frame:"
# Long enough to cover the broker's state write plus the pull retries, short
# enough that a frame never outlives the save it was captured for.
_STATE_FRAME_TTL_SECONDS = 120


def _state_frame_redis_key(user_id: int, rom_id: int) -> str:
    return f"{_STATE_FRAME_KEY_PREFIX}{user_id}:{rom_id}"


async def _stash_state_frame(user_id: int, rom_id: int, image: bytes) -> None:
    """Hold a browser-captured frame until the state it belongs to is pulled."""
    await async_cache.set(
        _state_frame_redis_key(user_id, rom_id),
        base64.b64encode(image),
        ex=_STATE_FRAME_TTL_SECONDS,
    )


async def _take_state_frame(user_id: int, rom_id: int) -> bytes | None:
    key = _state_frame_redis_key(user_id, rom_id)
    raw = await async_cache.get(key)
    await async_cache.delete(key)
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except (ValueError, TypeError):
        return None


def _fetch_state_screenshot(container: dict[str, Any], slot: int) -> bytes | None:
    """GET /state-screenshot from the broker, for emulators whose state files
    carry no frame of their own. A 404 is the normal "this broker does not
    capture frames" answer, so it is not logged."""
    result = _broker_get_binary_safe(
        container,
        _transfer_route(container, f"/state-screenshot?slot={slot}"),
        "state-screenshot GET",
        max_bytes=_STATE_SCREENSHOT_MAX_BYTES,
        timeout=_BROKER_TRANSFER_TIMEOUT,
    )
    return result[1] if result else None


async def _store_state_screenshot(
    user: User, rom: Rom, state_filename: str, image: bytes
) -> None:
    """Store a state screenshot so it binds to the state as its
    thumbnail. State.screenshot matches by filename stem, so the image reuses
    the state's stem with a .png extension. is_gallery stays False (the default)
    so it never shows in the user's screenshot gallery - it only helps the
    resume picker show the right frame. Mirrors the POST /api/states thumbnail
    path so streaming and in-browser states share one screenshots directory.
    """
    # Both sources are unverified bytes: a zip entry that only claims to be a
    # PNG, or whatever the broker returned. Guard here so one check covers both.
    if not image.startswith(_PNG_MAGIC):
        log.warning("state screenshot for %s is not a PNG, skipping", state_filename)
        return

    filename = sanitize_filename(f"{os.path.splitext(state_filename)[0]}.png")
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=rom.platform_slug, rom_id=rom.id
    )
    await fs_asset_handler.write_file(
        file=image, path=screenshots_path, filename=filename
    )
    scanned = await scan_screenshot(
        file_name=filename,
        user=user,
        platform_fs_slug=rom.platform_slug,
        rom_id=rom.id,
    )
    existing = db_screenshot_handler.get_screenshot(
        file_name=filename, rom_id=rom.id, user_id=user.id
    )
    if existing:
        db_screenshot_handler.update_screenshot(
            existing.id, {"file_size_bytes": scanned.file_size_bytes}
        )
    else:
        scanned.rom_id = rom.id
        scanned.user_id = user.id
        db_screenshot_handler.add_screenshot(screenshot=scanned)


def _user_states_for_emulator(user_id: int, rom_id: int, emulator: str) -> list[State]:
    """The user's states for this ROM and emulator, newest first."""
    states = [
        s
        for s in db_state_handler.get_states(user_id=user_id, rom_id=rom_id)
        if (s.emulator or "").lower() == emulator
    ]
    states.sort(key=lambda s: s.updated_at, reverse=True)
    return states


async def _is_duplicate_of_latest(latest: State | None, content: bytes) -> bool:
    """Whether ``content`` matches the most recent stored state byte for byte.

    Saving twice without playing in between is common (the exit autosave right
    after a manual save), and those captures are identical. Only the newest is
    compared: an older match is a genuine revisit of the same point.
    """
    if latest is None or latest.file_size_bytes != len(content):
        return False
    try:
        existing = await fs_asset_handler.read_file(
            f"{latest.file_path}/{latest.file_name}"
        )
    except FileNotFoundError:
        return False
    return existing == content


async def _prune_state_history(user: User, rom: Rom, emulator: str) -> int:
    """Delete the oldest states past the retention limit. Returns how many went.

    A file already gone from disk still loses its row, since a stale entry that
    no longer opens is worse than a missing file.
    """
    limit = STREAMING_STATE_HISTORY_LIMIT
    if limit <= 0:
        return 0
    states = _user_states_for_emulator(user.id, rom.id, emulator)
    stale = states[limit:]
    for state in stale:
        screenshot = state.screenshot
        db_state_handler.delete_state(state.id)
        try:
            await fs_asset_handler.remove_file(
                file_path=f"{state.file_path}/{state.file_name}"
            )
        except FileNotFoundError:
            log.warning("pruned state file already gone, %s", state.file_name)
        if screenshot is not None:
            db_screenshot_handler.delete_screenshot(screenshot.id)
            try:
                await fs_asset_handler.remove_file(
                    file_path=f"{screenshot.file_path}/{screenshot.file_name}"
                )
            except FileNotFoundError:
                log.warning(
                    "pruned screenshot file already gone, %s", screenshot.file_name
                )
    if stale:
        log.info(
            "pruned %d state(s) past the %d limit, rom=%s",
            len(stale),
            limit,
            rom.name,
        )
    return len(stale)


async def _store_state_asset(
    user: User,
    rom: Rom,
    emulator: str,
    filename: str,
    content: bytes,
    screenshot: bytes | None = None,
) -> None:
    """Store a pulled state file as a new entry in the ROM's state history.

    Each capture is kept rather than overwriting the slot it came from, so the
    player can resume from any earlier point. An unchanged capture is dropped
    and the oldest entries are pruned once the retention limit is reached.
    """
    history = _user_states_for_emulator(user.id, rom.id, emulator)
    if await _is_duplicate_of_latest(history[0] if history else None, content):
        log.info("state identical to the last capture, skipping, rom=%s", rom.name)
        return

    stamped = _stamped_state_filename(emulator, filename, datetime.now(timezone.utc))
    states_path = fs_asset_handler.build_states_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    await fs_asset_handler.write_file(file=content, path=states_path, filename=stamped)

    scanned_state = await scan_state(
        file_name=stamped,
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    db_state = db_state_handler.get_state_by_filename(
        user_id=user.id, rom_id=rom.id, file_name=stamped
    )
    if db_state:
        # Only reachable when the stamp collides, so the file on disk was just
        # overwritten and the row needs to agree with it.
        db_state_handler.update_state(
            db_state.id, {"file_size_bytes": scanned_state.file_size_bytes}
        )
    else:
        scanned_state.rom_id = rom.id
        scanned_state.user_id = user.id
        scanned_state.emulator = emulator
        db_state_handler.add_state(state=scanned_state)

    # Bind a thumbnail to the state so the resume picker shows the right frame.
    # Best-effort: a missing or unreadable screenshot must not fail the sync.
    if screenshot is not None:
        try:
            await _store_state_screenshot(user, rom, stamped, screenshot)
        except Exception:
            log.exception("failed to store state screenshot for %s", stamped)

    await _prune_state_history(user, rom, emulator)


async def _pull_state_to_library(
    user_id: int, rom_id: int, container: dict[str, Any], slot: int
) -> bool:
    """Background task: pull a freshly saved state from the broker and store it.

    Best-effort by design, a sync failure must never surface to the player,
    the state still exists inside the container.
    """
    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return False
    emulator = _emulator_for_container(container)

    for attempt in range(_STATE_PULL_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(_STATE_PULL_RETRY_DELAY)
        result = await asyncio.to_thread(_fetch_state_file, container, slot)
        if result is None:
            continue
        filename, content = result
        try:
            filename = sanitize_filename(filename)
        except ValueError:
            log.warning("broker returned invalid state filename")
            return False
        # The browser frame is preferred: it is what the player actually saw,
        # and capturing it never asks the emulator to read back its own
        # framebuffer, which is what deadlocks GPU-rendered cores. PCSX2 embeds
        # a frame in the state file; the rest write one beside it.
        screenshot = await _take_state_frame(user_id, rom_id)
        if screenshot is None:
            screenshot = _extract_state_screenshot(emulator, content)
        if screenshot is None:
            screenshot = await asyncio.to_thread(
                _fetch_state_screenshot, container, slot
            )
        try:
            await _store_state_asset(user, rom, emulator, filename, content, screenshot)
        except Exception:
            log.exception("failed to store pulled state %s", filename)
            return False
        log.info(
            "state synced to library, rom=%s slot=%d file=%s",
            rom.name,
            slot,
            filename,
        )
        return True

    log.warning("no state file to pull after save, rom_id=%d slot=%d", rom_id, slot)
    return False


async def _push_resume_state(container: dict[str, Any], resume_state: Any) -> bool:
    """Send the state a player picked to resume from down to the container.

    Best-effort: a failure means the session just starts fresh, which the claim
    response reports through `resume`.
    """
    try:
        content = await fs_asset_handler.read_file(
            f"{resume_state.file_path}/{resume_state.file_name}"
        )
    except Exception:
        log.exception("could not read resume state %s", resume_state.file_name)
        return False
    pushed = await asyncio.to_thread(
        _push_state_file,
        container,
        _container_state_filename(resume_state.file_name),
        content,
    )
    if not pushed:
        log.warning("resume state not pushed, launching fresh")
    return pushed


async def _hydrate_states_to_broker(
    user_id: int,
    rom_id: int,
    container: dict[str, Any],
    resume_pushed: bool = False,
) -> int:
    """Background task: push the newest stored state for this ROM down to the
    freshly claimed container. Emulators read state files lazily, so pushing
    right after launch is safe.

    Only the newest is sent: every history entry collapses to the same
    container-side name, and that name is what the in-emulator quick-load lands
    on. Older captures are reached through the resume picker instead.

    For the same reason, a resume pick already sent at claim time means there is
    nothing to add here: any push would overwrite it before the broker's
    deferred load fires.
    """
    if resume_pushed:
        return 0

    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return 0
    emulator = _emulator_for_container(container)

    states = _user_states_for_emulator(user_id, rom_id, emulator)
    if not states:
        return 0

    newest = states[0]
    try:
        content = await fs_asset_handler.read_file(
            f"{newest.file_path}/{newest.file_name}"
        )
    except FileNotFoundError:
        log.warning("stored state missing on disk, %s", newest.file_name)
        return 0
    ok = await asyncio.to_thread(
        _push_state_file,
        container,
        _container_state_filename(newest.file_name),
        content,
    )
    if ok:
        log.info("hydrated newest state to container, rom=%s", rom.name)
    return 1 if ok else 0


# ── In-game save sync ─────────────────────────────────────────────────────────
# Parallel to the state sync above, but for the emulator's own in-game saves
# (memory cards / NAND / battery saves). The broker ships them as a single zip
# archive via GET/PUT /save-file; RomM stores each pulled archive as one Save
# asset with a .zip extension so the whole card set travels as a unit.

# A pulled save archive can be large (PCSX2 ships whole 8 MB memory cards, a
# Wii NAND can hold many titles); 256 MB is generous for every emulator that
# separates its saves from its states.
_SAVE_FILE_MAX_BYTES = 256 * 1024 * 1024


def _fetch_save_archive(
    container: dict[str, Any], broker_session_id: str | None = None
) -> bytes | None:
    """GET /save-file from the broker. Returns the zip bytes or None.

    404 means nothing changed since the game launched (the normal "no new
    saves" case); any other failure is logged and treated the same way.
    """
    if _is_webstation(container):
        # Exit already built the delta archive and left it on the container,
        # named after the session that produced it. Matching on that name is
        # what keeps an archive a previous pull failed to collect from being
        # filed under this session's player.
        if not broker_session_id:
            return None
        prefix = f"{broker_session_id}-"
        for export in _webstation_exports(container):
            name = str(export.get("name", ""))
            if name.startswith(prefix):
                return _webstation_collect_export(container, name)
        return None

    result = _broker_get_binary_safe(
        container,
        "/save-file",
        "save-file GET",
        max_bytes=_SAVE_FILE_MAX_BYTES,
        timeout=_BROKER_TRANSFER_TIMEOUT,
    )
    return result[1] if result else None


def _push_save_archive(container: dict[str, Any], content: bytes) -> bool:
    """PUT /save-file to the broker. Best-effort, logs but never raises."""
    return _broker_put_binary(
        container,
        "/save-file",
        content,
        "save-file PUT",
        content_type="application/zip",
        timeout=_BROKER_TRANSFER_TIMEOUT,
    )


async def _store_save_asset(
    user: User, rom: Rom, emulator: str, content: bytes
) -> bool:
    """Store a pulled save archive as a new Save asset.

    Each pull creates a fresh row (timestamped filename), so the user keeps a
    history of save snapshots rather than overwriting. Identical content is
    deduplicated by hash so idle exits do not pile up copies.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H-%M-%S")
    filename = sanitize_filename(f"{rom.fs_name_no_ext} [{emulator} {ts}].saves.zip")

    saves_path = fs_asset_handler.build_saves_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    await fs_asset_handler.write_file(file=content, path=saves_path, filename=filename)

    scanned_save = await scan_save(
        file_name=filename,
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    # Drop the write if an identical archive is already stored for this ROM.
    if scanned_save.content_hash:
        existing = db_save_handler.get_save_by_content_hash(
            user_id=user.id, rom_id=rom.id, content_hash=scanned_save.content_hash
        )
        if existing is not None:
            try:
                await fs_asset_handler.remove_file(f"{saves_path}/{filename}")
            except FileNotFoundError:
                pass
            return False

    scanned_save.rom_id = rom.id
    scanned_save.user_id = user.id
    scanned_save.emulator = emulator
    db_save_handler.add_save(save=scanned_save)
    return True


async def _pull_saves_to_library(
    user_id: int,
    rom_id: int,
    container: dict[str, Any],
    broker_session_id: str | None = None,
) -> bool:
    """Background task: pull in-game saves from the broker and store them.

    Best-effort by design, a sync failure must never surface to the player,
    the save still exists inside the container.
    """
    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return False
    emulator = _emulator_for_container(container)

    for attempt in range(_STATE_PULL_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(_STATE_PULL_RETRY_DELAY)
        content = await asyncio.to_thread(
            _fetch_save_archive, container, broker_session_id
        )
        if content is None:
            continue
        try:
            stored = await _store_save_asset(user, rom, emulator, content)
        except Exception:
            log.exception("failed to store pulled saves, rom=%s", rom.name)
            return False
        if stored:
            log.info("saves synced to library, rom=%s", rom.name)
        else:
            log.info("pulled saves unchanged, rom=%s", rom.name)
        return True

    log.info("no save changes to pull, rom_id=%d", rom_id)
    return False


async def _newest_save_archive(
    user_id: int, rom_id: int, emulator: str
) -> tuple[str, bytes] | None:
    """The user's most recent stored save archive for this emulator, read off
    disk. Returns (file name, content), or None when there is nothing to send.
    """
    newest = None
    for save in db_save_handler.get_saves(
        user_id=user_id, rom_id=rom_id, order_by="created_at", order_dir="desc"
    ):
        if (save.emulator or "").lower() != emulator:
            continue
        if not save.file_name.endswith(".zip"):
            continue
        newest = save
        break
    if newest is None:
        return None

    try:
        content = await fs_asset_handler.read_file(
            f"{newest.file_path}/{newest.file_name}"
        )
    except FileNotFoundError:
        log.warning("stored save missing on disk, %s", newest.file_name)
        return None
    return newest.file_name, content


async def _hydrate_saves_to_broker(
    user_id: int, rom_id: int, container: dict[str, Any]
) -> bool:
    """Push the user's newest stored save archive down to the freshly claimed
    container BEFORE the game launches. Games read saves at boot, so this must
    happen synchronously ahead of the launch (unlike states, read lazily).
    """
    rom = db_rom_handler.get_rom(rom_id)
    if db_user_handler.get_user(user_id) is None or rom is None:
        return False

    newest = await _newest_save_archive(
        user_id, rom_id, _emulator_for_container(container)
    )
    if newest is None:
        return False
    file_name, content = newest

    ok = await asyncio.to_thread(_push_save_archive, container, content)
    if ok:
        log.info("hydrated saves to container, rom=%s file=%s", rom.name, file_name)
    return ok


async def _hydrate_saves_to_webstation(
    user_id: int, rom_id: int, container: dict[str, Any]
) -> str | None:
    """Upload the newest stored save archive and return the container path.

    The webstation broker restores as part of activate rather than through a
    push of its own, so hydration here only gets the bytes into place and
    hands back the path activate names.
    """
    newest = await _newest_save_archive(
        user_id, rom_id, _emulator_for_container(container)
    )
    if newest is None:
        return None
    file_name, content = newest

    path = await asyncio.to_thread(
        _webstation_upload_archive, container, f"rom-{rom_id}.zip", content
    )
    if path:
        log.info("uploaded saves to container, file=%s path=%s", file_name, path)
    return path


# ── Whole memory-card sync (per-user card model) ──────────────────────────────
# Opt-in per container via `memory_card_sync: true`. When on, the container's
# entire card (PCSX2 Slot 1, Dolphin Slot A) is one owned image: hydrated (or
# wiped to a fresh blank card) on claim, and evacuated to the library before the
# game is stopped. This REPLACES the /save-file in-game-save path above for that
# container; save-STATE sync is untouched.


def _empty_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    return buf.getvalue()


# PUT to a freshly claimed container to wipe slot 1 to a blank card, so the next
# player never inherits the previous owner's saves (the isolation guarantee for
# pooled hosts). The broker's wipe-then-replace lays down an empty card and
# PCSX2 formats it on first save.
_EMPTY_MEMORY_CARD = _empty_zip_bytes()


def _memory_card_sync_enabled(container: dict[str, Any]) -> bool:
    """Whether whole-card sync is both requested and possible for a container.

    Honouring `memory_card_sync` on a platform with no memory card would be
    silent data loss: whole-card sync REPLACES /save-file, so the per-file
    saves that platform actually uses (Wii NAND, xemu HDD) would stop syncing
    while RomM shuttled an empty card around. The flag is ignored instead, and
    _containers_for_platform warns the operator once per lookup.
    """
    if not container.get("memory_card_sync", False):
        return False
    return not _known_to_lack_memory_card(container.get("platform", ""))


def _memory_card_route(container: dict[str, Any]) -> str:
    """Where this container's broker serves the whole Slot-1 card.

    The webstation broker hosts several emulators off one container and the
    card belongs to the emulator, not to a session, so it takes the name in the
    query. The per-emulator brokers serve the one card they have.
    """
    path = "/memory-card"
    if _is_webstation(container):
        path = f"{path}?emulator={quote(_emulator_for_container(container), safe='')}"
    return _transfer_route(container, path)


class _MemoryCardUnavailable(Exception):
    """The broker's Slot-1 card could not be read (endpoint missing, wrong card
    type, oversize, or a transport error). Distinct from a broker-confirmed
    EMPTY slot: unavailable means we must NOT wipe, since we never captured it."""


# Its messages carry the broker host and port, so the client gets this fixed
# string and the real cause stays in the server log.
_CARD_UNREADABLE_REASON = "The streaming container did not return its memory card"

_CARD_IMPORT_FAILED_DETAIL = "Could not import the memory card"


def _fetch_memory_card(
    container: dict[str, Any], timeout: float = _CARD_HYDRATE_TIMEOUT
) -> bytes | None:
    """GET /memory-card from the broker. Tri-state:

    - bytes: the Slot-1 card was captured and can be stored.
    - None:  the broker CONFIRMS the slot is empty (404 tagged
      `X-Memory-Card: absent`). Nothing to store, safe to wipe.
    - raise `_MemoryCardUnavailable`: the card could not be read (endpoint
      missing / unmarked 404, 409 File card, oversize, empty 200, or a transport
      error). The caller must NOT wipe, since the card was never captured.
    """
    try:
        _, content = _broker_get_binary(
            container,
            _memory_card_route(container),
            max_bytes=MEMORY_CARD_MAX_BYTES,
            timeout=timeout,
        )
        return content
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and exc.headers.get("X-Memory-Card") == "absent":
            # Broker confirms the slot is genuinely empty (first run, or already
            # wiped). Safe to wipe; there is simply nothing to evacuate.
            return None
        if exc.code == 409:
            raise _MemoryCardUnavailable(
                "broker slot 1 is a File card, not a Folder card"
            ) from exc
        raise _MemoryCardUnavailable(
            f"broker memory-card GET failed, HTTP {exc.code}"
        ) from exc
    except Exception as exc:
        raise _MemoryCardUnavailable(f"broker memory-card GET failed, {exc}") from exc


def _push_memory_card(
    container: dict[str, Any], content: bytes, timeout: float = _CARD_HYDRATE_TIMEOUT
) -> bool:
    """PUT /memory-card to the broker (wipe-then-replace). Best-effort, logs
    but never raises. The caller decides whether a failure aborts the claim."""
    return _broker_put_binary(
        container,
        _memory_card_route(container),
        content,
        "memory-card PUT",
        content_type="application/zip",
        timeout=timeout,
    )


class MemoryCardSummary(TypedDict):
    file_count: int
    total_bytes: int
    game_codes: list[str]


def _summarize_memory_card(content: bytes) -> MemoryCardSummary:
    """Describe a fetched card for the import dialog. GameCube names its saves
    `<makercode>-<gamecode>-<comment>.gci`, so the gamecode is a filename field,
    not something that needs the card format parsed.

    Never raises: a card we cannot parse still has to be offered to the user.
    """
    codes: set[str] = set()
    file_count = 0
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                total += info.file_size
                parts = PurePosixPath(info.filename).name.split("-")
                if len(parts) >= 3 and info.filename.lower().endswith(".gci"):
                    codes.add(parts[1])
    except Exception:
        # Unparseable: nothing describable, so report nothing rather than a
        # file-less card that still claims a size.
        return {"file_count": 0, "total_bytes": 0, "game_codes": []}
    return {
        "file_count": file_count,
        "total_bytes": total,
        "game_codes": sorted(codes),
    }


def _resolve_memory_card(
    user_id: int, emulator: str, memory_card_id: int | None
) -> MemoryCard | None:
    """Pick the card to mount for a claim.

    An explicit id must be one the user owns for this emulator. Shared/public
    cards are view-only: they are browsable and downloadable through the memory
    card UI, but never live-mounted onto another user's session, since a mounted
    card is written back as a new version on release and that version belongs to
    the owner. With no id, use the user's most-recently-used
    card for the emulator, or None when the user has no card yet. Resolution
    never creates rows; the claim path creates a blank card only after the
    claim is won.
    """
    if memory_card_id is not None:
        card = db_memory_card_handler.get_card(user_id=user_id, id=memory_card_id)
        if card is None or card.emulator != emulator:
            raise HTTPException(
                status_code=404, detail="Memory card not found for this emulator"
            )
        return card

    cards = db_memory_card_handler.get_cards(user_id=user_id, emulator=emulator)
    if cards:
        return cards[0]  # get_cards orders by updated_at desc
    return None


def _create_blank_memory_card(
    user_id: int, emulator: str, platform_id: int | None
) -> MemoryCard:
    """Create a fresh blank card for a user's first play on an emulator. The
    blank carries no version, so hydrate wipes the container to a clean card
    that the emulator formats on first save.
    """
    blank = MemoryCard(
        user_id=user_id,
        emulator=emulator,
        platform_id=platform_id,
        name=f"{emulator} memory card",
        slot=1,
        is_public=False,
    )
    return db_memory_card_handler.add_card(blank)


async def _hydrate_memory_card_to_broker(
    user_id: int, card: MemoryCard, container: dict[str, Any]
) -> bool:
    """Push the card's newest version down to a freshly claimed container BEFORE
    launch (games read the card at boot). A blank card, or one whose stored file
    has gone missing, wipes the container to a fresh card so the player never
    inherits a previous owner's saves. Returns False only when the broker push
    itself fails, so the caller can abort a claim it could not isolate.
    """
    latest = db_memory_card_handler.get_latest_version(card.id)
    content = _EMPTY_MEMORY_CARD
    if latest is not None:
        try:
            content = await fs_asset_handler.read_file(
                f"{latest.file_path}/{latest.file_name}"
            )
        except FileNotFoundError:
            # The version row exists but the file is gone. Wiping to a blank
            # card keeps isolation intact rather than leaking the last card.
            log.warning(
                "memory card file missing on disk, %s, wiping to blank",
                latest.file_name,
            )
    ok = await asyncio.to_thread(_push_memory_card, container, content)
    if ok:
        log.info(
            "hydrated memory card to container, card=%d version=%s",
            card.id,
            latest.file_name if latest is not None else "(blank)",
        )
    return ok


def _adoption_already_stored(card_id: int, content: bytes | None) -> bool:
    """Is the container's card already this card's latest version?

    Dedup can refuse a version because a previous claim stored it and then died
    before recording the adoption decision, leaving the prompt to fire again on
    unchanged content. That retry is idempotent: hydrate would push back the
    very bytes sitting on the container, so the adoption stands and only the
    decision row is missing. A match against an older version means hydrate
    would push something else over the card, which is the case that must abort.
    """
    if not content:
        return False
    content_hash = content_hash_of_bytes(content)
    if not content_hash:
        return False
    latest = db_memory_card_handler.get_latest_version(card_id)
    return latest is not None and latest.content_hash == content_hash


async def _evacuate_memory_card(
    user_id: int, card_id: int, emulator: str, container: dict[str, Any]
) -> bool:
    """Pull the whole Slot-1 card off the broker and store it as a new version.

    Called before the emulator is stopped so a pooled container is captured
    before it can be reclaimed. Returns `safe_to_wipe`: True only when the card
    was captured (or the broker confirmed the slot is empty), False when it
    could not be read. The caller wipes the slot only when this is True, so a
    card that failed to evacuate is never destroyed.
    """
    user = db_user_handler.get_user(user_id)
    card = db_memory_card_handler.get_card_by_id(card_id)
    if user is None or card is None:
        return False
    try:
        # Teardown must not hang a release for the full transfer window, so the
        # fetch gets a tighter bound than hydrate-on-claim.
        content = await asyncio.to_thread(
            _fetch_memory_card, container, timeout=_CARD_TEARDOWN_TIMEOUT
        )
    except _MemoryCardUnavailable as exc:
        log.warning(
            "could not evacuate memory card %d, not safe to wipe, %s",
            card_id,
            exc,
        )
        return False
    if content is None:
        log.info("broker slot empty, nothing to evacuate, card=%d", card_id)
        return True
    try:
        stored = await store_memory_card_version(user, card, emulator, content)
    except Exception:
        log.exception("failed to store evacuated memory card %d", card_id)
        return False
    if stored:
        log.info("memory card evacuated to library, card=%d", card_id)
    else:
        log.info("evacuated memory card unchanged, card=%d", card_id)
    return True


async def _evacuate_session_card(
    session: dict[str, Any], container: dict[str, Any]
) -> bool:
    """Evacuate a whole-card-sync session's card before its container is freed.

    MUST be awaited while the Redis claim is still held: releasing the claim
    first would let another user claim the container and wipe the card (claim
    hydrates wipe-then-replace) before we capture it. Returns `safe_to_wipe`:
    True only when the card was captured (or confirmed empty). No-op returning
    False for containers without memory_card_sync or sessions that never
    resolved a card, so those are never wiped.
    """
    if not _memory_card_sync_enabled(container):
        return False
    card_id = session.get("memory_card_id")
    user_id = session.get("user_id")
    if not isinstance(card_id, int) or not isinstance(user_id, int):
        return False
    emulator = _emulator_for_container(container)
    try:
        return await _evacuate_memory_card(user_id, card_id, emulator, container)
    except Exception:
        log.exception("memory card evacuation failed, card=%d", card_id)
        return False


async def _wipe_session_card(container: dict[str, Any]) -> None:
    """Blank the broker's Slot-1 card after a confirmed evacuation.

    Defense in depth for pooled hosts: hydrate already wipes-then-replaces on
    the next claim, but wiping now guarantees no card is left behind between
    sessions for a bad or crashing hydrate to inherit. MUST run only when
    evacuation reported safe_to_wipe, after the game is stopped (so the
    emulator's exit flush cannot re-lay the card) and BEFORE the Redis claim is
    released (so a concurrent claimant's fresh card is never clobbered).
    Best-effort: a failed wipe is logged, not fatal, since the next claim wipes.
    """
    if not _memory_card_sync_enabled(container):
        return
    # Teardown path, so a tighter bound than hydrate-on-claim.
    ok = await asyncio.to_thread(
        _push_memory_card, container, _EMPTY_MEMORY_CARD, timeout=_CARD_TEARDOWN_TIMEOUT
    )
    if ok:
        log.info("wiped broker memory-card slot after evacuation")
    else:
        log.warning("memory-card slot wipe failed, relying on next-claim wipe")


# Streaming sessions shorter than this are treated as accidental (a claim that
# was released almost immediately) and not recorded as playtime.
_MIN_PLAY_SESSION_MS = 5_000


async def _record_play_session(session: dict[str, Any]) -> None:
    """Record a finished streaming session as RomM playtime.

    Reuses the same ingest path as device sync (dedup on user+rom+start_time,
    updates the ROM's last_played). The session's stored claimed_at is the
    start and now is the end. Best-effort: any failure is logged, never fatal,
    so playtime accounting cannot block or fail a teardown.
    """
    user_id = session.get("user_id")
    rom_id = session.get("rom_id")
    claimed_at = session.get("claimed_at")
    if (
        not isinstance(user_id, int)
        or not isinstance(rom_id, int)
        or not isinstance(claimed_at, str)
    ):
        return

    try:
        start = datetime.fromisoformat(claimed_at)
    except ValueError:
        return
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    end = datetime.now(timezone.utc)
    duration_ms = int((end - start).total_seconds() * 1000)
    if duration_ms < _MIN_PLAY_SESSION_MS:
        return

    try:
        user = db_user_handler.get_user(user_id)
        ingest_play_sessions(
            user_id=user_id,
            username=user.username if user else str(user_id),
            entries=[
                {
                    "rom_id": rom_id,
                    "save_slot": None,
                    "start_time": start,
                    "end_time": end,
                    "duration_ms": duration_ms,
                }
            ],
        )
    except Exception:
        log.exception("failed to record play session")


async def _teardown_abandoned_session(
    container: dict[str, Any], session_key: str, session: dict[str, Any]
) -> None:
    """Free a container whose owner vanished without releasing (heartbeat went
    stale). Same order as an owner release: stop the emulator so the card is
    quiescent, evacuate and wipe it, credit the owner's playtime, then drop
    the claim.
    """
    await asyncio.to_thread(_stop_broker, container)
    safe_to_wipe = await _evacuate_session_card(session, container)
    if safe_to_wipe:
        await _wipe_session_card(container)
    await _record_play_session(session)
    await async_cache.delete(_session_redis_key(session_key))


# Slot number encoded in each emulator's state filename, e.g. PCSX2 writes
# "SERIAL (CRC).03.p2s" for slot 3 and Dolphin writes "GAMEID.s03". Resuming
# from a picked state needs the slot to tell the broker what to load, and the
# match is also where the capture stamp is inserted, so an emulator missing
# from here gets no history either.
_STATE_SLOT_PATTERNS = {
    "pcsx2": re.compile(r"\.(\d{1,2})\.p2s$"),
    "dolphin": re.compile(r"\.s(\d{2})$"),
    "xemu": re.compile(r"\.x(\d{2})$"),
    # RetroArch leaves the number off its default slot: "GAME.state" is slot 0
    # and "GAME.state3" is slot 3.
    "retroarch": re.compile(r"\.state(\d{0,2})$"),
}


# Lowest slot each emulator's broker will actually address. Everything but
# RetroArch counts from 1, so a "0" in one of their names is a filename that
# happens to look like a state, not a slot they could load.
_MIN_STATE_SLOT = {"retroarch": 0}


def _slot_from_state_filename(emulator: str, filename: str) -> int | None:
    pattern = _STATE_SLOT_PATTERNS.get(emulator)
    if pattern is None:
        return None
    match = pattern.search(filename)
    if match is None:
        return None
    slot = int(match.group(1) or 0)
    return slot if slot >= _MIN_STATE_SLOT.get(emulator, 1) else None


# Every capture is kept, so the library needs one file per save, not one per
# slot. The stamp goes immediately before the slot token so the patterns above
# still match at the end of the name: states written before this keep
# resolving, and the container-side name is recovered by dropping the stamp.
_STATE_STAMP_FORMAT = "%Y%m%d-%H%M%S%f"
_STATE_STAMP_PATTERN = re.compile(r"\.\d{8}-\d{12}(?=\.)")


def _stamped_state_filename(emulator: str, filename: str, when: datetime) -> str:
    """Return ``filename`` with a capture stamp inserted before its slot token.

    An emulator with no known slot convention keeps the original name, since
    there is nowhere unambiguous to put the stamp. That emulator gets no
    history: each capture lands on the same name and updates its row in place,
    the pre-history behavior. No streaming emulator is in that position now.
    """
    pattern = _STATE_SLOT_PATTERNS.get(emulator)
    if pattern is None:
        return filename
    match = pattern.search(filename)
    if match is None:
        return filename
    stamp = when.strftime(_STATE_STAMP_FORMAT)
    return f"{filename[: match.start()]}.{stamp}{filename[match.start() :]}"


def _container_state_filename(filename: str) -> str:
    """Strip any capture stamp, giving the name the emulator expects on disk."""
    return _STATE_STAMP_PATTERN.sub("", filename, count=1)


def _resolve_resume_state(
    user_id: int, rom: Rom, container: dict[str, Any], state_id: int
) -> tuple[Any, int]:
    """Validate a resume-from-state pick and return (state, slot).

    Visibility follows the same rule as the state list the picker was built
    from: the claiming user's own states plus other users' public ones.
    Raises 404 for anything invisible, 400 when the state cannot drive a
    resume on this container.
    """
    state = next(
        (
            s
            for s in db_state_handler.get_rom_shared_states(
                rom_id=rom.id, user_id=user_id
            )
            if s.id == state_id
        ),
        None,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")

    emulator = _emulator_for_container(container)
    if (state.emulator or "").lower() != emulator:
        raise HTTPException(
            status_code=400,
            detail="State was made by a different emulator",
        )

    slot = _slot_from_state_filename(emulator, state.file_name)
    if slot is None:
        raise HTTPException(
            status_code=400,
            detail="State filename carries no recognizable slot number",
        )
    return state, slot


# ── Routes ────────────────────────────────────────────────────────────────────
#
# Reads gate on ROMS_READ; anything that creates, controls or releases a session
# gates on ROMS_USER_WRITE, matching the play-session routes. ROMS_USER_WRITE is
# always-on for authenticated users, so this costs no real user anything, but it
# is absent from READ_SCOPES -- which is all KIOSK_MODE hands an anonymous
# visitor. Without it, kiosk visitors (who all share one synthetic user, so
# session ownership cannot separate them) could claim sessions and overwrite
# each other's save states.


@protected_route(router.get, "/config", [Scope.ROMS_READ])
async def get_config(request: Request) -> JSONResponse:
    """Return streaming configuration to the frontend"""
    cfg = _get_streaming_config()

    # Keyed by platform: a pool is a backend concern, the frontend picks a
    # platform and the claim decides which container serves it.
    safe_containers: dict[str, dict[str, Any]] = {}
    for c in cfg.get("containers", []):
        if not c.get("platform") or not c.get("host"):
            log.warning("container missing platform/host, skipping: %s", c)
            continue

        platform = c.get("platform", "")
        if platform in safe_containers:
            continue
        safe_containers[platform] = {
            "platform": platform,
            "host": c.get("host"),
            "label": c.get("label") or platform.upper(),
            # Ship slot capabilities so the frontend selector reads them
            # instead of keeping its own hardcoded per-platform copy.
            "capabilities": _container_capabilities(c),
            # State namespace for this container, so the frontend can
            # filter the resume picker the same way hydration filters.
            "emulator": _emulator_for_container(c),
            # Whether this container syncs whole memory cards, so the
            # frontend only offers the card picker where it applies.
            "supports_memory_cards": _memory_card_sync_enabled(c),
        }

    return JSONResponse(
        {
            "enabled": cfg.get("enabled", False),
            "containers": list(safe_containers.values()),
        }
    )


@protected_route(router.post, "/sessions", [Scope.ROMS_USER_WRITE])
async def claim_session(
    request: Request, req: Annotated[ClaimSessionRequest, Body()]
) -> JSONResponse:
    """
    Claim a streaming session and tell the broker to load the ROM.

    The ROM's filesystem path is derived server-side from its database row -
    the client only supplies a ROM id, never a path.
    Returns 404 if the ROM doesn't exist or no container serves its platform.
    Returns 409 if every container serving the platform is occupied.
    Returns 428 if the container's pre-existing memory card needs a decision.
    Returns 502/503 if the broker rejects the launch or is unreachable.
    """
    rom = db_rom_handler.get_rom(req.rom_id)
    if rom is None:
        raise HTTPException(status_code=404, detail="ROM not found")

    # A hidden ROM/platform must not be launchable via its id: enforce the same
    # visibility policy as the ROM detail/content endpoints before any broker
    # launch. Raises a 404 that masks the hidden ROM's existence.
    assert_rom_visible(request, rom, not_found_detail="ROM not found")

    platform = rom.platform_slug
    candidates = _containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )

    # Pool members are interchangeable on emulator and card sync (enforced by
    # _containers_for_platform), so the pre-claim validation below holds for
    # whichever one the walk ends up winning.
    reference = candidates[0]

    # Validate the resume pick before claiming so a bad state_id cannot
    # leave a container wedged behind a failed launch.
    resume_state = None
    resume_slot: int | None = None
    if req.state_id is not None:
        resume_state, resume_slot = _resolve_resume_state(
            request.user.id, rom, reference, req.state_id
        )

    # Resolve the memory card to mount before claiming too, so a bad card id
    # fails cleanly (whole-card-sync containers only). May be None on first
    # play; the blank card is created only after the claim is won.
    memory_card = None
    if _memory_card_sync_enabled(reference):
        memory_card = _resolve_memory_card(
            request.user.id,
            _emulator_for_container(reference),
            req.memory_card_id,
        )

    rom_name = rom.name or rom.fs_name_no_ext

    now = datetime.now(timezone.utc).isoformat()
    session = {
        # Unique per claim, and safe to put in a filename. The webstation
        # broker names its exit archive after it, so the pull can tell this
        # session's saves from one an earlier pull failed to collect.
        "broker_session_id": secrets.token_hex(8),
        "rom_id": rom.id,
        "rom_name": rom_name,
        # Stored so admin views can release through the platform-keyed DELETE
        # route without reverse-mapping the container key, and so a container
        # serving several platforms resolves back to the right config entry.
        "platform": platform,
        "claimed_at": now,
        # Liveness stamp, refreshed by the heartbeat endpoint. A session that
        # stops refreshing counts as abandoned and can be taken over.
        "last_seen": now,
        "user_id": request.user.id,
        # Carried so every teardown path (owner release, save-and-exit, admin
        # force-release) can evacuate the right card before stopping the game.
        "memory_card_id": memory_card.id if memory_card is not None else None,
    }

    async def _try_claim(candidate: dict[str, Any]) -> bool:
        # SET NX is atomic: exactly one concurrent claim wins the key. The TTL
        # bounds how long an abandoned session (broker dead / backend crashed)
        # can hold the container; control calls and heartbeats refresh it.
        return bool(
            await async_cache.set(
                _session_redis_key(_container_key(candidate)),
                json.dumps(session),
                nx=True,
                ex=SESSION_TTL_SECONDS,
            )
        )

    # Config order, first free wins.
    container: dict[str, Any] | None = None
    for candidate in candidates:
        if await _try_claim(candidate):
            container = candidate
            break

    if container is None:
        # Every container is held, but a holder may be long gone: a closed tab
        # or a crashed browser never sends a release, and the TTL alone would
        # hold it for hours. A stale heartbeat means abandoned, so tear that
        # session down (evacuating its card and crediting its playtime) and
        # retry. Evicting anyone is deferred until here so a pool never
        # displaces a stale session while another container sits idle. A drain
        # marker is never taken over: the broker is still killing the previous
        # emulator, and the marker expires on its own within seconds.
        for candidate in candidates:
            existing = await _get_session(_container_key(candidate))
            if (
                existing is None
                or existing.get("draining")
                or not _session_is_stale(existing)
            ):
                continue
            log.warning(
                "taking over stale session, platform=%s user_id=%s",
                platform,
                existing.get("user_id"),
            )
            await _teardown_abandoned_session(
                candidate, _container_key(candidate), existing
            )
            if await _try_claim(candidate):
                container = candidate
                break

    if container is None:
        # Report the head of the pool as the holder: with one container that is
        # the only holder, and with several the player just needs to know the
        # platform is busy.
        existing = await _get_session(_container_key(candidates[0])) or {}
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Session in use"
                    if len(candidates) == 1
                    else f"All {len(candidates)} containers for this platform are in use"
                ),
                "rom_name": existing.get("rom_name"),
                "claimed_at": existing.get("claimed_at"),
            },
        )

    session_key = _container_key(container)

    # The emulator containers mount the RomM library at the same path the
    # backend uses (LIBRARY_BASE_PATH, /romm/library by default), so the
    # backend-side path is valid inside the broker container too. If a
    # container mounts the library at a different path, `library_path` on
    # its config entry overrides the prefix so the broker receives a path
    # that is valid inside that container.
    library_base = (container.get("library_path") or LIBRARY_BASE_PATH).rstrip("/")
    rom_path = f"{library_base}/{rom.full_path}"

    # A container that still holds someone's pre-existing card must not be
    # wiped on a hunch. Probe once, then record the answer so this never
    # interrupts a claim again. Probed only by the claim winner, so a user who
    # loses the race gets the 409 rather than a prompt describing the card of
    # the player currently on the container. Every exit from here that is not a
    # started session releases the claim, so an abandoned dialog leaves no trace.
    adoption_content: bytes | None = None
    adoption_undecided = False
    if (
        _memory_card_sync_enabled(container)
        and db_container_adoption_handler.get_adoption(_container_key(container))
        is None
    ):
        adoption_undecided = True
        try:
            adoption_content = await asyncio.to_thread(_fetch_memory_card, container)
        except _MemoryCardUnavailable as exc:
            # Unreadable is not empty, so the wipe needs the user's consent.
            # Only "discard" may override it: a card that was never captured
            # cannot be adopted, and pretending otherwise destroys it.
            log.warning("could not read the container memory card, %s", exc)
            if req.card_import != "discard":
                await async_cache.delete(_session_redis_key(session_key))
                if req.card_import is None:
                    raise HTTPException(
                        status_code=428,
                        detail={
                            "code": "memory_card_import_required",
                            "outcome": "unreadable",
                            "reason": _CARD_UNREADABLE_REASON,
                        },
                    ) from exc
                raise HTTPException(
                    status_code=502, detail=_CARD_IMPORT_FAILED_DETAIL
                ) from exc
            adoption_content = None
        if adoption_content is None and req.card_import == "adopt":
            # The slot is empty now, so the import the user asked for cannot
            # happen. Abort without recording so the prompt fires again.
            log.warning("adopt requested but the container slot is empty")
            await async_cache.delete(_session_redis_key(session_key))
            raise HTTPException(status_code=502, detail=_CARD_IMPORT_FAILED_DETAIL)
        if adoption_content is not None and req.card_import is None:
            await async_cache.delete(_session_redis_key(session_key))
            raise HTTPException(
                status_code=428,
                detail={
                    "code": "memory_card_import_required",
                    "outcome": "found",
                    "summary": _summarize_memory_card(adoption_content),
                },
            )
        if req.card_import == "discard":
            adoption_content = None

    # The player is back in a session, so any note about their previous one
    # being force-released has served its purpose.
    await _clear_termination(session_key, request.user.id)

    # Auto-create the blank card only after the claim is won, so a lost race
    # (409) never leaves an orphan card behind. If a later step fails and aborts
    # the claim, delete the blank we just made so an aborted claim leaks nothing.
    created_blank_card_id: int | None = None
    if _memory_card_sync_enabled(container) and memory_card is None:
        memory_card = _create_blank_memory_card(
            request.user.id, _emulator_for_container(container), rom.platform_id
        )
        created_blank_card_id = memory_card.id
        session["memory_card_id"] = memory_card.id
        await async_cache.set(
            _session_redis_key(session_key),
            json.dumps(session),
            ex=SESSION_TTL_SECONDS,
        )

    # Establish version 1 from the container's own card before hydrate runs, so
    # the hydrate that follows pushes the adopted card back rather than a blank.
    # An absent or discarded card is recorded too, so the prompt fires once and
    # a card that shows up later is treated as the container's, not the user's.
    if _memory_card_sync_enabled(container) and adoption_undecided:
        # Resolved above or freshly created as a blank, never None on this path.
        assert memory_card is not None
        adopted = req.card_import == "adopt" and adoption_content is not None
        if adopted:
            stored = False
            try:
                stored = await store_memory_card_version(
                    request.user,
                    memory_card,
                    _emulator_for_container(container),
                    adoption_content,  # type: ignore[arg-type]
                )
            except Exception as exc:
                # Hydrate would wipe the container next, so a failed import must
                # abort rather than destroy the card it was asked to keep.
                log.exception("could not adopt the container memory card")
                await async_cache.delete(_session_redis_key(session_key))
                if created_blank_card_id is not None:
                    db_memory_card_handler.delete_card(created_blank_card_id)
                raise HTTPException(
                    status_code=502, detail=_CARD_IMPORT_FAILED_DETAIL
                ) from exc
            if not stored and not _adoption_already_stored(
                memory_card.id, adoption_content
            ):
                # Content-hash dedup matched an older version of this card, so
                # no version was created and hydrate would push whichever
                # version is latest over the container card. Abort instead.
                log.error(
                    "adopted memory card matched an existing version of card %d",
                    memory_card.id,
                )
                await async_cache.delete(_session_redis_key(session_key))
                if created_blank_card_id is not None:
                    db_memory_card_handler.delete_card(created_blank_card_id)
                raise HTTPException(status_code=502, detail=_CARD_IMPORT_FAILED_DETAIL)
        db_container_adoption_handler.add_adoption(
            container_key=_container_key(container),
            outcome="adopt" if adopted else "discard",
            user_id=request.user.id,
        )

    # Push the resume state before launch so its file is in place when the
    # broker's deferred slot load fires. Best-effort: a failed push falls
    # back to a fresh launch, reported through `resume` in the response.
    # The webstation broker only takes a state while a session is up, and its
    # session starts at activate, so that push has to happen after launch.
    resume_pushed = False
    resume_after_launch = _is_webstation(container) and resume_state is not None
    if resume_state is not None and not resume_after_launch:
        resume_pushed = await _push_resume_state(container, resume_state)

    # Prepare in-game saves before launch - games read them at boot, so unlike
    # states this cannot be deferred to a background task.
    archive_path: str | None = None
    if memory_card is not None:
        # Whole-card sync: hydrate (or wipe to blank) is REQUIRED. If it fails
        # we cannot guarantee the container is isolated from the previous
        # player's card, so abort the claim rather than launch a leaky session.
        try:
            hydrated = await _hydrate_memory_card_to_broker(
                request.user.id, memory_card, container
            )
        except Exception:
            log.exception("memory card hydration failed")
            hydrated = False
        if not hydrated:
            await async_cache.delete(_session_redis_key(session_key))
            if created_blank_card_id is not None:
                db_memory_card_handler.delete_card(created_blank_card_id)
            raise HTTPException(
                status_code=502, detail="Could not prepare the memory card"
            )
    if _is_webstation(container):
        # Restore runs inside activate on this protocol, so hydration only gets
        # the bytes onto the container and names the path activate restores.
        # Still runs under whole-card sync: the archive carries the state the
        # last session ended on, which the card does not.
        # Best-effort: a failed upload just means the container keeps its own.
        try:
            archive_path = await _hydrate_saves_to_webstation(
                request.user.id, rom.id, container
            )
        except Exception:
            log.exception("save hydration failed, continuing launch")
        # With no pick to push, the restored archive is the resume: it carries
        # the autosave slot's state file alongside the in-game saves, so
        # loading that slot replays where the last session left off.
        caps = platform_capabilities(platform)
        if (
            not resume_after_launch
            and archive_path is not None
            and caps["has_autosave"]
        ):
            resume_slot = caps["autosave_slot"]
            resume_pushed = True
    elif memory_card is None:
        # Legacy per-file save sync (containers without memory_card_sync).
        # Best-effort: a failed hydration just means the container keeps its own.
        try:
            await _hydrate_saves_to_broker(request.user.id, rom.id, container)
        except Exception:
            log.exception("save hydration failed, continuing launch")

    try:
        # Tell the broker to load the ROM, raises HTTPException on failure.
        # Wrapped in asyncio.to_thread because urllib is synchronous.
        if _is_webstation(container):
            launch_result = await asyncio.to_thread(
                _webstation_activate,
                container,
                session_id=str(session["broker_session_id"]),
                user=request.user,
                emulator=_emulator_for_container(container),
                rom={
                    "id": rom.id,
                    "name": rom_name,
                    "platform": platform,
                    "path": rom_path,
                },
                archive_path=archive_path,
                resume_slot=(
                    resume_slot if resume_pushed or resume_after_launch else None
                ),
                memory_card_synced=memory_card is not None,
            )
        else:
            launch_result = await asyncio.to_thread(
                _call_broker,
                container,
                rom_path,
                rom_name,
                resume_slot if resume_pushed else None,
            )
    except Exception:
        # Launch failed, free the claim so the container isn't wedged.
        await async_cache.delete(_session_redis_key(session_key))
        if created_blank_card_id is not None:
            db_memory_card_handler.delete_card(created_blank_card_id)
        raise

    log.info("session claimed, platform=%s rom=%s", platform, rom_name)

    # The webstation broker's deferred load waits for its emulator to report
    # the game running, and holds off further until the state file is there, so
    # this push lands ahead of it even though it runs after activate.
    if resume_after_launch and resume_state is not None:
        resume_pushed = await _push_resume_state(container, resume_state)

    # Hydrate the container with the user's newest stored state in the
    # background, the stream should not wait on file transfers.
    _spawn_sync_task(
        _hydrate_states_to_broker(
            request.user.id,
            rom.id,
            container,
            resume_pushed=resume_pushed,
        )
    )

    host = container.get("host", "")
    if _is_webstation(container):
        # Activate answers with the room URL carrying the claiming user's
        # token, relative to the container root. An absolute path replaces
        # whatever path the configured host carries.
        room_url = (
            str(launch_result.get("url", "")) if isinstance(launch_result, dict) else ""
        )
        if room_url:
            host = urljoin(host, room_url)
    else:
        # The broker mints a stream token bound to this session and returns it
        # in the launch body. Append it so the iframe URL carries it, the broker
        # swaps it for a cookie on first load. No token means the gate is not
        # deployed on that container, so leave host untouched.
        stream_token = (
            launch_result.get("stream_token", "")
            if isinstance(launch_result, dict)
            else ""
        )
        if stream_token:
            sep = "&" if "?" in host else "?"
            host = f"{host}{sep}stream_token={stream_token}"

    return JSONResponse(
        {
            "platform": platform,
            "host": host,
            "label": container.get("label", platform.upper()),
            "rom_name": rom_name,
            "claimed_at": now,
            # None when no resume was requested; False signals the frontend
            # to tell the player the session started fresh.
            "resume": resume_pushed if req.state_id is not None else None,
        }
    )


@protected_route(
    router.post, "/sessions/{platform}/save-and-exit", [Scope.ROMS_USER_WRITE]
)
async def save_and_exit_session(
    request: Request, platform: str, req: Annotated[SaveAndExitRequest, Body()]
) -> JSONResponse:
    """
    Save game state then release the session.
    wait=true (default): blocks until broker confirms save+kill complete.
    wait=false: broker fires save+kill in background, returns immediately.
    """
    container, session_key, session = await _resolve_owned_session(platform, request)

    # Whole-card sync must evacuate a quiescent card, so force a blocking
    # save+kill for these containers even on the navigate-away (wait=false)
    # path. Otherwise the evacuate below can read a card the emulator is
    # still writing, and the wipe can race its exit flush.
    card_sync = _memory_card_sync_enabled(container)
    effective_wait = True if card_sync else req.wait
    saved, effective_slot = await asyncio.to_thread(
        _save_and_exit_broker, container, slot=req.slot, wait=effective_wait
    )

    # Evacuate the whole card while the claim still guards the container, so a
    # concurrent claim cannot wipe it first. The save+kill above was blocking
    # on the card-sync path, so the game is stopped and the card is quiescent.
    # Awaited before the key is released.
    safe_to_wipe = await _evacuate_session_card(session, container)
    if safe_to_wipe:
        await _wipe_session_card(container)

    if effective_wait:
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

    await _record_play_session(session)

    # Sync the exit save to the library. With wait=false the broker save may
    # still be running; the pull blocks on the broker until it finishes.
    rom_id = session.get("rom_id")
    if isinstance(rom_id, int) and (saved or not effective_wait):
        _spawn_sync_task(
            _pull_state_to_library(request.user.id, rom_id, container, effective_slot)
        )

    # Legacy per-file in-game save pull, only for containers not on whole-card
    # sync (those were evacuated above, independent of any savestate).
    if isinstance(rom_id, int) and not card_sync:
        _spawn_sync_task(
            _pull_saves_to_library(
                request.user.id,
                rom_id,
                container,
                _broker_session_id(session),
            )
        )

    log.info("save-and-exit, platform=%s saved=%s", platform, saved)
    return JSONResponse({"status": "ok", "saved": saved, "platform": platform})


@protected_route(router.post, "/sessions/{platform}/heartbeat", [Scope.ROMS_USER_WRITE])
async def heartbeat_session(request: Request, platform: str) -> JSONResponse:
    """Refresh the session's liveness stamp and report whether it still exists.

    The frontend calls this every ~30s while a session is active. A session
    that stops refreshing counts as abandoned after _SESSION_STALE_SECONDS
    and the next claim may take the container over.

    Reports `ended` rather than raising 404 when the caller no longer holds the
    session, so a force-released player learns why on the poll they are already
    making rather than watching a dead stream.
    """
    candidates = _containers_for_platform(platform)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{platform}'",
        )
    found = await _find_session_for_user(candidates, request.user.id)
    if found is None:
        return JSONResponse(await _session_status(platform, request))
    _, session_key, session = found

    session["last_seen"] = datetime.now(timezone.utc).isoformat()
    # XX: only rewrite a key that still exists, so a heartbeat racing a
    # teardown cannot resurrect a released session as a ghost claim. The
    # rewrite also resets the TTL back to the full window.
    await async_cache.set(
        _session_redis_key(session_key),
        json.dumps(session),
        xx=True,
        ex=SESSION_TTL_SECONDS,
    )
    return JSONResponse({"status": "active", "platform": platform})


@protected_route(router.get, "/sessions/{platform}/status", [Scope.ROMS_READ])
async def session_status(request: Request, platform: str) -> JSONResponse:
    """Does the caller still hold this platform's session?

    Unlike the heartbeat this has no side effects, so a client can call it on
    mount or after a reconnect without extending a claim it may not own.
    """
    return JSONResponse(await _session_status(platform, request))


@protected_route(router.post, "/sessions/{platform}/volume", [Scope.ROMS_USER_WRITE])
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


@protected_route(router.post, "/sessions/{platform}/mute", [Scope.ROMS_USER_WRITE])
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


@protected_route(
    router.post, "/sessions/{platform}/save-state", [Scope.ROMS_USER_WRITE]
)
async def save_state(
    request: Request, platform: str, req: Annotated[SaveStateRequest, Body()]
) -> JSONResponse:
    """Save game state to a slot without stopping the emulator.

    The autosave slot is a valid target: the library keeps every capture, so
    the player writes through one slot rather than picking one.
    """
    container, session_key, session = await _resolve_owned_session(platform, request)
    _assert_valid_slot(platform, req.slot)

    ok = await asyncio.to_thread(_save_state_broker, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to save state")

    await _refresh_session(session_key)

    # Every save syncs to the library in the background. The broker holds the
    # /state-file response until the emulator finishes writing the slot.
    rom_id = session.get("rom_id")
    if isinstance(rom_id, int):
        _spawn_sync_task(
            _pull_state_to_library(request.user.id, rom_id, container, req.slot)
        )

    return JSONResponse({"status": "saving", "slot": req.slot, "platform": platform})


@protected_route(
    router.post, "/sessions/{platform}/state-frame", [Scope.ROMS_USER_WRITE]
)
async def put_state_frame(request: Request, platform: str) -> JSONResponse:
    """Stash a frame the browser grabbed off the stream canvas, for the state
    save that follows it to pick up as its thumbnail."""
    _, session_key, session = await _resolve_owned_session(platform, request)

    image = await request.body()
    if not image.startswith(_PNG_MAGIC):
        raise HTTPException(status_code=400, detail="Frame must be a PNG")
    if len(image) > _STATE_SCREENSHOT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Frame too large")

    rom_id = session.get("rom_id")
    if not isinstance(rom_id, int):
        raise HTTPException(status_code=409, detail="Session has no rom")

    await _stash_state_frame(request.user.id, rom_id, image)
    await _refresh_session(session_key)
    return JSONResponse({"status": "ok", "platform": platform})


@protected_route(
    router.post, "/sessions/{platform}/load-state", [Scope.ROMS_USER_WRITE]
)
async def load_state(
    request: Request, platform: str, req: Annotated[LoadStateRequest, Body()]
) -> JSONResponse:
    """Load game state from a manual slot or the platform's autosave slot."""
    container, session_key, _ = await _resolve_owned_session(platform, request)
    _assert_valid_slot(platform, req.slot)

    ok = await asyncio.to_thread(_load_state_broker, container, req.slot)
    if not ok:
        raise HTTPException(status_code=502, detail="Broker failed to load state")

    await _refresh_session(session_key)
    return JSONResponse(
        {"status": "ok", "loaded": True, "slot": req.slot, "platform": platform}
    )


@protected_route(router.delete, "/sessions/{platform}", [Scope.ROMS_USER_WRITE])
async def release_session(
    request: Request,
    platform: str,
    reason: str | None = Query(default=None, max_length=200),
    container_key: str | None = Query(default=None, alias="container", max_length=300),
) -> JSONResponse:
    """Release a session and tell the broker to stop the emulator.

    `reason` is only meaningful when an admin ends someone else's session; it
    is surfaced to the displaced player. `container` names which container to
    release, needed when a pool serves the platform and the admin is ending a
    session they do not own; it is the key `GET /streaming/sessions` reports.
    """
    if container_key is not None:
        container, session_key, session = await _resolve_named_container(
            platform, container_key
        )
        if session is None:
            return JSONResponse({"status": "not_found", "platform": platform})
        _assert_session_owner(session, request)
    else:
        try:
            container, session_key, session = await _resolve_owned_session(
                platform, request
            )
        except HTTPException as exc:
            # Nothing configured or nothing active: releasing is a no-op rather
            # than an error, matching a repeated release from the same tab.
            if exc.status_code != 404:
                raise
            return JSONResponse({"status": "not_found", "platform": platform})

    # Teardown pulls the whole card off the broker and pushes a blank one back,
    # several seconds of broker round-trips. The player who quit does not need
    # the claim released to get their UI back, so it runs after the response is
    # sent. The Redis claim stays held until teardown deletes it, so a re-launch
    # or concurrent claim is still blocked throughout, preserving the
    # evacuate-before-release invariant.
    teardown = BackgroundTask(
        _teardown_released_session,
        container,
        session,
        session_key,
        platform,
        acting_user_id=request.user.id,
        acting_username=request.user.username,
        reason=reason,
    )
    log.info("session releasing, platform=%s", platform)
    return JSONResponse(
        {"status": "released", "platform": platform}, background=teardown
    )


async def _teardown_released_session(
    container: dict[str, Any],
    session: dict[str, Any],
    session_key: str,
    platform: str,
    *,
    acting_user_id: int,
    acting_username: str,
    reason: str | None,
) -> None:
    """Stop the emulator, evacuate the card, then release the claim.

    Ordering is load-bearing (see the inline notes). Runs detached from the
    release request; every step is best-effort so a teardown hiccup cannot wedge
    the claim, which the stale-session takeover reclaims if this never finishes.
    """
    try:
        # Stop the emulator first so the card is quiescent before evacuation: a
        # running game's exit flush could otherwise re-lay a card over the wipe,
        # and reading a live card risks a torn snapshot. The claim still guards
        # the container throughout, so no concurrent claim can interleave.
        state_slot = await asyncio.to_thread(_stop_broker, container)

        # Evacuate the whole card, then wipe the slot, both before releasing the
        # claim so a concurrent claim cannot clobber the fresh card or inherit
        # the old one. Wipe runs only when evacuation captured the card.
        safe_to_wipe = await _evacuate_session_card(session, container)
        if safe_to_wipe:
            await _wipe_session_card(container)

        # Leave a note when this is a force-release rather than a player closing
        # their own game. A different user is the obvious case; a reason covers
        # the rest, since only the admin panel sends one and an admin can be
        # logged in as the same account that is playing in another tab.
        if session.get("user_id") != acting_user_id or reason is not None:
            await _record_termination(
                session, session_key, ended_by=acting_username, reason=reason
            )
            log.info(
                "session force-released, platform=%s by=%s user_id=%s reason=%s",
                platform,
                acting_username,
                session.get("user_id"),
                reason or "-",
            )

        await _record_play_session(session)

        rom_id = session.get("rom_id")
        # Awaited, not spawned: the broker holds the exited session's state only
        # until the next activate, and releasing the claim below is what lets
        # that activate happen.
        if isinstance(rom_id, int) and state_slot is not None:
            await _pull_state_to_library(
                session["user_id"], rom_id, container, state_slot
            )

        # Legacy per-file save pull, only for containers not on whole-card sync.
        # Fire and forget: it reads files the broker keeps after the emulator
        # dies, so it does not gate the claim release above it.
        if isinstance(rom_id, int) and not _memory_card_sync_enabled(container):
            _spawn_sync_task(
                _pull_saves_to_library(
                    session["user_id"],
                    rom_id,
                    container,
                    _broker_session_id(session),
                )
            )

        log.info("session released, platform=%s", platform)
    except Exception:
        log.exception("session teardown failed, platform=%s", platform)
    finally:
        # The claim goes even when a step above raised. The API already told the
        # caller the session was released, so a key left behind blocks every
        # later claim until stale takeover or the TTL expires. A card left
        # un-evacuated is recoverable, since the next claim prompts to adopt
        # whatever is still on the container; a phantom claim is not.
        await async_cache.delete(_session_redis_key(session_key))


def _container_by_key(container_key: str) -> tuple[dict[str, Any], str]:
    """A configured container named by its key, plus the platform to file its
    sessions under.

    The session routes are platform-keyed, so a container serving several gets
    the first, which `_container_for_session` resolves back to this entry.
    Raises 404 when the key names no container.
    """
    entries = _containers_by_key().get(container_key) if container_key else None
    if not entries or not _get_streaming_config().get("enabled", False):
        raise HTTPException(
            status_code=404, detail=f"No streaming container '{container_key}'"
        )
    return entries[0], str(entries[0].get("platform", ""))


@protected_route(router.get, "/containers", [Scope.ROMS_READ])
async def list_containers(request: Request) -> JSONResponse:
    """Admin view, one row per configured container with whatever it is running.

    One row per container rather than per platform: a container serves many
    platforms but hosts one session, so the platform rows the frontend gets
    from `/streaming/config` are the wrong unit for operating the fleet.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    cfg = _get_streaming_config()
    containers: list[dict[str, Any]] = []
    for container_key, entries in _containers_by_key().items():
        first = entries[0]
        session = await _get_session(container_key) if container_key else None
        user_id = session.get("user_id") if session else None
        user = db_user_handler.get_user(user_id) if isinstance(user_id, int) else None
        containers.append(
            {
                "container": container_key,
                "label": first.get("label"),
                "host": first.get("host"),
                "platforms": [e.get("platform") for e in entries if e.get("platform")],
                # The desktop emulator lives on the webstation broker only; the
                # per-emulator mods have no activate route to ask for it.
                "supports_desktop": _is_webstation(first),
                # A container whose host has no scheme has an empty key and can
                # never be claimed, so surface it rather than listing it as idle.
                "configured": bool(container_key),
                "session": (
                    {
                        "platform": session.get("platform"),
                        "rom_id": session.get("rom_id"),
                        "rom_name": session.get("rom_name"),
                        "desktop": bool(session.get("desktop")),
                        "claimed_at": session.get("claimed_at"),
                        "user_id": user_id,
                        "username": user.username if user else None,
                    }
                    if session
                    else None
                ),
            }
        )
    return JSONResponse(
        {"enabled": cfg.get("enabled", False), "containers": containers}
    )


@protected_route(router.post, "/desktop", [Scope.ROMS_USER_WRITE])
async def claim_desktop_session(
    request: Request, req: Annotated[DesktopSessionRequest, Body()]
) -> JSONResponse:
    """Admin, open a container's desktop with no game running.

    This is how an operator configures an emulator (BIOS, controllers, paths)
    inside the container that will run it. The desktop claims the same key
    under the same SET NX as a game, so it blocks players and a running game
    blocks it: only one thing can drive the container's display.

    Returns 404 for an unknown container, 409 when it is occupied, 502/503 when
    the broker rejects the activation or is unreachable.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    container, platform = _container_by_key(req.container)
    if not _is_webstation(container):
        raise HTTPException(
            status_code=400,
            detail="This container's broker does not serve a desktop session",
        )

    session_key = _container_key(container)
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "user_id": request.user.id,
        "broker_session_id": secrets.token_hex(8),
        # No ROM and no card. Teardown reads both and skips the save pull, the
        # card evacuation and the playtime credit when they are absent, which
        # is what a desktop session wants: nothing of it belongs in a library.
        "rom_id": None,
        "rom_name": None,
        "memory_card_id": None,
        "desktop": True,
        "platform": platform,
        "claimed_at": now,
        "last_seen": now,
    }
    # No stale takeover here, unlike a player's claim: the admin named this
    # container, so displacing whoever holds it should be their explicit call
    # through release, not a side effect of asking for the desktop.
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
                "message": "Container in use",
                "rom_name": existing.get("rom_name"),
                "claimed_at": existing.get("claimed_at"),
            },
        )

    try:
        launch_result = await asyncio.to_thread(
            _webstation_activate,
            container,
            session_id=str(session["broker_session_id"]),
            user=request.user,
            emulator="desktop",
        )
    except Exception:
        # Activation failed, free the claim so the container isn't wedged.
        await async_cache.delete(_session_redis_key(session_key))
        raise

    host = container.get("host", "")
    room_url = str(launch_result.get("url", "")) if launch_result else ""
    if room_url:
        host = urljoin(host, room_url)

    log.info("desktop session claimed, container=%s", session_key)
    return JSONResponse(
        {
            "container": session_key,
            "platform": platform,
            "host": host,
            "label": container.get("label", platform.upper()),
            "claimed_at": now,
        }
    )


@protected_route(router.get, "/sessions", [Scope.ROMS_READ])
async def list_sessions(request: Request) -> JSONResponse:
    """Admin view, active sessions across all configured containers.

    Entries carry the platform the session was claimed under so an admin
    client can release one through `DELETE /sessions/{platform}`.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    grouped = _containers_by_key()

    sessions: list[dict[str, Any]] = []
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
        container_key = key_str.removeprefix(_SESSION_KEY_PREFIX)
        container = (
            _container_for_session(grouped, container_key, s.get("platform")) or {}
        )
        user_id = s.get("user_id")
        user = db_user_handler.get_user(user_id) if user_id is not None else None
        sessions.append(
            {
                "container": container_key,
                "label": container.get("label"),
                "platform": s.get("platform"),
                "rom_id": s.get("rom_id"),
                "rom_name": s.get("rom_name"),
                "desktop": bool(s.get("desktop")),
                "claimed_at": s.get("claimed_at"),
                "user_id": user_id,
                "username": user.username if user else None,
            }
        )
    return JSONResponse({"sessions": sessions})


@protected_route(router.delete, "/sessions", [Scope.ROMS_USER_WRITE])
async def force_release_all(
    request: Request, reason: str | None = Query(default=None, max_length=200)
) -> JSONResponse:
    """Admin, force-release all active sessions.

    `reason` is surfaced to every displaced player alongside the admin's name.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Map container keys back to configs so each broker can be told to stop -
    # deleting only the Redis keys would leave the games running.
    grouped = _containers_by_key()

    async def _teardown(key: str | bytes, container_key: str) -> None:
        # Read before the teardown so the displaced player can be identified
        # even when the container config has since been removed.
        session = await _get_session(container_key)
        container = _container_for_session(
            grouped, container_key, session.get("platform") if session else None
        )

        # Stop the emulator, then evacuate and wipe the card, all while the claim
        # still guards the container and before deleting the key. Stopping first
        # quiesces the card so an exit flush cannot undo the wipe.
        if container is not None:
            # Best-effort stop; a broker error must not abort the sweep.
            await asyncio.to_thread(_stop_broker, container)
            if session is not None:
                safe_to_wipe = await _evacuate_session_card(session, container)
                if safe_to_wipe:
                    await _wipe_session_card(container)
                # Credit playtime to the session's owner, not the admin.
                await _record_play_session(session)

        # Note who ended it before the key goes, so the player's next poll can
        # explain the stream vanishing.
        if session is not None:
            await _record_termination(
                session, container_key, ended_by=request.user.username, reason=reason
            )

        await async_cache.delete(key)

    released = []
    teardowns = []
    async for key in async_cache.scan_iter(match=f"{_SESSION_KEY_PREFIX}*"):
        # scan_iter yields bytes unless the client decodes responses.
        key_str = key.decode() if isinstance(key, bytes) else key
        container_key = key_str.removeprefix(_SESSION_KEY_PREFIX)
        released.append(container_key)
        teardowns.append(_teardown(key, container_key))

    # Tear down concurrently so one slow or stuck broker cannot serialize the
    # whole sweep behind its timeout.
    results = await asyncio.gather(*teardowns, return_exceptions=True)
    for container_key, result in zip(released, results, strict=False):
        if isinstance(result, BaseException):
            log.warning("force-release failed for %s, %s", container_key, result)

    log.info("all sessions force-released by admin, %s", released)
    return JSONResponse({"status": "released", "platforms": released})
