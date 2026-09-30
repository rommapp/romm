from typing import Any

from handler.database import (
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from models.assets import Save, Screenshot, State
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
