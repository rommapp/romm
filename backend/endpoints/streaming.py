from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.config_manager import config_manager as cm

try:
    import config

    # In RomM, the full parsed YAML is often stored in 'ROMM_CONFIG'
    # or accessible via a function in the config module.
    config_handler = config  # type: ignore[assignment]
except ImportError as e:
    config_handler = None  # type: ignore[assignment]
    # This will tell you EXACTLY why the config is failing in your logs
    logging.getLogger("romm").error(f"streaming: failed to import config_handler: {e}")

log = logging.getLogger("romm")

router = APIRouter(prefix="/streaming", tags=["streaming"])

_sessions: dict[str, dict[str, Any]] = {}


class ClaimSessionRequest(BaseModel):
    platform: str
    rom_path: str
    rom_name: str


class SaveAndExitRequest(BaseModel):
    slot: Annotated[int, Field(ge=0, le=10)] = 0
    wait: bool = True


class VolumeRequest(BaseModel):
    level: Annotated[int, Field(ge=0, le=100)]


class MuteRequest(BaseModel):
    mute: bool | None = None  # None = toggle, True/False = explicit set


class StateRequest(BaseModel):
    slot: Annotated[int, Field(ge=1, le=9)] = 1


def _get_streaming_config() -> dict[str, Any]:
    """Extract streaming config from the parsed Config object"""
    try:
        cfg = cm.get_config()

        enabled = getattr(cfg, "STREAMING_ENABLED", False)
        containers = getattr(cfg, "STREAMING_CONTAINERS", [])

        return {"enabled": enabled, "containers": containers}

    except Exception as e:
        log.error(f"streaming: Failed to extract config from cm: {e}")
        return {"enabled": False, "containers": []}


def _container_for_platform(platform: str) -> dict[str, Any] | None:
    cfg = _get_streaming_config()
    if not cfg.get("enabled", False):
        return None
    for entry in cfg.get("containers", []):
        if entry.get("platform") == platform:
            return entry
    return None


# broker communication


def _broker_url(container: dict[str, Any], path: str) -> str:
    """
    Build the URL for the ROM broker API.

    The broker runs inside the emulator container on BROKER_PORT (default 8000).
    `broker_host` in config.yml is the host:port of the broker endpoint —
    separate from `host` which is the browser-facing stream URL.

    If broker_host is not set, we assume it is on the same host and swap the port.
    Example:
      host:         http://192.168.1.51:3000   (Selkies web UI, browser-facing)
      broker_host:  http://192.168.1.51:8000   (broker API, server-to-server)
    """
    broker_host = container.get("broker_host", "").rstrip("/")

    if not broker_host:
        # Derive broker URL from stream host — replace port with 8000
        stream_host = container.get("host", "").rstrip("/")
        # Parse out just the scheme + hostname, replace port
        # e.g. http://192.168.1.51:3000 → http://192.168.1.51:8000
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(stream_host)
            broker_host = urlunparse(parsed._replace(netloc=f"{parsed.hostname}:8000"))
        except Exception:
            broker_host = stream_host

    return f"{broker_host}{path}"


def _call_broker(container: dict[str, Any], rom_path: str, rom_name: str) -> None:
    """
    POST to the broker's /launch endpoint to tell the PCSX2 container to
    load a ROM. Uses only Python stdlib urllib — no extra dependencies.

    Raises HTTPException if the broker is unreachable or returns an error.
    """
    url = _broker_url(container, "/launch")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))

    payload = json.dumps(
        {
            "rom_path": rom_path,
            "rom_name": rom_name,
        }
    ).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            log.info("streaming: broker launched ROM — %s", body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        log.error("streaming: broker HTTP error %d — %s", exc.code, error_body)
        try:
            detail = json.loads(error_body)
        except Exception:
            detail = error_body
        raise HTTPException(
            status_code=502,
            detail=f"Broker returned {exc.code}: {detail}",
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        log.error("streaming: broker unreachable at %s — %s", url, exc)
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
    POST /save-and-exit to the broker. Best-effort — logs but never raises.
    With wait=True the call blocks until save+kill completes (use for button press).
    With wait=False the broker fires save+kill in the background (use for navigation away).
    Returns True if the broker reported a successful save.
    """
    url = _broker_url(container, "/save-and-exit")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    payload = json.dumps({"slot": slot, "wait": wait}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )
    timeout = 20 if wait else 5
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            saved = bool(body.get("saved", False))
            log.info(
                "streaming: broker save-and-exit — saved=%s slot=%d wait=%s",
                saved,
                slot,
                wait,
            )
            return saved
    except Exception as exc:
        log.warning("streaming: broker save-and-exit failed — %s", exc)
        return False


def _volume_broker(container: dict[str, Any], level: int) -> bool:
    """POST /volume to the broker. Best-effort — logs but never raises."""
    url = _broker_url(container, "/volume")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    payload = json.dumps({"level": level}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            log.debug("streaming: broker volume set to %d — %s", level, body)
            return body.get("status") == "ok"
    except Exception as exc:
        log.warning("streaming: broker volume failed — %s", exc)
        return False


def _mute_broker(container: dict[str, Any], mute: bool | None) -> bool | None:
    """POST /mute to the broker. Returns confirmed mute state, or None on error."""
    url = _broker_url(container, "/mute")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    body_dict: dict[str, Any] = {} if mute is None else {"mute": mute}
    payload = json.dumps(body_dict).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            confirmed = body.get("mute")
            log.debug("streaming: broker mute — %s", body)
            return confirmed
    except Exception as exc:
        log.warning("streaming: broker mute failed — %s", exc)
        return None


def _save_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /save-state to the broker. Returns True if the request was accepted."""
    url = _broker_url(container, "/save-state")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    payload = json.dumps({"slot": slot}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            log.debug("streaming: broker save-state slot=%d — %s", slot, body)
            return body.get("status") == "saving"
    except Exception as exc:
        log.warning("streaming: broker save-state failed — %s", exc)
        return False


def _load_state_broker(container: dict[str, Any], slot: int) -> bool:
    """POST /load-state to the broker. Returns True if broker confirmed success."""
    url = _broker_url(container, "/load-state")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    payload = json.dumps({"slot": slot}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            **({"X-Broker-Secret": secret} if secret else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            loaded = bool(body.get("loaded", False))
            log.debug("streaming: broker load-state slot=%d loaded=%s", slot, loaded)
            return loaded
    except Exception as exc:
        log.warning("streaming: broker load-state failed — %s", exc)
        return False


def _stop_broker(container: dict[str, Any]) -> None:
    """Tell the broker to stop emulator. Best-effort — don't raise on failure."""
    url = _broker_url(container, "/launch")
    secret = os.environ.get("BROKER_SECRET", container.get("broker_secret", ""))
    req = urllib.request.Request(
        url,
        method="DELETE",
        headers={**({"X-Broker-Secret": secret} if secret else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as exc:
        log.warning("streaming: could not stop broker session — %s", exc)


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/config")
async def get_config() -> JSONResponse:
    """Return streaming configuration to the frontend"""
    cfg = _get_streaming_config()

    safe_containers = []
    for c in cfg.get("containers", []):
        if not c.get("platform") or not c.get("host"):
            continue

        safe_containers.append(
            {
                "platform": c.get("platform"),
                "host": c.get("host"),
                "label": c.get("label") or c.get("platform", "").upper(),
            }
        )

    return JSONResponse(
        {
            "enabled": cfg.get("enabled", False),
            "containers": safe_containers,
        }
    )


@router.post("/sessions")
async def claim_session(req: ClaimSessionRequest, request: Request) -> JSONResponse:
    """
    Claim a streaming session and tell the broker to load the ROM.
    returns 404 is not configured for that platform
    returns 409 if the platform is already occupied
    returns 503 if the broker is unreachable
    """
    container = _container_for_platform(req.platform)

    if container is None:
        raise HTTPException(
            status_code=404,
            detail=f"No streaming container configured for platform '{req.platform}'",
        )

    existing = _sessions.get(req.platform)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Session in use",
                "rom_name": existing["rom_name"],
                "claimed_at": existing["claimed_at"],
            },
        )

    # Tell the broker to load the ROM — raises HTTPException on failure.
    # Wrapped in asyncio.to_thread because urllib is synchronous.
    await asyncio.to_thread(_call_broker, container, req.rom_path, req.rom_name)

    now = datetime.utcnow().isoformat()
    _sessions[req.platform] = {
        "rom_path": req.rom_path,
        "rom_name": req.rom_name,
        "claimed_at": now,
        "user_id": str(request.client.host) if request.client else "unknown",
    }

    log.info(
        "streaming: session claimed — platform=%s rom=%s", req.platform, req.rom_name
    )

    return JSONResponse(
        {
            "platform": req.platform,
            "host": container["host"],
            "label": container.get("label", req.platform.upper()),
            "rom_name": req.rom_name,
            "claimed_at": now,
        }
    )


@router.post("/sessions/{platform}/save-and-exit")
async def save_and_exit_session(platform: str, req: SaveAndExitRequest) -> JSONResponse:
    """
    Save game state then release the session.
    wait=true (default): blocks until broker confirms save+kill complete.
    wait=false: broker fires save+kill in background, returns immediately.
    """
    session = _sessions.get(platform)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active session for platform '{platform}'",
        )

    container = _container_for_platform(platform)
    saved = False
    if container:
        saved = await asyncio.to_thread(
            _save_and_exit_broker, container, slot=req.slot, wait=req.wait
        )
    else:
        log.warning(
            "streaming: save-and-exit — no container for platform=%s, releasing without save",
            platform,
        )

    _sessions.pop(platform, None)
    log.info("streaming: save-and-exit — platform=%s saved=%s", platform, saved)
    return JSONResponse({"status": "ok", "saved": saved, "platform": platform})


@router.post("/sessions/{platform}/volume")
async def set_volume(platform: str, req: VolumeRequest) -> JSONResponse:
    """Set emulator audio volume (0–100). Best-effort — no 404 if broker unreachable."""
    session = _sessions.get(platform)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )

    container = _container_for_platform(platform)
    ok = False
    if container:
        ok = await asyncio.to_thread(_volume_broker, container, req.level)
    else:
        log.warning("streaming: volume — no container for platform=%s", platform)

    return JSONResponse(
        {"status": "ok" if ok else "error", "level": req.level, "platform": platform}
    )


@router.post("/sessions/{platform}/mute")
async def set_mute(platform: str, req: MuteRequest) -> JSONResponse:
    """Toggle or explicitly set mute state. Omit body to toggle."""
    session = _sessions.get(platform)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )

    container = _container_for_platform(platform)
    confirmed: bool | None = None
    if container:
        confirmed = await asyncio.to_thread(_mute_broker, container, req.mute)
    else:
        log.warning("streaming: mute — no container for platform=%s", platform)

    return JSONResponse({"status": "ok", "mute": confirmed, "platform": platform})


@router.post("/sessions/{platform}/save-state")
async def save_state(platform: str, req: StateRequest) -> JSONResponse:
    """Save game state to a slot (1–9) without stopping the emulator."""
    session = _sessions.get(platform)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )

    container = _container_for_platform(platform)
    ok = False
    if container:
        ok = await asyncio.to_thread(_save_state_broker, container, req.slot)
    else:
        log.warning("streaming: save-state — no container for platform=%s", platform)

    return JSONResponse(
        {"status": "saving" if ok else "error", "slot": req.slot, "platform": platform}
    )


@router.post("/sessions/{platform}/load-state")
async def load_state(platform: str, req: StateRequest) -> JSONResponse:
    """Load game state from a slot (1–9)."""
    session = _sessions.get(platform)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No active session for platform '{platform}'"
        )

    container = _container_for_platform(platform)
    ok = False
    if container:
        ok = await asyncio.to_thread(_load_state_broker, container, req.slot)
    else:
        log.warning("streaming: load-state — no container for platform=%s", platform)

    return JSONResponse(
        {
            "status": "ok" if ok else "error",
            "loaded": ok,
            "slot": req.slot,
            "platform": platform,
        }
    )


@router.delete("/sessions/{platform}")
async def release_session(platform: str) -> JSONResponse:

    # Release a session. Also tells the broker to stop PCSX2.
    released = _sessions.pop(platform, None)

    if released is None:
        return JSONResponse({"status": "not_found", "platform": platform})

    # Best-effort stop, don't block user
    container = _container_for_platform(platform)
    if container:
        await asyncio.to_thread(_stop_broker, container)

    log.info("streaming: session released — platform=%s", platform)
    return JSONResponse({"status": "released", "platform": platform})


@router.get("/sessions")
async def list_sessions() -> JSONResponse:
    """Debug — active sessions."""
    return JSONResponse(
        {
            platform: {
                "rom_name": s["rom_name"],
                "claimed_at": s["claimed_at"],
            }
            for platform, s in _sessions.items()
        }
    )


@router.delete("/sessions")
async def force_release_all() -> JSONResponse:
    # Admin endpoint — force releases all active sessions
    released = list(_sessions.keys())
    _sessions.clear()
    log.info("streaming: all sessions force-released by admin — %s", released)
    return JSONResponse({"status": "released", "platforms": released})
