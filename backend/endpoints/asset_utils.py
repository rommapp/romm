from fastapi import HTTPException, status
from pathlib import Path
from config import ASSETS_BASE_PATH
from fnmatch import fnmatch
from typing import Callable

def refresh_assets(
    user,
    rom,
    build_path_func: Callable,
    get_db_entries: Callable,
    scan_fn: Callable,
    add_fn: Callable,
    delete_fn: Callable,
    patterns: list[str],
    emulator: str | None = None,
    exclude_patterns: list[str] | None = None,
) -> dict:
    """
    Generic filesystem <-> DB sync:
      • build_path_func(user, platform_fs_slug[, emulator]) → relative folder
      • get_db_entries(user_id, rom_id) → list of DB models
      • scan_fn(file_name, user, platform_fs_slug[, emulator]) → new model
      • add_fn(model), delete_fn(model.id)
      • patterns: glob patterns like ["MyGame.srm","MyGame.state*"]
    """
    # resolve on‑disk folder
    kwargs = dict(user=user, platform_fs_slug=rom.platform.fs_slug)
    if "emulator" in build_path_func.__code__.co_varnames:
        kwargs["emulator"] = emulator
    rel = build_path_func(**kwargs)
    p = Path(ASSETS_BASE_PATH) / rel

    if not p.exists():
        return {"added": [], "removed": []}

    # collect all matching files, then filter out exclude_patterns
    exclude_patterns = exclude_patterns or []
    fs_names = set()
    for pat in patterns:
        raw = [f.name for f in p.glob(pat) if f.is_file()]
        filtered = [
            name for name in raw
            if not any(fnmatch(name, excl) for excl in exclude_patterns)
        ]
        fs_names |= set(filtered)

    # pull DB entries
    entries = get_db_entries(user_id=user.id, rom_id=rom.id)
    db_names = {e.file_name for e in entries}

    db_map = {e.file_name: e for e in entries}

    to_add = fs_names - db_map.keys()
    to_rm  = db_map.keys() - fs_names

    for fn in to_add:
        m = scan_fn(
            file_name=fn,
            user=user,
            platform_fs_slug=rom.platform.fs_slug,
            emulator=emulator,
        )
        m.rom_id = rom.id
        m.user_id = user.id
        m.emulator = emulator
        add_fn(m)

    for fn in to_rm:
        e = db_map[fn]
        delete_fn(e.id)

    return {"added": list(to_add), "removed": list(to_rm)}