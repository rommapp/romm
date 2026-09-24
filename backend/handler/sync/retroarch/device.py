"""Registers the RetroArch install a user syncs from as a RomM device."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from handler.database import db_device_handler
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from models.device import KNOWN_DEVICES, Device
from models.user import User

# RetroArch's WebDAV requests carry no install identity, so each user gets a
# single RetroArch device, deduped by the (user, client identifier) index.
CLIENT_DEVICE_IDENTIFIER = "retroarch"


def touch_retroarch_device(user: User) -> None:
    """Creates the user's RetroArch device on first sync, else bumps `last_seen`."""
    existing = db_device_handler.get_device_by_client_identifier(
        user_id=user.id, client_device_identifier=CLIENT_DEVICE_IDENTIFIER
    )
    if existing:
        db_device_handler.update_last_seen_debounced(device_id=existing.id)
        return

    device_type = KNOWN_DEVICES["retroarch"]
    try:
        device = db_device_handler.add_device(
            Device(
                id=str(uuid.uuid4()),
                user_id=user.id,
                name="RetroArch",
                platform=device_type.platform,
                client=device_type.client,
                client_device_identifier=CLIENT_DEVICE_IDENTIFIER,
                sync_mode=device_type.sync_mode,
                last_seen=datetime.now(timezone.utc),
            )
        )
    except IntegrityError:
        # A concurrent first sync registered it.
        return

    log.info(
        f"Auto-created RetroArch device {device.id} for user {hl(user.username, color=CYAN)}"
    )
