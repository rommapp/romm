"""Save-state sync.

Emulator save states are centralized through RomM's states asset store so
they survive container rebuilds and roam across containers. The backend is
the only file mover: after a save it pulls the state file from the broker
and stores it under the session user's assets; on claim it pushes the user's
stored states back down so the container slots always reflect the central
copy (last write wins, central copy is the source of truth).

Broker file API (secret-protected, stdlib on the broker side):
  GET /state-file?slot=N   - newest state file for slot N. Blocks while a
                             save is in flight, so no clock coupling between
                             hosts. Returns raw bytes + X-State-Filename.
  PUT /state-file?filename=NAME - write NAME into the emulator's state dir.
"""

import asyncio
import base64
import io
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import HTTPException

from config import STREAMING_STATE_HISTORY_LIMIT
from handler.asset_store import store_screenshot, store_state_file
from handler.database import (
    db_rom_handler,
    db_screenshot_handler,
    db_state_handler,
    db_user_handler,
)
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache
from handler.streaming import broker, commands
from handler.streaming.config import ResolvedContainer
from handler.streaming.session_store import set_session_disc
from logger.logger import log
from models.assets import State
from models.rom import Rom
from models.user import User
from utils.filesystem import sanitize_filename

# Slot number encoded in each emulator's state filename, e.g. PCSX2 writes
# "SERIAL (CRC).03.p2s" for slot 3 and Dolphin writes "GAMEID.s03". Resuming
# from a picked state needs the slot to tell the broker what to load, and the
# match is also where the capture stamp is inserted, so an emulator missing
# from here gets no history either.
_SLOT_PATTERNS = {
    "pcsx2": re.compile(r"\.(\d{1,2})\.p2s$"),
    "dolphin": re.compile(r"\.s(\d{2})$"),
    "xemu": re.compile(r"\.x(\d{2})$"),
    # RetroArch leaves the number off its default slot: "GAME.state" is slot 0
    # and "GAME.state3" is slot 3.
    "retroarch": re.compile(r"\.state(\d{0,2})$"),
}


# Lowest slot each emulator's broker will actually address. Everything but
# RetroArch counts from 1, so a "0" in one of their names is a filename that
# happens to look like a state, not a slot they could load.
_MIN_SLOT = {"retroarch": 0}


def slot_from_state_filename(emulator: str, filename: str) -> int | None:
    pattern = _SLOT_PATTERNS.get(emulator)
    if pattern is None:
        return None
    match = pattern.search(filename)
    if match is None:
        return None
    slot = int(match.group(1) or 0)
    return slot if slot >= _MIN_SLOT.get(emulator, 1) else None


# Every capture is kept, so the library needs one file per save, not one per
# slot. The stamp goes immediately before the slot token so the patterns above
# still match at the end of the name: states written before this keep
# resolving, and the container-side name is recovered by dropping the stamp.
_STAMP_FORMAT = "%Y%m%d-%H%M%S%f"
_STAMP_PATTERN = re.compile(r"\.\d{8}-\d{12}(?=\.)")


def stamped_state_filename(emulator: str, filename: str, when: datetime) -> str:
    """Return ``filename`` with a capture stamp inserted before its slot token.

    An emulator with no known slot convention keeps the original name, since
    there is nowhere unambiguous to put the stamp. That emulator gets no
    history: each capture lands on the same name and updates its row in place,
    the pre-history behavior. No streaming emulator is in that position now.
    """
    pattern = _SLOT_PATTERNS.get(emulator)
    if pattern is None:
        return filename
    match = pattern.search(filename)
    if match is None:
        return filename
    stamp = when.strftime(_STAMP_FORMAT)
    return f"{filename[: match.start()]}.{stamp}{filename[match.start() :]}"


def container_state_filename(filename: str) -> str:
    """Strip any capture stamp, giving the name the emulator expects on disk."""
    return _STAMP_PATTERN.sub("", filename, count=1)


def resolve_resume_state(
    user_id: int, rom: Rom, container: ResolvedContainer, state_id: int
) -> tuple[State, int]:
    """Validate a resume-from-state pick and return (state, slot).

    Visibility follows the same rule as the state list the picker was built
    from: the claiming user's own states plus other users' public ones.
    Raises 404 for anything invisible, 400 when the state cannot drive a
    resume on this container.
    """
    state = next(
        (
            s
            for s in db_state_handler.get_rom_shared_states(
                rom_id=rom.id, user_id=user_id
            )
            if s.id == state_id
        ),
        None,
    )
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")

    emulator = container.emulator
    if (state.emulator or "").lower() != emulator:
        raise HTTPException(
            status_code=400,
            detail="State was made by a different emulator",
        )

    slot = slot_from_state_filename(emulator, state.file_name)
    if slot is None:
        raise HTTPException(
            status_code=400,
            detail="State filename carries no recognizable slot number",
        )
    return state, slot


def fetch_state_file(
    container: ResolvedContainer, slot: int
) -> tuple[str, bytes] | None:
    """GET /state-file from the broker. Returns (filename, content) or None.

    The broker blocks while a save is in flight, so a generous timeout stands
    in for save-completion polling. 404 means no state exists for the slot.
    """
    limits = container.state_transfer
    result = broker.get_binary_safe(
        container,
        container.protocol.transfer_route(f"/state-file?slot={slot}"),
        "state-file GET",
        max_bytes=limits["max_bytes"],
        timeout=limits["timeout"],
    )
    if result is None:
        return None
    headers, content = result
    filename = headers.get("X-State-Filename", "")
    if not filename:
        log.warning("broker state-file response missing a filename")
        return None
    return filename, content


def push_state_file(
    container: ResolvedContainer, filename: str, content: bytes
) -> bool:
    """PUT /state-file to the broker. Best-effort, logs but never raises."""
    return broker.put_binary(
        container,
        container.protocol.transfer_route(
            f"/state-file?filename={quote(filename, safe='')}"
        ),
        content,
        "state-file PUT",
        content_type="application/octet-stream",
        timeout=container.state_transfer["timeout"],
    )


# PCSX2 embeds a PNG of the moment of save inside every .p2s savestate zip
# under this entry name (pcsx2/SaveState.cpp: EntryFilename_Screenshot).
# Extracting it gives each pulled state a thumbnail with no broker round-trip,
# mirroring how in-browser EmulatorJS states carry a screenshot.
_SCREENSHOT_ZIP_ENTRY = "Screenshot.png"
SCREENSHOT_MAX_BYTES = 16 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def extract_state_screenshot(emulator: str, state_content: bytes) -> bytes | None:
    """Pull the embedded frame PNG out of a savestate archive, or None when the
    format carries no embedded screenshot. Only PCSX2 (.p2s zip) embeds one;
    the others write the frame as its own file, served by /state-screenshot."""
    if emulator != "pcsx2":
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(state_content)) as zf:
            with zf.open(_SCREENSHOT_ZIP_ENTRY) as entry:
                data = entry.read(SCREENSHOT_MAX_BYTES + 1)
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        # No screenshot entry, or the state is not a readable zip. Not fatal:
        # the state still syncs, it just has no thumbnail.
        log.warning("could not extract state screenshot, %s", exc)
        return None
    if not data or len(data) > SCREENSHOT_MAX_BYTES:
        return None
    return data


_FRAME_KEY_PREFIX = "romm:streaming:frame:"
# Long enough to cover the broker's state write plus the pull retries, short
# enough that a frame never outlives the save it was captured for.
_FRAME_TTL_SECONDS = 120


def _frame_redis_key(user_id: int, rom_id: int) -> str:
    return f"{_FRAME_KEY_PREFIX}{user_id}:{rom_id}"


async def stash_state_frame(user_id: int, rom_id: int, image: bytes) -> None:
    """Hold a browser-captured frame until the state it belongs to is pulled."""
    await async_cache.set(
        _frame_redis_key(user_id, rom_id),
        base64.b64encode(image),
        ex=_FRAME_TTL_SECONDS,
    )


async def take_state_frame(user_id: int, rom_id: int) -> bytes | None:
    key = _frame_redis_key(user_id, rom_id)
    raw = await async_cache.get(key)
    await async_cache.delete(key)
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except (ValueError, TypeError):
        return None


def fetch_state_screenshot(container: ResolvedContainer, slot: int) -> bytes | None:
    """GET /state-screenshot from the broker, for emulators whose state files
    carry no frame of their own. A 404 is the normal "this broker does not
    capture frames" answer, so it is not logged."""
    result = broker.get_binary_safe(
        container,
        container.protocol.transfer_route(f"/state-screenshot?slot={slot}"),
        "state-screenshot GET",
        max_bytes=SCREENSHOT_MAX_BYTES,
        timeout=broker.TRANSFER_TIMEOUT,
    )
    return result[1] if result else None


async def store_state_screenshot(
    user: User, rom: Rom, state_filename: str, image: bytes
) -> None:
    """Bind a thumbnail to a state so the resume picker shows the right frame.

    `State.screenshot` matches by filename stem, so the image reuses the state's
    stem with a .png extension. is_gallery stays False (the default) so it never
    shows in the user's screenshot gallery.
    """
    # Both sources are unverified bytes: a zip entry that only claims to be a
    # PNG, or whatever the broker returned. Guard here so one check covers both.
    if not image.startswith(PNG_MAGIC):
        log.warning("state screenshot for %s is not a PNG, skipping", state_filename)
        return

    await store_screenshot(
        user,
        rom,
        image,
        sanitize_filename(f"{os.path.splitext(state_filename)[0]}.png"),
    )


def user_states_for_emulator(user_id: int, rom_id: int, emulator: str) -> list[State]:
    """The user's states for this ROM and emulator, newest first."""
    states = [
        s
        for s in db_state_handler.get_states(user_id=user_id, rom_ids=[rom_id])
        if (s.emulator or "").lower() == emulator
    ]
    # Ties on id, because updated_at only has second resolution: two captures
    # in the same second would otherwise order arbitrarily, and only the first
    # of them is ever hydrated.
    states.sort(key=lambda s: (s.updated_at, s.id), reverse=True)
    return states


async def _is_duplicate_of_latest(latest: State | None, content: bytes) -> bool:
    """Whether ``content`` matches the most recent stored state byte for byte.

    Saving twice without playing in between is common (the exit autosave right
    after a manual save), and those captures are identical. Only the newest is
    compared: an older match is a genuine revisit of the same point.
    """
    if latest is None or latest.file_size_bytes != len(content):
        return False
    try:
        existing = await fs_asset_handler.read_file(
            f"{latest.file_path}/{latest.file_name}"
        )
    except FileNotFoundError:
        return False
    return existing == content


async def _remove_pruned_file(path: str) -> None:
    """Drop a pruned asset's file. A file that will not go leaves the prune
    running: the rows are already gone, and stopping here would leave the rest
    of the history over the limit as well."""
    try:
        await fs_asset_handler.remove_file(file_path=path)
    except FileNotFoundError:
        log.warning("pruned file already gone, %s", path)
    except OSError as exc:
        log.error("could not remove pruned file %s, leaving it orphaned: %s", path, exc)


async def prune_state_history(
    user: User, rom: Rom, emulator: str, history: list[State] | None = None
) -> int:
    """Delete the oldest states past the retention limit. Returns how many went.

    A file already gone from disk still loses its row, since a stale entry that
    no longer opens is worse than a missing file. `history` is the newest-first
    list a caller already holds, saving a second fetch and sort of the same rows.
    """
    limit = STREAMING_STATE_HISTORY_LIMIT
    if limit <= 0:
        return 0
    states = (
        history
        if history is not None
        else user_states_for_emulator(user.id, rom.id, emulator)
    )
    stale = states[limit:]
    for state in stale:
        screenshot = state.screenshot
        db_state_handler.delete_state(state.id)
        await _remove_pruned_file(f"{state.file_path}/{state.file_name}")
        if screenshot is not None:
            db_screenshot_handler.delete_screenshot(screenshot.id)
            await _remove_pruned_file(f"{screenshot.file_path}/{screenshot.file_name}")
    if stale:
        log.info(
            "pruned %d state(s) past the %d limit, rom=%s",
            len(stale),
            limit,
            rom.name,
        )
    return len(stale)


async def store_state_asset(
    user: User,
    rom: Rom,
    emulator: str,
    filename: str,
    content: bytes,
    screenshot: bytes | None = None,
    disc_file_id: int | None = None,
) -> None:
    """Store a pulled state file as a new entry in the ROM's state history.

    Each capture is kept rather than overwriting the slot it came from, so the
    player can resume from any earlier point. An unchanged capture is dropped
    and the oldest entries are pruned once the retention limit is reached.
    """
    history = user_states_for_emulator(user.id, rom.id, emulator)
    if await _is_duplicate_of_latest(history[0] if history else None, content):
        log.info("state identical to the last capture, skipping, rom=%s", rom.name)
        return

    stamped = stamped_state_filename(emulator, filename, datetime.now(timezone.utc))
    existing_names = {state.file_name for state in history}
    stored = await store_state_file(
        user, rom, emulator, content, stamped, fields={"disc_file_id": disc_file_id}
    )
    if stamped not in existing_names:
        # The capture is the newest, so it heads the list the prune below reads.
        history.insert(0, stored)

    # Bind a thumbnail to the state so the resume picker shows the right frame.
    # Best-effort: a missing or unreadable screenshot must not fail the sync.
    if screenshot is not None:
        try:
            await store_state_screenshot(user, rom, stamped, screenshot)
        except Exception:
            log.exception("failed to store state screenshot for %s", stamped)

    await prune_state_history(user, rom, emulator, history=history)


async def pull_state_to_library(
    user_id: int,
    rom_id: int,
    container: ResolvedContainer,
    slot: int,
    disc_file_id: int | None = None,
) -> bool:
    """Background task: pull a freshly saved state from the broker and store it.

    Best-effort by design, a sync failure must never surface to the player,
    the state still exists inside the container.
    """
    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return False
    emulator = container.emulator

    for attempt in range(broker.PULL_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(broker.PULL_RETRY_DELAY)
        result = await asyncio.to_thread(fetch_state_file, container, slot)
        if result is None:
            continue
        filename, content = result
        try:
            filename = sanitize_filename(filename)
        except ValueError:
            log.warning("broker returned invalid state filename")
            return False
        # The browser frame is preferred: it is what the player actually saw,
        # and capturing it never asks the emulator to read back its own
        # framebuffer, which is what deadlocks GPU-rendered cores. PCSX2 embeds
        # a frame in the state file; the rest write one beside it.
        screenshot = await take_state_frame(user_id, rom_id)
        if screenshot is None:
            screenshot = extract_state_screenshot(emulator, content)
        if screenshot is None:
            screenshot = await asyncio.to_thread(
                fetch_state_screenshot, container, slot
            )
        try:
            await store_state_asset(
                user, rom, emulator, filename, content, screenshot, disc_file_id
            )
        except Exception:
            log.exception("failed to store pulled state %s", filename)
            return False
        log.info(
            "state synced to library, rom=%s slot=%d file=%s",
            rom.name,
            slot,
            filename,
        )
        return True

    log.warning("no state file to pull after save, rom_id=%d slot=%d", rom_id, slot)
    return False


async def push_resume_state(container: ResolvedContainer, resume_state: State) -> bool:
    """Send the state a player picked to resume from down to the container.

    Best-effort: a failure means the session just starts fresh, which the claim
    response reports through `resume`.
    """
    try:
        content = await fs_asset_handler.read_file(
            f"{resume_state.file_path}/{resume_state.file_name}"
        )
    except Exception:
        log.exception("could not read resume state %s", resume_state.file_name)
        return False
    pushed = await asyncio.to_thread(
        push_state_file,
        container,
        container_state_filename(resume_state.file_name),
        content,
    )
    if not pushed:
        log.warning("resume state not pushed, launching fresh")
    return pushed


async def hydrate_states_to_broker(
    user_id: int,
    rom_id: int,
    container: ResolvedContainer,
    resume_pushed: bool = False,
) -> int:
    """Background task: push the newest stored state for this ROM down to the
    freshly claimed container. Emulators read state files lazily, so pushing
    right after launch is safe.

    Only the newest is sent: every history entry collapses to the same
    container-side name, and that name is what the in-emulator quick-load lands
    on. Older captures are reached through the resume picker instead.

    For the same reason, a resume pick already sent at claim time means there is
    nothing to add here: any push would overwrite it before the broker's
    deferred load fires.
    """
    if resume_pushed:
        return 0

    user = db_user_handler.get_user(user_id)
    rom = db_rom_handler.get_rom(rom_id)
    if user is None or rom is None:
        return 0
    emulator = container.emulator

    states = user_states_for_emulator(user_id, rom_id, emulator)
    if not states:
        return 0

    newest = states[0]
    try:
        content = await fs_asset_handler.read_file(
            f"{newest.file_path}/{newest.file_name}"
        )
    except FileNotFoundError:
        log.warning("stored state missing on disk, %s", newest.file_name)
        return 0
    ok = await asyncio.to_thread(
        push_state_file,
        container,
        container_state_filename(newest.file_name),
        content,
    )
    if ok:
        log.info("hydrated newest state to container, rom=%s", rom.name)
    return 1 if ok else 0


async def restore_session_disc(
    rom_id: int,
    container: ResolvedContainer,
    session_key: str,
    file_id: int,
    broker_session_id: str | None = None,
) -> bool:
    """Background task: put back the disc a resumed state was captured on.

    The launch always mounts the ROM folder so the emulator loads the playlist
    and starts on the first disc; anything else would boot a bare image the
    tray commands cannot step through. So the disc is restored afterwards, and
    the broker holds the swap until the core reports a running game.

    Best-effort: a failure leaves the session on disc one, which the player can
    fix with the swap control.
    """
    rom_file = db_rom_handler.get_rom_file_by_id(file_id)
    if rom_file is None or rom_file.rom_id != rom_id:
        log.warning(
            "resume: could not restore disc, file %s is not in the library", file_id
        )
        return False
    library_base = container.library_path
    disc_path = f"{library_base}/{rom_file.full_path}"
    if not await asyncio.to_thread(commands.swap_disc, container, disc_path):
        log.warning("resume: could not restore disc %s", rom_file.file_name)
        return False
    await set_session_disc(session_key, file_id, broker_session_id)
    log.info("resume: restored disc %s", rom_file.file_name)
    return True
