"""Whole memory-card sync (per-user card model).

Opt-in per container via `memory_card_sync: true`. When on, the container's
entire card (PCSX2 Slot 1, Dolphin Slot A) is one owned image: hydrated (or
wiped to a fresh blank card) on claim, and evacuated to the library before the
game is stopped. This REPLACES the /save-file in-game-save path for that
container; save-STATE sync is untouched.
"""

import asyncio
import io
import urllib.error
import zipfile
from pathlib import PurePosixPath
from typing import Any, TypedDict

from fastapi import HTTPException

from handler.database import db_memory_card_handler, db_user_handler
from handler.filesystem import fs_asset_handler
from handler.streaming import broker
from handler.streaming.config import ResolvedContainer
from logger.logger import log
from models.assets import MemoryCard
from utils.memory_cards import (
    MEMORY_CARD_MAX_BYTES,
    content_hash_of_bytes,
    store_memory_card_version,
)


def _empty_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    return buf.getvalue()


# PUT to a freshly claimed container to wipe slot 1 to a blank card, so the next
# player never inherits the previous owner's saves (the isolation guarantee for
# pooled hosts). The broker's wipe-then-replace lays down an empty card and
# PCSX2 formats it on first save.
EMPTY_CARD = _empty_zip_bytes()


class MemoryCardUnavailable(Exception):
    """The broker's Slot-1 card could not be read (endpoint missing, wrong card
    type, oversize, or a transport error). Distinct from a broker-confirmed
    EMPTY slot: unavailable means we must NOT wipe, since we never captured it."""


# Its messages carry the broker host and port, so the client gets this fixed
# string and the real cause stays in the server log.
CARD_UNREADABLE_REASON = "The streaming container did not return its memory card"

CARD_IMPORT_FAILED_DETAIL = "Could not import the memory card"


def fetch_card(
    container: ResolvedContainer, timeout: float = broker.CARD_HYDRATE_TIMEOUT
) -> bytes | None:
    """GET /memory-card from the broker. Tri-state:

    - bytes: the Slot-1 card was captured and can be stored.
    - None:  the broker CONFIRMS the slot is empty (404 tagged
      `X-Memory-Card: absent`). Nothing to store, safe to wipe.
    - raise `MemoryCardUnavailable`: the card could not be read (endpoint
      missing / unmarked 404, 409 File card, oversize, empty 200, or a transport
      error). The caller must NOT wipe, since the card was never captured.
    """
    try:
        _, content = broker.get_binary(
            container,
            container.memory_card_route(),
            max_bytes=MEMORY_CARD_MAX_BYTES,
            timeout=timeout,
        )
        return content
    except urllib.error.HTTPError as exc:
        try:
            if exc.code == 404 and exc.headers.get("X-Memory-Card") == "absent":
                # Broker confirms the slot is genuinely empty (first run, or
                # already wiped). Safe to wipe; there is nothing to evacuate.
                return None
            if exc.code == 409:
                raise MemoryCardUnavailable(
                    "broker slot 1 is a File card, not a Folder card"
                ) from exc
            raise MemoryCardUnavailable(
                f"broker memory-card GET failed, HTTP {exc.code}"
            ) from exc
        finally:
            exc.close()
    except Exception as exc:
        raise MemoryCardUnavailable(f"broker memory-card GET failed, {exc}") from exc


def push_card(
    container: ResolvedContainer,
    content: bytes,
    timeout: float = broker.CARD_HYDRATE_TIMEOUT,
) -> bool:
    """PUT /memory-card to the broker (wipe-then-replace). Best-effort, logs
    but never raises. The caller decides whether a failure aborts the claim."""
    return broker.put_binary(
        container,
        container.memory_card_route(),
        content,
        "memory-card PUT",
        content_type="application/zip",
        timeout=timeout,
    )


class MemoryCardSummary(TypedDict):
    file_count: int
    total_bytes: int
    game_codes: list[str]


def summarize_card(content: bytes) -> MemoryCardSummary:
    """Describe a fetched card for the import dialog. GameCube names its saves
    `<makercode>-<gamecode>-<comment>.gci`, so the gamecode is a filename field,
    not something that needs the card format parsed.

    Never raises: a card we cannot parse still has to be offered to the user.
    """
    codes: set[str] = set()
    file_count = 0
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                total += info.file_size
                parts = PurePosixPath(info.filename).name.split("-")
                if len(parts) >= 3 and info.filename.lower().endswith(".gci"):
                    codes.add(parts[1])
    except Exception:
        # Unparseable: nothing describable, so report nothing rather than a
        # file-less card that still claims a size.
        return {"file_count": 0, "total_bytes": 0, "game_codes": []}
    return {
        "file_count": file_count,
        "total_bytes": total,
        "game_codes": sorted(codes),
    }


def resolve_card(
    user_id: int, emulator: str, memory_card_id: int | None
) -> MemoryCard | None:
    """Pick the card to mount for a claim.

    An explicit id must be one the user owns for this emulator. Shared/public
    cards are view-only: they are browsable and downloadable through the memory
    card UI, but never live-mounted onto another user's session, since a mounted
    card is written back as a new version on release and that version belongs to
    the owner. With no id, use the user's most-recently-used
    card for the emulator, or None when the user has no card yet. Resolution
    never creates rows; the claim path creates a blank card only after the
    claim is won.
    """
    if memory_card_id is not None:
        card = db_memory_card_handler.get_card(user_id=user_id, id=memory_card_id)
        if card is None or card.emulator != emulator:
            raise HTTPException(
                status_code=404, detail="Memory card not found for this emulator"
            )
        return card

    cards = db_memory_card_handler.get_cards(user_id=user_id, emulator=emulator)
    if cards:
        return cards[0]  # get_cards orders by updated_at desc
    return None


def create_blank_card(
    user_id: int, emulator: str, platform_id: int | None
) -> MemoryCard:
    """Create a fresh blank card for a user's first play on an emulator. The
    blank carries no version, so hydrate wipes the container to a clean card
    that the emulator formats on first save.
    """
    blank = MemoryCard(
        user_id=user_id,
        emulator=emulator,
        platform_id=platform_id,
        name=f"{emulator} memory card",
        slot=1,
        is_public=False,
    )
    return db_memory_card_handler.add_card(blank)


async def hydrate_card_to_broker(
    user_id: int, card: MemoryCard, container: ResolvedContainer
) -> bool:
    """Push the card's newest version down to a freshly claimed container BEFORE
    launch (games read the card at boot). A blank card, or one whose stored file
    has gone missing, wipes the container to a fresh card so the player never
    inherits a previous owner's saves. Returns False only when the broker push
    itself fails, so the caller can abort a claim it could not isolate.
    """
    latest = db_memory_card_handler.get_latest_version(card.id)
    content = EMPTY_CARD
    if latest is not None:
        try:
            content = await fs_asset_handler.read_file(
                f"{latest.file_path}/{latest.file_name}"
            )
        except FileNotFoundError:
            # The version row exists but the file is gone. Wiping to a blank
            # card keeps isolation intact rather than leaking the last card.
            log.warning(
                "memory card file missing on disk, %s, wiping to blank",
                latest.file_name,
            )
    ok = await asyncio.to_thread(push_card, container, content)
    if ok:
        log.info(
            "hydrated memory card to container, card=%d version=%s",
            card.id,
            latest.file_name if latest is not None else "(blank)",
        )
    return ok


def adoption_already_stored(card_id: int, content: bytes | None) -> bool:
    """Is the container's card already this card's latest version?

    Dedup can refuse a version because a previous claim stored it and then died
    before recording the adoption decision, leaving the prompt to fire again on
    unchanged content. That retry is idempotent: hydrate would push back the
    very bytes sitting on the container, so the adoption stands and only the
    decision row is missing. A match against an older version means hydrate
    would push something else over the card, which is the case that must abort.
    """
    if not content:
        return False
    content_hash = content_hash_of_bytes(content)
    if not content_hash:
        return False
    latest = db_memory_card_handler.get_latest_version(card_id)
    return latest is not None and latest.content_hash == content_hash


async def discard_blank_card(card_id: int) -> None:
    """Drop a card this claim created, with any archive it picked up on the way:
    an abort after adoption is a card that already holds a version."""
    for path in db_memory_card_handler.delete_card(card_id):
        try:
            await fs_asset_handler.remove_file(file_path=path)
        except OSError as exc:
            log.warning("could not remove card archive %s, %s", path, exc)


async def evacuate_card(
    user_id: int, card_id: int, container: ResolvedContainer
) -> bool:
    """Pull the whole Slot-1 card off the broker and store it as a new version.

    Called before the emulator is stopped so a pooled container is captured
    before it can be reclaimed. Returns `safe_to_wipe`: True only when the card
    was captured (or the broker confirmed the slot is empty), False when it
    could not be read. The caller wipes the slot only when this is True, so a
    card that failed to evacuate is never destroyed.
    """
    user = db_user_handler.get_user(user_id)
    card = db_memory_card_handler.get_card_by_id(card_id)
    if user is None or card is None:
        return False
    try:
        # Teardown must not hang a release for the full transfer window, so the
        # fetch gets a tighter bound than hydrate-on-claim.
        content = await asyncio.to_thread(
            fetch_card, container, timeout=broker.CARD_TEARDOWN_TIMEOUT
        )
    except MemoryCardUnavailable as exc:
        log.warning(
            "could not evacuate memory card %d, not safe to wipe, %s",
            card_id,
            exc,
        )
        return False
    if content is None:
        log.info("broker slot empty, nothing to evacuate, card=%d", card_id)
        return True
    try:
        stored = await store_memory_card_version(user, card, content)
    except Exception:
        log.exception("failed to store evacuated memory card %d", card_id)
        return False
    if stored:
        log.info("memory card evacuated to library, card=%d", card_id)
    else:
        log.info("evacuated memory card unchanged, card=%d", card_id)
    return True


async def evacuate_session_card(
    session: dict[str, Any], container: ResolvedContainer
) -> bool:
    """Evacuate a whole-card-sync session's card before its container is freed.

    MUST be awaited while the Redis claim is still held: releasing the claim
    first would let another user claim the container and wipe the card (claim
    hydrates wipe-then-replace) before we capture it. Returns `safe_to_wipe`:
    True only when the card was captured (or confirmed empty). No-op returning
    False for containers without memory_card_sync or sessions that never
    resolved a card, so those are never wiped.
    """
    if not container.memory_card_sync:
        return False
    card_id = session.get("memory_card_id")
    user_id = session.get("user_id")
    if not isinstance(card_id, int) or not isinstance(user_id, int):
        return False
    try:
        return await evacuate_card(user_id, card_id, container)
    except Exception:
        log.exception("memory card evacuation failed, card=%d", card_id)
        return False


async def wipe_session_card(container: ResolvedContainer) -> None:
    """Blank the broker's Slot-1 card after a confirmed evacuation.

    Defense in depth for pooled hosts: hydrate already wipes-then-replaces on
    the next claim, but wiping now guarantees no card is left behind between
    sessions for a bad or crashing hydrate to inherit. MUST run only when
    evacuation reported safe_to_wipe, after the game is stopped (so the
    emulator's exit flush cannot re-lay the card) and BEFORE the Redis claim is
    released (so a concurrent claimant's fresh card is never clobbered).
    Best-effort: a failed wipe is logged, not fatal, since the next claim wipes.
    """
    if not container.memory_card_sync:
        return
    # Teardown path, so a tighter bound than hydrate-on-claim.
    ok = await asyncio.to_thread(
        push_card,
        container,
        EMPTY_CARD,
        timeout=broker.CARD_TEARDOWN_TIMEOUT,
    )
    if ok:
        log.info("wiped broker memory-card slot after evacuation")
    else:
        log.warning("memory-card slot wipe failed, relying on next-claim wipe")
