from fastapi import HTTPException, status
from pathlib import Path
from config import ASSETS_BASE_PATH
from logger.logger import log

def refresh_assets(
    user,
    rom,
    build_path_func,
    get_db_entries,
    scan_fn,
    add_fn,
    delete_fn,
    patterns: list[str],
    emulator: str | None = None,
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

    log.info(f"→ refreshing assets in {p.resolve()}")
    log.info(f"→ using patterns: {patterns}")

    if not p.exists():
        log.error(f"folder missing: {p}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assets folder missing: {p}"
        )

    # collect all matching files
    fs_names = set()
    for pat in patterns:
        matched = [f.name for f in p.glob(pat) if f.is_file()]
        log.info(f"pattern '{pat}' matched files: {matched}")
        fs_names.update(matched)
    log.info(f"all filesystem names: {fs_names}")

    # pull DB entries
    entries = get_db_entries(user_id=user.id, rom_id=rom.id)
    db_names = {e.file_name for e in entries}
    log.info(f"database has entries: {db_names}")

    db_map = {e.file_name: e for e in entries}

    to_add = fs_names - db_map.keys()
    log.info(f"files to ADD: {to_add}")
    to_rm  = db_map.keys() - fs_names
    log.info(f"files to REMOVE: {to_rm}")

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
        log.info(f"added {fn}")

    for fn in to_rm:
        e = db_map[fn]
        delete_fn(e.id)
        log.info(f"removed {fn}")

    return {"added": list(to_add), "removed": list(to_rm)}