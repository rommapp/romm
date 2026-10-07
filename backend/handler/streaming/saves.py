"""In-game save sync.

Parallel to the state sync, but for the emulator's own in-game saves (memory
cards / NAND / battery saves). The broker ships them as a single zip archive
via GET/PUT /save-file; RomM stores each pulled archive as one Save asset with
a .zip extension so the whole card set travels as a unit. A RetroArch exit
holding one battery save is the exception, filed as the bare file instead.
"""

import asyncio
import io
import os
import posixpath
import secrets
import time
import zipfile
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from fastapi import HTTPException
from redis.exceptions import WatchError

from handler.database import db_rom_handler, db_save_handler, db_user_handler
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache
from handler.scan_handler import scan_save
from handler.streaming import archive, broker, states, webstation
from handler.streaming.config import ResolvedContainer
from logger.logger import log
from models.assets import EMULATOR_MAX_LENGTH, Save, State
from models.rom import Rom
from models.user import User
from utils.filesystem import check_filename_length, fit_filename, sanitize_filename
from utils.uploads import is_emulator_folder_name

# An exit files its archive in the background, so a claim landing behind it would
# hydrate from the archive before last. The exit leaves a marker a claim waits out.
SAVE_PULL_WAIT_SECONDS = 20.0
_SAVE_PULL_KEY_PREFIX = "romm:streaming:save-pull:"
# Backstop for a backend that dies mid-pull: a marker nobody clears would cost
# every later claim on that ROM the full wait.
SAVE_PULL_TTL_SECONDS = 10 * 60
_SAVE_PULL_POLL_SECONDS = 0.25


def _save_pull_redis_key(user_id: int, rom_id: int) -> str:
    return f"{_SAVE_PULL_KEY_PREFIX}{user_id}:{rom_id}"


class SavePullMark(NamedTuple):
    """One exit's pending pull, whose token lets only that pull clear it."""

    user_id: int
    rom_id: int
    token: str


async def mark_save_pull_pending(user_id: int, rom_id: int) -> SavePullMark:
    """Hold this user's claims on this ROM until the returned mark is cleared, a
    later mark taking over so an earlier pull finishing cannot let a claim past it."""
    token = secrets.token_hex(8)
    await async_cache.set(
        _save_pull_redis_key(user_id, rom_id), token, ex=SAVE_PULL_TTL_SECONDS
    )
    return SavePullMark(user_id, rom_id, token)


async def clear_save_pull_pending(mark: SavePullMark) -> None:
    """Drop the marker, while it is still the one `mark` set."""
    key = _save_pull_redis_key(mark.user_id, mark.rom_id)
    async with async_cache.pipeline() as pipe:
        await pipe.watch(key)
        current = await pipe.get(key)
        if isinstance(current, bytes):
            current = current.decode()
        if current != mark.token:
            await pipe.unwatch()
            return
        pipe.multi()
        await pipe.delete(key)
        try:
            await pipe.execute()
        except WatchError:
            # Only a later mark or the TTL moves the key, and neither is ours.
            pass


async def wait_for_save_pull(
    user_id: int, rom_id: int, budget: float = SAVE_PULL_WAIT_SECONDS
) -> bool:
    """Wait for a pull of this user's saves for this ROM to finish filing.

    Returns:
        Whether nothing is pending any more, False once `budget` runs out, since a
        claim is interactive and must not hang on a wedged pull.
    """
    key = _save_pull_redis_key(user_id, rom_id)
    deadline = time.monotonic() + budget
    while await async_cache.exists(key):
        if time.monotonic() >= deadline:
            log.warning(
                "gave up waiting for the previous session's saves, rom_id=%d", rom_id
            )
            return False
        await asyncio.sleep(_SAVE_PULL_POLL_SECONDS)
    return True


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


async def _store_save_file(
    user: User,
    rom: Rom,
    emulator: str,
    filename: str,
    content: bytes,
    *,
    newest_only: bool = False,
) -> bool:
    """Store one pulled save file as a new Save asset, unless identical content
    is already stored for this ROM, so idle exits do not pile up copies.

    Args:
        newest_only: skip only a copy of the newest save, so a return to an
            older one still records the latest play.
    """
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

    if scanned_save.content_hash:
        if newest_only:
            newest = _newest(
                db_save_handler.get_saves(user_id=user.id, rom_ids=[rom.id])
            )
            existing = (
                newest
                if newest and newest.content_hash == scanned_save.content_hash
                else None
            )
        else:
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


async def store_save_asset(user: User, rom: Rom, emulator: str, content: bytes) -> bool:
    """Store a pulled save archive as a new Save asset.

    Each pull creates a fresh row (timestamped filename), so the user keeps a
    history of save snapshots rather than overwriting.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    filename = sanitize_filename(
        fit_filename(rom.fs_name_no_ext, f" [{emulator} {ts}].saves.zip")
    )
    return await _store_save_file(user, rom, emulator, filename, content)


class _ExitState(NamedTuple):
    name: str
    content: bytes
    screenshot: bytes | None


class RawExit(NamedTuple):
    """A RetroArch exit archive unpacked into the files the library keeps bare."""

    core: str
    save_name: str
    save: bytes
    states: list[_ExitState]


_RAW_EXIT_KINDS = {"save", "state", "state_screenshot"}


def _fileable_state(name: str) -> bool:
    """Whether the state history takes a RetroArch state under this name: a
    slot to resume it from, and room for the capture stamp."""
    try:
        name = sanitize_filename(name)
        check_filename_length(
            states.stamped_state_filename("retroarch", name, datetime.now(timezone.utc))
        )
    except ValueError:
        return False
    return states.slot_from_state_filename("retroarch", name) is not None


def unpack_raw_exit(emulator: str, content: bytes) -> RawExit | None:
    """The one `.srm` and the states of a RetroArch exit, or None to keep the zip."""
    if emulator.lower() != "retroarch":
        return None
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return None
    with zf:
        try:
            manifest = archive.read_manifest(zf)
        except ValueError:
            return None
        session = manifest.get("session")
        core = session.get("core") if isinstance(session, dict) else None
        # The core names the save's folder and fills its emulator column.
        if (
            not isinstance(core, str)
            or len(core) > EMULATOR_MAX_LENGTH
            or not is_emulator_folder_name(core)
        ):
            return None
        labelled = archive.manifest_files(manifest)
        members = [
            info
            for info in zf.infolist()
            if not info.is_dir() and info.filename != archive.MANIFEST_NAME
        ]
        kinds = {
            info.filename: labelled.get(info.filename, {}).get("kind")
            for info in members
        }
        if any(
            not isinstance(kind, str) or kind not in _RAW_EXIT_KINDS
            for kind in kinds.values()
        ):
            return None
        # RetroArch's save import takes a single `.srm`.
        save_members = [info for info in members if kinds[info.filename] == "save"]
        if len(save_members) != 1 or not save_members[0].filename.lower().endswith(
            ".srm"
        ):
            return None
        if sum(info.file_size for info in members) > broker.SAVE_FILE_MAX_BYTES:
            return None

        by_name = {info.filename: info for info in members}
        exit_states = []
        # Oldest first, so the state written last heads the history.
        for info in sorted(members, key=lambda i: i.date_time):
            if kinds[info.filename] != "state":
                continue
            shot = by_name.get(f"{info.filename}.png")
            exit_states.append(
                _ExitState(
                    posixpath.basename(info.filename),
                    archive.read_member(zf, info),
                    archive.read_member(zf, shot) if shot is not None else None,
                )
            )
        # Once the zip is dropped, a state the history can't file is gone.
        if not all(_fileable_state(state.name) for state in exit_states):
            return None
        return RawExit(
            core,
            posixpath.basename(save_members[0].filename),
            archive.read_member(zf, save_members[0]),
            exit_states,
        )


def _importable_raw_exit(
    container: ResolvedContainer, content: bytes
) -> RawExit | None:
    """The exit unpacked, where the save import can take it back, or None to keep it."""
    try:
        raw = unpack_raw_exit(container.emulator, content)
    except Exception:
        # An archive that won't unpack is still a save.
        log.exception("could not unpack the exit archive, keeping it whole")
        return None
    if raw is None:
        return None
    spec = webstation.import_spec(container, container.emulator, container.platform)
    return raw if spec is not None and spec.accepts("save") else None


def _capture_times(copies: list[State | None]) -> list[datetime | None]:
    """When to file each new exit state: under the next one stored, or now (None)."""
    times: list[datetime | None] = []
    ceiling: datetime | None = None
    for copy in reversed(copies):
        if copy is not None:
            ceiling = copy.created_at
            if ceiling.tzinfo is None:
                ceiling = ceiling.replace(tzinfo=timezone.utc)
        elif ceiling is not None:
            ceiling -= timedelta(seconds=1)
        times.append(ceiling if copy is None else None)
    return times[::-1]


async def _store_raw_exit(
    user: User,
    rom: Rom,
    emulator: str,
    raw: RawExit,
    content: bytes,
    disc_file_id: int | None,
) -> bool:
    """File the exit's save under its core, as the web player names one, and its states.

    Returns:
        Whether any of them was new.
    """
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    extension = os.path.splitext(raw.save_name)[1]
    filename = sanitize_filename(
        fit_filename(rom.fs_name_no_ext, f" [{ts}]{extension}")
    )
    stored = await _store_save_file(
        user, rom, raw.core, filename, raw.save, newest_only=True
    )

    lost_state = False
    # A state the session already filed (the exit's own, or one saved from
    # RomM mid-session) is in the history under a stamped name.
    checked: list[tuple[_ExitState, State | None]] = []
    for state in raw.states:
        try:
            copy = await states.stored_copy(user.id, rom.id, emulator, state.content)
        except Exception:
            log.exception("failed to check exit state %s", state.name)
            lost_state = True
            continue
        checked.append((state, copy))
    captured = _capture_times([copy for _state, copy in checked])
    for (state, copy), when in zip(checked, captured, strict=True):
        if copy is not None:
            continue
        try:
            await states.store_state_asset(
                user,
                rom,
                emulator,
                sanitize_filename(state.name),
                state.content,
                screenshot=state.screenshot,
                disc_file_id=disc_file_id,
                core=raw.core,
                captured_at=when,
            )
            stored = True
        except Exception:
            log.exception("failed to store exit state %s", state.name)
            lost_state = True
    # The zip is the state's only other copy, so it stays when one didn't file.
    if lost_state:
        stored = await store_save_asset(user, rom, emulator, content) or stored
    return stored


async def pull_saves_to_library(
    user_id: int,
    rom_id: int,
    container: ResolvedContainer,
    broker_session_id: str | None = None,
    *,
    settled: bool = False,
    disc_file_id: int | None = None,
) -> bool:
    """Background task: pull in-game saves from the broker and store them.

    Best-effort by design, a sync failure must never surface to the player,
    the save still exists inside the container.

    Args:
        settled: the emulator is done writing, so one attempt is final where the
            retries would wait out one still writing.
        disc_file_id: the disc the session swapped to, for the states it files.
    """
    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return False
    emulator = container.emulator

    for attempt in range(1 if settled else broker.PULL_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(broker.PULL_RETRY_DELAY)
        content = await asyncio.to_thread(
            fetch_save_archive, container, broker_session_id
        )
        if content is None:
            continue
        try:
            raw = await asyncio.to_thread(_importable_raw_exit, container, content)
            stored = (
                await _store_raw_exit(user, rom, emulator, raw, content, disc_file_id)
                if raw is not None
                else await store_save_asset(user, rom, emulator, content)
            )
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


def _written_by(save: Save, emulator: str) -> bool:
    """An archive another emulator wrote lays its members out somewhere this
    one never reads."""
    return (save.emulator or "").lower() == emulator


def _is_archive(save: Save) -> bool:
    """A bare save file carries no layout the broker could restore it from."""
    return save.file_name.lower().endswith(".zip")


def _is_restorable(save: Save, emulator: str) -> bool:
    """Whether the broker can put this stored save back on the container."""
    return _written_by(save, emulator) and _is_archive(save)


def _newest(saves: Iterable[Save]) -> Save | None:
    # updated_at, as the web player writes into its existing row; id breaks
    # same-second ties. A row whose file vanished can't boot.
    return max(
        (s for s in saves if not s.missing_from_fs),
        key=lambda s: (s.updated_at, s.id),
        default=None,
    )


def newest_restorable(user_id: int, rom_id: int, emulator: str) -> Save | None:
    """The user's most recent restorable archive for this emulator."""
    return _newest(
        [
            save
            for save in db_save_handler.get_saves(user_id=user_id, rom_ids=[rom_id])
            if _is_restorable(save, emulator)
        ]
    )


def default_save(
    user_id: int, rom_id: int, container: ResolvedContainer
) -> tuple[Save | None, bool]:
    """The save a launch with no pick restores, and whether it is foreign.

    Raises:
        HTTPException: 503 when the broker can't say whether a newer `.srm` imports.
    """
    stored = db_save_handler.get_saves(user_id=user_id, rom_ids=[rom_id])
    native = _newest([s for s in stored if _is_restorable(s, container.emulator)])
    if container.emulator.lower() != "retroarch":
        return native, False
    raw = _newest([s for s in stored if s.file_name.lower().endswith(".srm")])
    if raw is None or _newest([s for s in (raw, native) if s]) is not raw:
        return native, False
    spec = webstation.require_import_spec(
        container, container.emulator, container.platform
    )
    if spec is None or not spec.accepts("save"):
        return native, False
    return raw, True


def resolve_save_archive(
    user_id: int, rom: Rom, container: ResolvedContainer, save_id: int
) -> tuple[Save, bool]:
    """Validate a launch-screen save pick and return (save, is_foreign).

    Raises 404 for a save that is not the claiming user's own on this ROM,
    400 for one neither restorable here nor accepted as an import, and 503
    when the broker couldn't be asked whether it imports one.
    """
    save = db_save_handler.get_save(user_id=user_id, id=save_id)
    # Same 404 for another user's save and another ROM's, so neither leaks.
    if save is None or save.rom_id != rom.id:
        raise HTTPException(status_code=404, detail="Save not found")

    if not container.supports_save_picker:
        raise HTTPException(
            status_code=400,
            detail="This emulator always restores the newest save",
        )
    if _is_restorable(save, container.emulator):
        return save, False

    spec = webstation.require_import_spec(
        container, container.emulator, container.platform
    )
    if spec is not None and spec.accepts("save"):
        return save, True

    if not _is_archive(save):
        raise HTTPException(
            status_code=400,
            detail="Save is not a restorable archive",
        )
    raise HTTPException(
        status_code=400,
        detail="Save was made by a different emulator",
    )


async def read_restorable_archive(save: Save) -> tuple[str, bytes] | None:
    """The archive's (file name, content), or None when it is gone off disk."""
    try:
        content = await fs_asset_handler.read_file(f"{save.file_path}/{save.file_name}")
    except FileNotFoundError:
        log.warning("stored save missing on disk, %s", save.file_name)
        return None
    return save.file_name, content


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

    newest = newest_restorable(user_id, rom_id, container.emulator)
    if newest is None:
        return False
    stored = await read_restorable_archive(newest)
    if stored is None:
        return False
    file_name, content = stored

    ok = await asyncio.to_thread(push_save_archive, container, content)
    if ok:
        log.info("hydrated saves to container, rom=%s file=%s", rom.name, file_name)
    return ok


async def hydrate_saves_to_webstation(
    user_id: int, rom_id: int, container: ResolvedContainer, save: Save | None = None
) -> str | None:
    """Upload the stored save archive to restore and return the container path.

    The webstation broker restores as part of activate, so hydration only gets
    the bytes into place. `save` is the player's pick, newest when absent.
    """
    picked = save or newest_restorable(user_id, rom_id, container.emulator)
    if picked is None:
        return None
    stored = await read_restorable_archive(picked)
    if stored is None:
        return None
    file_name, content = stored

    path = await asyncio.to_thread(
        webstation.upload_archive, container, f"rom-{rom_id}.zip", content
    )
    if path:
        log.info("uploaded saves to container, file=%s path=%s", file_name, path)
    return path
