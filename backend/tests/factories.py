from datetime import datetime
from typing import Any

from handler.auth.base_handler import auth_handler
from handler.database import (
    db_client_token_handler,
    db_firmware_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from models.assets import Save, Screenshot, State
from models.client_token import ClientToken
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User


def make_rom(
    platform: Platform,
    name: str,
    /,
    *,
    fs_stem: str | None = None,
    fs_extension: str = "zip",
    **overrides: Any,
) -> Rom:
    """Persist a ROM whose slug and filename fields derive from `name`.

    Args:
        fs_stem: The filename without its extension, defaulting to `name`.
        fs_extension: The file extension, or empty for a folder ROM.
    """
    stem = name if fs_stem is None else fs_stem
    fields: dict[str, Any] = {
        "platform_id": platform.id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "fs_name": f"{stem}.{fs_extension}" if fs_extension else stem,
        "fs_name_no_tags": stem,
        "fs_name_no_ext": stem,
        "fs_extension": fs_extension,
        "fs_path": f"{platform.slug}/roms",
    }
    return db_rom_handler.add_rom(Rom(**(fields | overrides)))


def make_esrb_rated_rom(platform: Platform, name: str, esrb: str, /) -> Rom:
    """Persist a ROM whose only age rating is IGDB's ESRB `esrb`."""
    return make_rom(
        platform,
        name,
        igdb_metadata={
            "age_ratings": [
                {"category": "ESRB", "rating": esrb, "rating_cover_url": ""}
            ]
        },
    )


def _asset_fields(rom: Rom, user: User, file_name: str, folder: str) -> dict[str, Any]:
    return {
        "rom_id": rom.id,
        "user_id": user.id,
        "file_name": file_name,
        "file_path": f"{rom.platform_slug}/{folder}",
    }


def make_save(rom: Rom, user: User, file_name: str, /, **overrides: Any) -> Save:
    """Persist a save; the model derives the filename parts from `file_name`."""
    fields = _asset_fields(rom, user, file_name, "saves")
    return db_save_handler.add_save(Save(**(fields | overrides)))


def make_state(rom: Rom, user: User, file_name: str, /, **overrides: Any) -> State:
    """Persist a state; the model derives the filename parts from `file_name`."""
    fields = _asset_fields(rom, user, file_name, "states")
    return db_state_handler.add_state(State(**(fields | overrides)))


def make_screenshot(
    rom: Rom, user: User, file_name: str, /, **overrides: Any
) -> Screenshot:
    """Persist a screenshot; the model derives the filename parts from `file_name`."""
    fields = _asset_fields(rom, user, file_name, "screenshots")
    return db_screenshot_handler.add_screenshot(Screenshot(**(fields | overrides)))


def make_firmware(
    platform: Platform, file_name: str, /, *, missing: bool = False, **overrides: Any
) -> Firmware:
    """Persist a BIOS file row, present on disk unless `missing`."""
    fields: dict[str, Any] = {
        "platform_id": platform.id,
        "file_name": file_name,
        "file_path": f"{platform.fs_slug}/bios",
        "file_size_bytes": 1024,
        "crc_hash": "crc",
        "md5_hash": "md5",
        "sha1_hash": "sha1",
        "missing_from_fs": missing,
    }
    return db_firmware_handler.add_firmware(Firmware(**(fields | overrides)))


def make_device_token(
    user: User,
    device_id: str | None,
    /,
    *,
    scopes: str = "devices.read devices.write roms.read",
    expires_at: datetime | None = None,
    **overrides: Any,
) -> tuple[ClientToken, str]:
    """Persist a client token bound to `device_id`, or unbound when it is None.

    Returns:
        The stored token and the raw `rmm_` credential a client sends.
    """
    raw_token = auth_handler.generate_client_token()
    fields: dict[str, Any] = {
        "user_id": user.id,
        "name": "Handheld",
        "hashed_token": auth_handler.hash_client_token(raw_token),
        "scopes": scopes,
        "expires_at": expires_at,
        "device_id": device_id,
    }
    token = db_client_token_handler.add_token(ClientToken(**(fields | overrides)))
    return token, raw_token
