import uuid
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from typing import Any

from fastapi import Request
from ua_parser import Result as UAResult
from ua_parser import parse as parse_ua

from handler.auth.constants import SESSION_COOKIE_NAME
from handler.database import db_device_handler
from handler.redis_handler import async_cache
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import KNOWN_DEVICES, Device
from models.user import User
from utils import json_module


async def get_session_from_environ(environ: dict[str, Any]) -> dict[str, Any]:
    """Resolve the auth session for a socket handshake.

    Tries the session the middleware attached to the ASGI scope first; if it's
    absent (scope not propagated to the mounted socket app), falls back to
    parsing the session cookie and reading the session straight from Redis —
    the same lookup RedisSessionMiddleware performs.
    """
    scope = environ.get("asgi.scope", {})
    session = scope.get("session")
    if session:
        return session

    raw_cookie = environ.get("HTTP_COOKIE", "")
    if not raw_cookie:
        return {}

    cookie: SimpleCookie = SimpleCookie()
    cookie.load(raw_cookie)
    morsel = cookie.get(SESSION_COOKIE_NAME)
    if morsel is None:
        return {}

    session_data = await async_cache.get(f"session:{morsel.value}")
    if not session_data:
        return {}
    try:
        return json_module.loads(session_data)
    except Exception:  # noqa: BLE001 - malformed session is "no session"
        return {}


def _get_device_name(user_agent: UAResult) -> str | None:
    """Extract stable browser + OS family from a User-Agent string.

    Returns something like "Chrome on Mac OS X" or "Firefox on Windows"
    which won't change across browser version updates.
    """
    browser = user_agent.user_agent.family if user_agent.user_agent else None
    os = user_agent.os.family if user_agent.os else None

    if browser and os:
        return f"{browser} on {os}"
    if browser:
        return browser

    return os or "Web Browser"


def create_or_find_web_device(request: Request, user: User) -> Device:
    """Find or create a web browser device for the given user.

    Uses parsed browser/OS family + client IP as fingerprint to avoid
    creating duplicate devices for the same browser.
    """
    device_type = KNOWN_DEVICES["web"]

    user_agent = parse_ua(request.headers.get("user-agent", ""))
    client_version = user_agent.user_agent.major if user_agent.user_agent else None
    ip_address = request.client.host if request.client else None

    existing = db_device_handler.get_device_by_fingerprint(
        user_id=user.id,
        ip_address=ip_address,
        platform=device_type.platform,
    )
    if existing:
        db_device_handler.update_last_seen(device_id=existing.id, user_id=user.id)
        return existing

    device = Device(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=_get_device_name(user_agent),
        platform=device_type.platform,
        client=device_type.client,
        client_version=client_version,
        sync_mode=device_type.sync_mode,
        ip_address=ip_address,
        last_seen=datetime.now(timezone.utc),
    )
    device = db_device_handler.add_device(device)
    log.info(
        f"Auto-created web device {device.id} for user {hl(user.username, color=CYAN)}"
    )
    return device
