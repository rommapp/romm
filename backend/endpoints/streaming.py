from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.config_manager import config_manager as cm

try:
    import config

    # In RomM, the full parsed YAML is often stored in 'ROMM_CONFIG'
    # or accessible via a function in the config module.
    config_handler = config
except ImportError:
    config_handler = None
    # This will tell you EXACTLY why the config is failing in your logs
    logging.getLogger("romm").error(f"streaming: failed to import config_handler: {e}")

log = logging.getLogger("romm")

router = APIRouter(prefix="/streaming", tags=["streaming"])

_sessions: dict[str, dict[str, Any]] = {}


class ClaimSessionRequest(BaseModel):
    platform: str
    rom_path: str
    rom_name: str


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


def _stop_broker(container: dict[str, Any]) -> None:
    """Tell the broker to stop emulator. Best-effort — don't raise on failure."""
    url = _broker_url(container, "/launch")
    secret = container.get("broker_secret", "")
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

    # Tell the broker to load the ROM — raises HTTPException on failure
    _call_broker(container, req.rom_path, req.rom_name)

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


@router.delete("/sessions/{platform}")
async def release_session(platform: str) -> JSONResponse:

    # Release a session. Also tells the broker to stop PCSX2.
    released = _sessions.pop(platform, None)

    if released is None:
        return JSONResponse({"status": "not_found", "platform": platform})

    # Best-effort stop, don't block user
    container = _container_for_platform(platform)
    if container:
        _stop_broker(container)

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
