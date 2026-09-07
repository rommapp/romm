"""In-game save sync.

Parallel to the state sync, but for the emulator's own in-game saves (memory
cards / NAND / battery saves). The broker ships them as a single zip archive
via GET/PUT /save-file; RomM stores each pulled archive as one Save asset with
a .zip extension so the whole card set travels as a unit.
"""

import asyncio
from datetime import datetime, timezone

from handler.database import db_rom_handler, db_save_handler, db_user_handler
from handler.filesystem import fs_asset_handler
from handler.scan_handler import scan_save
from handler.streaming import broker, webstation
from handler.streaming.config import ResolvedContainer
from logger.logger import log
from models.rom import Rom
from models.user import User
from utils.filesystem import sanitize_filename


def fetch_save_archive(
    container: ResolvedContainer, broker_session_id: str | None = None
) -> bytes | None:
    """GET /save-file from the broker. Returns the zip bytes or None.

    404 means nothing changed since the game launched (the normal "no new
    saves" case); any other failure is logged and treated the same way.
    """
    if container.is_webstation:
        # Exit already built the delta archive and left it on the container,
        # named after the session that produced it. Matching on that name is
        # what keeps an archive a previous pull failed to collect from being
        # filed under this session's player.
        if not broker_session_id:
            return None
        prefix = f"{broker_session_id}-"
        for export in webstation.exports(container):
            name = str(export.get("name", ""))
            if name.startswith(prefix):
                return webstation.collect_export(container, name)
        return None

    result = broker.get_binary_safe(
        container,
        "/save-file",
        "save-file GET",
        max_bytes=broker.SAVE_FILE_MAX_BYTES,
        timeout=broker.TRANSFER_TIMEOUT,
    )
    return result[1] if result else None


def push_save_archive(container: ResolvedContainer, content: bytes) -> bool:
    """PUT /save-file to the broker. Best-effort, logs but never raises."""
    return broker.put_binary(
        container,
        "/save-file",
        content,
        "save-file PUT",
        content_type="application/zip",
        timeout=broker.TRANSFER_TIMEOUT,
    )


async def store_save_asset(user: User, rom: Rom, emulator: str, content: bytes) -> bool:
    """Store a pulled save archive as a new Save asset.

    Each pull creates a fresh row (timestamped filename), so the user keeps a
    history of save snapshots rather than overwriting. Identical content is
    deduplicated by hash so idle exits do not pile up copies.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H-%M-%S")
    filename = sanitize_filename(f"{rom.fs_name_no_ext} [{emulator} {ts}].saves.zip")

    saves_path = fs_asset_handler.build_saves_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )
    await fs_asset_handler.write_file(file=content, path=saves_path, filename=filename)

    scanned_save = await scan_save(
        file_name=filename,
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )

    # Drop the write if an identical archive is already stored for this ROM.
    if scanned_save.content_hash:
        existing = db_save_handler.get_save_by_content_hash(
            user_id=user.id, rom_id=rom.id, content_hash=scanned_save.content_hash
        )
        if existing is not None:
            try:
                await fs_asset_handler.remove_file(f"{saves_path}/{filename}")
            except FileNotFoundError:
                pass
            return False

    scanned_save.rom_id = rom.id
    scanned_save.user_id = user.id
    scanned_save.emulator = emulator
    db_save_handler.add_save(save=scanned_save)
    return True


async def pull_saves_to_library(
    user_id: int,
    rom_id: int,
    container: ResolvedContainer,
    broker_session_id: str | None = None,
) -> bool:
    """Background task: pull in-game saves from the broker and store them.

    Best-effort by design, a sync failure must never surface to the player,
    the save still exists inside the container.
    """
    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return False
    emulator = container.emulator

    for attempt in range(broker.PULL_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(broker.PULL_RETRY_DELAY)
        content = await asyncio.to_thread(
            fetch_save_archive, container, broker_session_id
        )
        if content is None:
            continue
        try:
            stored = await store_save_asset(user, rom, emulator, content)
        except Exception:
            log.exception("failed to store pulled saves, rom=%s", rom.name)
            return False
        if stored:
            log.info("saves synced to library, rom=%s", rom.name)
        else:
            log.info("pulled saves unchanged, rom=%s", rom.name)
        return True

    log.info("no save changes to pull, rom_id=%d", rom_id)
    return False


async def _newest_save_archive(
    user_id: int, rom_id: int, emulator: str
) -> tuple[str, bytes] | None:
    """The user's most recent stored save archive for this emulator, read off
    disk. Returns (file name, content), or None when there is nothing to send.
    """
    archives = [
        save
        for save in db_save_handler.get_saves(user_id=user_id, rom_ids=[rom_id])
        if (save.emulator or "").lower() == emulator and save.file_name.endswith(".zip")
    ]
    if not archives:
        return None
    # Ties on id, because created_at only has second resolution: two archives
    # written in the same second would otherwise hydrate arbitrarily.
    newest = max(archives, key=lambda s: (s.created_at, s.id))

    try:
        content = await fs_asset_handler.read_file(
            f"{newest.file_path}/{newest.file_name}"
        )
    except FileNotFoundError:
        log.warning("stored save missing on disk, %s", newest.file_name)
        return None
    return newest.file_name, content


async def hydrate_saves_to_broker(
    user_id: int, rom_id: int, container: ResolvedContainer
) -> bool:
    """Push the user's newest stored save archive down to the freshly claimed
    container BEFORE the game launches. Games read saves at boot, so this must
    happen synchronously ahead of the launch (unlike states, read lazily).
    """
    rom = db_rom_handler.get_rom(rom_id)
    if db_user_handler.get_user(user_id) is None or rom is None:
        return False

    newest = await _newest_save_archive(user_id, rom_id, container.emulator)
    if newest is None:
        return False
    file_name, content = newest

    ok = await asyncio.to_thread(push_save_archive, container, content)
    if ok:
        log.info("hydrated saves to container, rom=%s file=%s", rom.name, file_name)
    return ok


async def hydrate_saves_to_webstation(
    user_id: int, rom_id: int, container: ResolvedContainer
) -> str | None:
    """Upload the newest stored save archive and return the container path.

    The webstation broker restores as part of activate rather than through a
    push of its own, so hydration here only gets the bytes into place and
    hands back the path activate names.
    """
    newest = await _newest_save_archive(user_id, rom_id, container.emulator)
    if newest is None:
        return None
    file_name, content = newest

    path = await asyncio.to_thread(
        webstation.upload_archive, container, f"rom-{rom_id}.zip", content
    )
    if path:
        log.info("uploaded saves to container, file=%s path=%s", file_name, path)
    return path
