from typing import Any

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom


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
