import uuid
from datetime import datetime, timezone

from fastapi import Request
from ua_parser import parse as parse_ua

from handler.database import db_device_handler
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import Device
from models.user import User


def _parse_platform(user_agent: str) -> str:
    """Extract stable browser + OS family from a User-Agent string.

    Returns something like "Chrome on Mac OS X" or "Firefox on Windows"
    which won't change across browser version updates.
    """
    result = parse_ua(user_agent)

    browser = result.user_agent.family if result.user_agent else None
    os = result.os.family if result.os else None

    if browser and os:
        return f"{browser} on {os}"
    if browser:
        return browser
    if os:
        return os
    return "Unknown Browser"


def create_or_find_web_device(request: Request, user: User) -> Device:
    """Find or create a web browser device for the given user.

    Uses parsed browser/OS family + client IP as fingerprint to avoid
    creating duplicate devices for the same browser.
    """
    user_agent = request.headers.get("user-agent", "")
    platform = _parse_platform(user_agent)
    client_host = request.client.host if request.client else None
    ip_address = request.headers.get("x-forwarded-for", client_host)
    # TODO: differentiate name vs platform vs client better
    existing = db_device_handler.get_device_by_fingerprint(
        user_id=user.id,
        mac_address=None,
        hostname=ip_address,
        platform=platform,
    )
    if existing:
        db_device_handler.update_last_seen(device_id=existing.id, user_id=user.id)
        return existing

    now = datetime.now(timezone.utc)
    device = Device(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="Web Browser",
        platform=platform,
        client="web",
        hostname=ip_address,
        ip_address=ip_address,
        last_seen=now,
    )
    device = db_device_handler.add_device(device)
    log.info(
        f"Auto-created web device {device.id} for user {hl(user.username, color=CYAN)}"
    )
    return device
