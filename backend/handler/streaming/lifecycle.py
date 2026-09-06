"""What every teardown path does, and in what order.

Stopping the emulator, evacuating and wiping the card, crediting the playtime,
filing the exit state and saves, and only then giving the container back. The
order is load-bearing and lives here once rather than in each route that ends
a session.
"""

import asyncio
import secrets
from collections.abc import Coroutine
from datetime import datetime, timezone
from typing import Any

from handler.activity_handler import activity_handler
from handler.database import db_user_handler
from handler.play_session_handler import ingest_play_sessions
from handler.streaming import background, commands, memory_cards, saves, states
from handler.streaming.config import ResolvedContainer
from handler.streaming.session_store import (
    DRAIN_MARKER_TTL,
    StreamingSessionContended,
    broker_session_id,
    claim_drain_marker,
    drain_marker,
    drop_drain_marker,
    hold_drain_marker,
    hold_session_claim,
    record_termination,
    release_own_session,
    replace_session_if,
    same_claim,
    session_disc_id,
    session_is_stale,
)
from logger.logger import log


async def abort_claim(
    session_key: str,
    claim: dict[str, Any],
    blank_card_id: int | None = None,
) -> None:
    """Undo a claim that will not become a session.

    Every exit from `claim_session` that is not a started session goes through
    here: leaving the key behind wedges the container until the TTL lapses, and
    leaving an auto-created blank card behind orphans a row nobody asked for.

    Guarded like every other release: a card probe or an activate blocks for
    minutes, and an unguarded delete would free a container an admin release
    and a fresh claim had already handed to somebody else.
    """
    if not await release_own_session(session_key, claim):
        log.warning("aborted claim on %s was no longer ours", session_key)
    if blank_card_id is not None:
        await memory_cards.discard_blank_card(blank_card_id)


def _hold_reservation(
    session_key: str, token: str | None, claim: dict[str, Any]
) -> asyncio.Future:
    """Keep a container reserved while a teardown runs.

    The drain marker holds it where one landed; where it did not, nothing took
    the container over and the claim itself still reserves it. Either way the
    stamp is kept current, since the player who owned it has left and an
    unrefreshed reservation reads as abandoned to the next claimant.
    """
    return asyncio.ensure_future(
        hold_drain_marker(session_key, token)
        if token is not None
        else hold_session_claim(session_key, claim)
    )


async def _drop_reservation(
    session_key: str, token: str | None, claim: dict[str, Any]
) -> None:
    """Free whatever `_hold_reservation` was holding. `token` keeps the release
    aimed at this drain, so an overrun that outlived its own marker cannot free
    whoever took the container afterwards."""
    if token is not None:
        await drop_drain_marker(session_key, token)
    elif not await release_own_session(session_key, claim):
        log.error("session %s survived its own exit", session_key)


async def release_after_state_pull(
    session_key: str,
    pull: Coroutine[Any, Any, Any],
    token: str | None,
    claim: dict[str, Any],
) -> None:
    """Run the exit state pull, then free the container it was holding.

    The reservation goes even when the pull raised: the state is recoverable
    from the container on the next claim, a container nothing releases is not.
    """
    keepalive = _hold_reservation(session_key, token, claim)
    try:
        await pull
    finally:
        keepalive.cancel()
        await _drop_reservation(session_key, token, claim)


async def quiesce_container(
    container: ResolvedContainer, session: dict[str, Any], *, save: bool = True
) -> int | None:
    """Stop the emulator, then evacuate and wipe its memory card.

    Every teardown path opens this way, and the order is load-bearing: stopping
    first is what makes the card quiescent, and the wipe runs only where the
    evacuation captured the card. Returns the slot the stop wrote an exit state
    to, if any.
    """
    state_slot = await asyncio.to_thread(commands.stop, container, save)
    if await memory_cards.evacuate_session_card(session, container):
        await memory_cards.wipe_session_card(container)
    return state_slot


def collect_exit_saves(container: ResolvedContainer, session: dict[str, Any]) -> None:
    """Start pulling the in-game save archive a stopped session left behind.

    Fire and forget: the broker keeps the archive after the emulator dies, so
    no teardown has to wait on it. Whole-card sync containers evacuate the card
    instead and have no archive, and a session that ran no ROM (the admin
    desktop) has nowhere to file one, so neither schedules anything.

    One home for the rule: every teardown path files a session's saves the same
    way, and under the session's owner rather than whoever ended it.
    """
    rom_id = session.get("rom_id")
    user_id = session.get("user_id")
    if (
        container.memory_card_sync
        or not isinstance(rom_id, int)
        or not isinstance(user_id, int)
    ):
        return
    background.spawn_sync_task(
        saves.pull_saves_to_library(
            user_id, rom_id, container, broker_session_id(session)
        )
    )


async def collect_exit_state(
    container: ResolvedContainer, session: dict[str, Any], state_slot: int | None
) -> None:
    """File the state the stop wrote, while the claim still guards the container.

    The broker keeps an exited session's state only until the next activate, and
    dropping the claim is what lets that activate happen.
    """
    rom_id = session.get("rom_id")
    user_id = session.get("user_id")
    if (
        state_slot is None
        or not isinstance(rom_id, int)
        or not isinstance(user_id, int)
    ):
        return
    await states.pull_state_to_library(
        user_id,
        rom_id,
        container,
        state_slot,
        disc_file_id=session_disc_id(session),
    )


# Streaming sessions shorter than this are treated as accidental (a claim that
# was released almost immediately) and not recorded as playtime.
_MIN_PLAY_SESSION_MS = 5_000

# A streaming session is a play session like any other, so it goes on the
# activity board next to the devices. The container key stands in for a device
# id: a user holds at most one session per container, which is what
# clear_active needs to find the entry again.
_DEVICE_TYPE = "streaming"


async def publish_session_activity(session_key: str, session: dict[str, Any]) -> None:
    """Put a live streaming session on the activity board.

    Best-effort: the board is a view, never a reason to fail a launch.
    """
    user_id = session.get("user_id")
    rom_id = session.get("rom_id")
    if not isinstance(user_id, int) or not isinstance(rom_id, int):
        return
    try:
        entry = await activity_handler.build_entry(
            user_id=user_id,
            device_id=session_key,
            rom_id=rom_id,
            preserve_started_at=True,
            device_type=_DEVICE_TYPE,
        )
        if entry is not None:
            await activity_handler.publish_active(entry)
    except Exception:
        log.exception("failed to publish streaming session activity")


async def refresh_session_activity(session_key: str, session: dict[str, Any]) -> None:
    """Keep the activity entry alive on the player's heartbeat.

    Re-stores what is already there instead of rebuilding it: nothing on the
    entry changes for the length of a session, and a beat every 30s per session
    would otherwise cost two queries and a broadcast each time. An entry that
    has gone (expired while the backend was down) is rebuilt.
    """
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return
    try:
        existing = await activity_handler.get_active(user_id, session_key)
    except Exception:
        log.exception("failed to read streaming session activity")
        return
    if existing is None:
        await publish_session_activity(session_key, session)
        return
    try:
        await activity_handler.set_active(existing)
    except Exception:
        log.exception("failed to refresh streaming session activity")


async def clear_session_activity(session_key: str, session: dict[str, Any]) -> None:
    """Take a finished streaming session off the activity board.

    Every teardown path calls this: the board is socket-driven, so an entry left
    behind sits on an open board until its TTL runs out.
    """
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return
    try:
        await activity_handler.publish_clear(user_id, session_key)
    except Exception:
        log.exception("failed to clear streaming session activity")


async def record_play_session(session: dict[str, Any]) -> None:
    """Record a finished streaming session as RomM playtime.

    Reuses the same ingest path as device sync (dedup on user+rom+start_time,
    updates the ROM's last_played). The session's stored claimed_at is the
    start and now is the end. Best-effort: any failure is logged, never fatal,
    so playtime accounting cannot block or fail a teardown.
    """
    user_id = session.get("user_id")
    rom_id = session.get("rom_id")
    claimed_at = session.get("claimed_at")
    if (
        not isinstance(user_id, int)
        or not isinstance(rom_id, int)
        or not isinstance(claimed_at, str)
    ):
        return

    try:
        start = datetime.fromisoformat(claimed_at)
    except ValueError:
        return
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    end = datetime.now(timezone.utc)
    duration_ms = int((end - start).total_seconds() * 1000)
    if duration_ms < _MIN_PLAY_SESSION_MS:
        return

    try:
        user = db_user_handler.get_user(user_id)
        ingest_play_sessions(
            user_id=user_id,
            username=user.username if user else str(user_id),
            entries=[
                {
                    "rom_id": rom_id,
                    "save_slot": None,
                    "start_time": start,
                    "end_time": end,
                    "duration_ms": duration_ms,
                }
            ],
        )
    except Exception:
        log.exception("failed to record play session")


async def teardown_released_session(
    container: ResolvedContainer,
    session: dict[str, Any],
    session_key: str,
    platform: str,
    *,
    acting_user_id: int,
    acting_username: str,
    reason: str | None,
    save: bool = True,
) -> None:
    """Stop the emulator, evacuate the card, then release the claim.

    Ordering is load-bearing (see the inline notes). Runs detached from the
    release request; every step is best-effort so a teardown hiccup cannot wedge
    the claim, which the stale-session takeover reclaims if this never finishes.
    """
    # Take the claim into a drain marker first. Everything below runs detached
    # and blocks on the broker for as long as the emulator takes to die, so a
    # takeover landing in that window would otherwise have its emulator stopped
    # and its claim deleted along with the session it replaced.
    try:
        token = await claim_drain_marker(session_key, session)
    except StreamingSessionContended:
        # The claim is still ours, it just could not be marked: it is what
        # reserves the container below, and the delete at the end is guarded on
        # it anyway.
        log.error("could not drain released session %s", session_key)
        token = None
    else:
        if token is None:
            log.warning("skipping teardown, session %s was taken over", session_key)
            return

    keepalive = _hold_reservation(session_key, token, session)
    try:
        # The marker, or the claim it could not replace, holds the container
        # throughout, so no concurrent claim can interleave.
        state_slot = await quiesce_container(container, session, save=save)

        # Leave a note when this is a force-release rather than a player closing
        # their own game. A different user is the obvious case; a reason covers
        # the rest, since only the admin panel sends one and an admin can be
        # logged in as the same account that is playing in another tab.
        if session.get("user_id") != acting_user_id or reason is not None:
            await record_termination(
                session, session_key, ended_by=acting_username, reason=reason
            )
            log.info(
                "session force-released, platform=%s by=%s user_id=%s reason=%s",
                platform,
                acting_username,
                session.get("user_id"),
                reason or "-",
            )

        await record_play_session(session)
        await clear_session_activity(session_key, session)

        # Awaited, not spawned: the claim is released below.
        await collect_exit_state(container, session, state_slot)
        collect_exit_saves(container, session)

        log.info("session released, platform=%s", platform)
    except Exception:
        log.exception("session teardown failed, platform=%s", platform)
    finally:
        # The claim goes even when a step above raised. The API already told the
        # caller the session was released, so a key left behind blocks every
        # later claim until stale takeover or the TTL expires. A card left
        # un-evacuated is recoverable, since the next claim prompts to adopt
        # whatever is still on the container; a phantom claim is not.
        keepalive.cancel()
        await _drop_reservation(session_key, token, session)


async def _teardown_abandoned_session(
    container: ResolvedContainer, session_key: str, session: dict[str, Any]
) -> bool:
    """Free a container whose owner vanished without releasing (heartbeat went
    stale). Same order as an owner release: stop the emulator so the card is
    quiescent, evacuate and wipe it, credit the owner's playtime, then drop
    the claim.

    Returns False when the session stopped looking abandoned before any of that
    started, meaning the owner came back or another request got here first.
    """
    # Claim the teardown before touching the broker. The work below runs for
    # seconds, and the staleness check that led here is older still, so without
    # the marker a heartbeat landing in that window would refresh a claim whose
    # container is already being wiped. Re-checking staleness under the same
    # watch is what makes the decision current rather than the caller's, and the
    # marker's own token is what keeps a second claim from running all of this
    # a second time over the same container.
    token = secrets.token_hex(8)
    try:
        marked = await replace_session_if(
            session_key,
            lambda current: session_is_stale(current) and same_claim(current, session),
            drain_marker(token),
            DRAIN_MARKER_TTL,
        )
    except StreamingSessionContended:
        # Somebody is writing to this key, so it is not the derelict session
        # this path exists to clean up.
        return False
    if not marked:
        return False

    keepalive = asyncio.ensure_future(hold_drain_marker(session_key, token))
    try:
        state_slot = await quiesce_container(container, session)
        await record_play_session(session)
        await clear_session_activity(session_key, session)
        # That tab may still be showing the stream, so leave the same note an
        # admin force-release does rather than letting the picture simply stop.
        await record_termination(
            session, session_key, ended_by=None, reason="abandoned"
        )
        await collect_exit_state(container, session, state_slot)
        collect_exit_saves(container, session)
    except Exception:
        log.exception("abandoned session teardown failed, key=%s", session_key)
    finally:
        # A step raising above would otherwise leave the container unclaimable
        # until the marker expires: draining blocks the claim, the takeover
        # skips it, and no release path owns it. Only this teardown's own marker
        # goes, never a claim that replaced it in the meantime.
        keepalive.cancel()
        await drop_drain_marker(session_key, token)
    return True


# How long a claim waits for stale sessions to be torn down before it gives up.
# The teardown stops a broker, evacuates and wipes a card and pulls the exit
# state, each with its own timeout and retries, so on a sick container it can
# run for minutes. A claim is an interactive request and must not, so this is
# the budget for the whole sweep rather than for each container in it.
ABANDONED_TEARDOWN_WAIT = 30.0


async def await_teardown_within_budget(
    container: ResolvedContainer,
    session_key: str,
    session: dict[str, Any],
    budget: float,
) -> bool:
    """Tear down an abandoned session, but only wait `budget` seconds for it.

    A teardown that overruns keeps running, shielded, and frees the container
    when it lands. It is never cancelled part-way: the card evacuation and the
    state pull are the abandoned player's only copies, and the drain marker
    this leaves behind blocks a claim until the teardown drops it.
    """
    task = background.spawn_sync_task(
        _teardown_abandoned_session(container, session_key, session)
    )
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=budget)
    except asyncio.TimeoutError:
        log.warning(
            "stale session teardown is taking too long, leaving it to finish, key=%s",
            session_key,
        )
        return False
