"""The Redis-backed record of which container is serving whom.

A session outlives the request that made it and is shared across uvicorn
workers, so it lives in Redis rather than in process memory: the emulator
container keeps running across a backend restart either way, and a claim that
did not survive would strand it. Claiming uses SET NX, which is atomic, so two
concurrent claims for one container cannot both win with no in-process locking.

Everything that mutates a session goes through the compare-and-set helpers
here. A blind write would resurrect a claim a concurrent release had just
deleted, which is the difference between a container that frees itself and one
wedged until its TTL lapses.
"""

import asyncio
import json
import secrets
import time
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, NamedTuple

from redis.exceptions import WatchError

from handler.redis_handler import async_cache
from handler.socket_handler import socket_handler
from logger.logger import log

# Sessions are stored in Redis so they are shared across uvicorn workers and
# survive backend restarts (the emulator container keeps running either way).
# Claiming uses SET NX, which is atomic in Redis. Two concurrent claims for
# the same container cannot both succeed, with no in-process locking needed.
SESSION_KEY_PREFIX = "romm:streaming:session:"

# An active session is long-lived (a game can run for hours), but the key
# must not live forever: if the broker container dies or the backend
# crashes mid-session, the TTL ensures the container is eventually
# reclaimable instead of wedged until an admin force-releases. Control
# calls (save-state / volume / mute / save-and-exit) and the heartbeat
# refresh the TTL so a session in active use never expires.
STREAMING_SESSION_TTL_SECONDS = 6 * 60 * 60

# When save-and-exit runs with wait=false the broker is still killing the
# emulator in the background when the route returns. A short drain TTL
# keeps the key briefly so a concurrent new claim can't /launch on top of
# a not-yet-dead emulator (which would lose the in-flight save). The key
# expires on its own; no explicit DELETE.
STREAMING_SESSION_DRAIN_SECONDS = 5

# Save-and-exit holds the container past the drain window when an exit state is
# still coming back out of it. The marker is short and refreshed for as long as
# the pull runs (see hold_drain_marker) rather than sized to the slowest
# possible transfer, so a backend that dies mid-pull frees the container in a
# minute instead of parking it for the length of a transfer nobody is doing.
DRAIN_MARKER_TTL = 60
_DRAIN_MARKER_REFRESH = 20

# A live player refreshes `last_seen` roughly every 30s (frontend heartbeat,
# piggybacked on the activity interval). A session whose stamp is older than
# this is abandoned (tab closed, browser crashed, network gone) and the next
# claim may tear it down and take the container over. Generous enough to ride
# out background-tab timer throttling (browsers wake timers at least once a
# minute).
_STREAMING_SESSION_STALE_SECONDS = 180

# How often backend-side work running under a claim restamps it. Well inside the
# stale window, so a single missed refresh cannot hand the container away.
_CLAIM_REFRESH_SECONDS = _STREAMING_SESSION_STALE_SECONDS // 3

# How long a marker or a claim may be kept alive by the work behind it. Past
# this the refresh stops and the container ages back out on its own: every step
# under a keepalive carries its own timeout, so overrunning this means something
# is wedged, and a wedged step must not reserve a container indefinitely.
_HOLD_CEILING_SECONDS = 15 * 60


def session_redis_key(session_key: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_key}"


async def get_session(session_key: str) -> dict[str, Any] | None:
    raw = await async_cache.get(session_redis_key(session_key))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        # Corrupt entry, drop it rather than wedging the container forever.
        await async_cache.delete(session_redis_key(session_key))
        return None


async def get_live_session(session_key: str) -> dict[str, Any] | None:
    """The session occupying a container, or None when nobody holds it.

    A drain marker holds the key while a teardown finishes: it has no owner and
    nothing to release, so every reader that asks "who is on this container"
    wants it treated as absent.
    """
    session = await get_session(session_key)
    if session is None or session.get("draining"):
        return None
    return session


async def iter_session_keys() -> AsyncIterator[str]:
    """Every container key with a session row in the cache."""
    async for key in async_cache.scan_iter(match=f"{SESSION_KEY_PREFIX}*"):
        # scan_iter yields bytes unless the client decodes responses.
        key_str = key.decode() if isinstance(key, bytes) else key
        yield key_str.removeprefix(SESSION_KEY_PREFIX)


async def iter_live_sessions() -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Every occupied container, as (container key, session). Unreadable rows
    and drain markers are skipped, so listing routes never re-decide either."""
    async for container_key in iter_session_keys():
        session = await get_live_session(container_key)
        if session is not None:
            yield container_key, session


async def refresh_session(session_key: str) -> None:
    """Reset the session TTL back to the full window. Called after every
    successful control op so a session in active use never expires; only an
    abandoned one (broker dead / backend crashed) ages out."""
    await async_cache.expire(
        session_redis_key(session_key), STREAMING_SESSION_TTL_SECONDS
    )


# A contended session key is rewritten by at most a heartbeat, a swap and a
# release, so a handful of retries is far more than the contention warrants.
_STREAMING_SESSION_CAS_ATTEMPTS = 5


class StreamingSessionContended(Exception):
    """The session key stayed contended for the whole CAS budget.

    Kept apart from the None that means "gone": a key nobody could write is
    still a key that exists, and callers that treat it as a vanished claim
    report a live session as ended.
    """


class _CasOutcome(Enum):
    """How one compare-and-set against a session key ended."""

    WROTE = auto()
    MISSING = auto()  # nothing at the key
    CORRUPT = auto()  # the key held something that is not a session
    REJECTED = auto()  # the plan declined to write against what it read
    VANISHED = auto()  # the write found no key left to overwrite


class _SessionWrite(NamedTuple):
    """What a plan wants left at the key: JSON with a TTL, or a delete."""

    value: str | None
    ttl: int | None = None


async def cas_session(
    session_key: str,
    plan: Callable[[dict[str, Any]], _SessionWrite | None],
) -> tuple[_CasOutcome, dict[str, Any] | None]:
    """Run `plan` against the session at `session_key` and apply what it asks
    for, atomically.

    The whole session is one JSON blob, so a plain read-modify-write silently
    drops whichever concurrent update landed in between: a heartbeat racing a
    disc swap would write back a copy with no `disc_file_id`. WATCH aborts the
    write when the key moved under us and the retry re-reads.

    `plan` sees the freshly read session inside the same watch, so a caller can
    act on a condition without it going stale between the check and the write,
    and returns the write to make or None to abandon this attempt. Returns the
    outcome and the session `plan` was given, which callers map to their own
    conventions since "gone", "refused" and "the write found nothing" mean
    different things to each of them. Raises `StreamingSessionContended` once
    the retry budget is spent.
    """
    key = session_redis_key(session_key)
    for _ in range(_STREAMING_SESSION_CAS_ATTEMPTS):
        async with async_cache.pipeline() as pipe:
            await pipe.watch(key)
            raw = await pipe.get(key)
            if raw is None:
                await pipe.unwatch()
                return _CasOutcome.MISSING, None
            try:
                session = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                session = None
            if not isinstance(session, dict):
                await pipe.unwatch()
                # Drop it rather than wedging the container until the TTL.
                await async_cache.delete(key)
                return _CasOutcome.CORRUPT, None
            write = plan(session)
            if write is None:
                await pipe.unwatch()
                return _CasOutcome.REJECTED, session
            pipe.multi()
            if write.value is None:
                await pipe.delete(key)
            else:
                # xx so a release landing between the watch and the exec cannot
                # be undone by resurrecting the key.
                await pipe.set(key, write.value, xx=True, ex=write.ttl)
            try:
                results = await pipe.execute()
            except WatchError:
                continue
            # An expiry between the watch and the exec does not abort the
            # transaction, so an xx write can succeed having set nothing.
            if write.value is not None and not (results and results[0]):
                return _CasOutcome.VANISHED, session
            return _CasOutcome.WROTE, session
    raise StreamingSessionContended(session_key)


async def mutate_session(
    session_key: str,
    changes: dict[str, Any],
    *,
    require: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any] | None:
    """Merge `changes` into a live session, atomically.

    Returns the stored session, or None when the key is gone, corrupt, or
    `require` rejected it. Raises `StreamingSessionContended` when the write
    never landed, which is not the same as the key being gone.
    """

    def plan(session: dict[str, Any]) -> _SessionWrite | None:
        if require is not None and not require(session):
            return None
        session.update(changes)
        return _SessionWrite(json.dumps(session), STREAMING_SESSION_TTL_SECONDS)

    outcome, session = await cas_session(session_key, plan)
    return session if outcome is _CasOutcome.WROTE else None


def same_claim(session: dict[str, Any], claim: dict[str, Any]) -> bool:
    """Whether a session read back is still the one a route resolved. Identity is
    the holder plus the moment they took it, so a re-claim by the same user does
    not pass for the claim it replaced."""
    return (
        not session.get("draining")
        and session.get("user_id") == claim.get("user_id")
        and session.get("claimed_at") == claim.get("claimed_at")
    )


async def replace_session_if(
    session_key: str,
    require: Callable[[dict[str, Any]], bool],
    value: str | None,
    ttl: int | None = None,
) -> bool:
    """Overwrite or delete a session key, while `require` accepts what is there.

    Returns True when the intended state is what the key now holds, False when
    `require` rejected it. A delete finding the key already gone counts as done;
    a write that did not land does not, so it raises
    `StreamingSessionContended` along with running out of retries. The caller
    still holds what it tried to give up in that case, and must not report
    otherwise.
    """
    outcome, _ = await cas_session(
        session_key,
        lambda current: _SessionWrite(value, ttl) if require(current) else None,
    )
    if outcome is _CasOutcome.MISSING:
        return value is None
    if outcome is _CasOutcome.VANISHED:
        raise StreamingSessionContended(session_key)
    return outcome is _CasOutcome.WROTE


def drain_marker(token: str) -> str:
    return json.dumps({"draining": True, "drain_token": token})


async def claim_drain_marker(
    session_key: str, claim: dict[str, Any], ttl: int = DRAIN_MARKER_TTL
) -> str | None:
    """Replace a session with a drain marker, while the key still holds the claim
    that is exiting.

    Deliberately not a session record: the session is over, and joinable and the
    admin views must not keep advertising it. Deliberately not an unconditional
    write either, since an admin force-release and a fresh claim both fit inside
    the blocking save+kill that runs before this, and the marker would bury a
    session somebody is playing.

    Returns the token the marker carries, or None when the key had moved on.
    Raises `StreamingSessionContended` when the marker never landed, which leaves the
    container held by a claim the caller has already stopped.
    """
    token = secrets.token_hex(8)
    landed = await replace_session_if(
        session_key,
        lambda current: same_claim(current, claim),
        drain_marker(token),
        ttl,
    )
    return token if landed else None


async def hold_drain_marker(session_key: str, token: str) -> None:
    """Keep a drain marker alive for as long as the work behind it runs.

    The marker is short-lived and refreshed rather than sized to the slowest
    imaginable pull: a backend that dies mid-pull then frees the container in a
    minute instead of parking it for the length of a transfer nobody is doing.
    """
    marker = drain_marker(token)
    deadline = time.monotonic() + _HOLD_CEILING_SECONDS
    while True:
        await asyncio.sleep(_DRAIN_MARKER_REFRESH)
        try:
            held = await replace_session_if(
                session_key,
                lambda current: current.get("drain_token") == token,
                marker,
                DRAIN_MARKER_TTL,
            )
        except StreamingSessionContended:
            # Contention is not a takeover: the marker is still ours, the write
            # just did not land. Stopping here would leave the work behind the
            # marker running against a key nothing refreshes.
            continue
        if not held:
            log.warning("drain marker on %s is no longer ours", session_key)
            return
        if time.monotonic() >= deadline:
            log.warning(
                "stopped refreshing the drain marker on %s, the work behind it "
                "has run for over %ss",
                session_key,
                _HOLD_CEILING_SECONDS,
            )
            return


async def hold_session_claim(session_key: str, claim: dict[str, Any]) -> None:
    """Keep a claim's liveness stamp current for as long as work runs under it.

    For the paths where a drain marker could not be written and the claim itself
    is what reserves the container. The stamp is the player's, and the player is
    gone, so without this the record ages past `_STREAMING_SESSION_STALE_SECONDS` and the
    next claimant tears the container down mid-work.
    """
    deadline = time.monotonic() + _HOLD_CEILING_SECONDS
    while True:
        await asyncio.sleep(_CLAIM_REFRESH_SECONDS)
        try:
            held = await mutate_session(
                session_key,
                {"last_seen": datetime.now(timezone.utc).isoformat()},
                require=lambda current: same_claim(current, claim),
            )
        except StreamingSessionContended:
            continue
        if held is None:
            log.warning("claim on %s is no longer ours", session_key)
            return
        if time.monotonic() >= deadline:
            log.warning(
                "stopped refreshing the claim on %s, the work behind it has run "
                "for over %ss",
                session_key,
                _HOLD_CEILING_SECONDS,
            )
            return


async def stamp_launched(session_key: str, claim: dict[str, Any]) -> None:
    """Record that the activate returned, so the status poll stops asking the
    broker for an extraction phase.

    Guarded on the claim it was made for, like `set_session_disc`: an activate
    outlives the claim when a release lands while it runs, and an unguarded
    write would stamp a stranger's session or bring a short drain marker back
    with a six-hour TTL that no release path owns.

    Best-effort: a stamp that never lands only costs a few redundant broker
    round trips, and failing a session that is already up would be worse.
    """
    try:
        await mutate_session(
            session_key,
            {"launched_at": datetime.now(timezone.utc).isoformat()},
            require=lambda current: same_claim(current, claim),
        )
    except StreamingSessionContended:
        log.warning("could not stamp the launch on session %s", session_key)


async def drop_drain_marker(session_key: str, token: str) -> None:
    """Delete a drain marker, while it is still the one `token` wrote.

    A marker that expired, or that a later exit replaced, belongs to whoever
    holds the container now, and deleting it would free a container mid-play.
    """
    try:
        await replace_session_if(
            session_key,
            lambda current: current.get("drain_token") == token,
            None,
        )
    except StreamingSessionContended:
        log.warning("could not drop the drain marker on %s", session_key)


async def release_own_session(session_key: str, claim: dict[str, Any]) -> bool:
    """Free a container, while the key still holds the claim being released.

    Save-and-exit blocks on the broker for as long as the emulator takes to
    write and die, and an admin force-release plus a new claim both fit in that
    window. The unguarded delete would then end a session that had just begun.

    False means the container is still held, either by somebody else's claim or
    because the delete never landed.
    """
    try:
        return await replace_session_if(
            session_key, lambda current: same_claim(current, claim), None
        )
    except StreamingSessionContended:
        log.warning("could not release session %s", session_key)
        return False


async def set_session_disc(
    session_key: str, file_id: int, broker_session_id: str | None = None
) -> None:
    """Record the disc a session is now running.

    The write only lands on the claim it was made for. A swap can outlive that
    claim: the broker holds it until the game is up, by which time the key can
    be the short drain marker save-and-exit leaves behind, or a fresh claim by
    someone else. Writing either would stamp the wrong disc, and the drain
    marker would come back with a six-hour TTL that no release path owns.

    Best-effort: the disc is already in the tray by the time this runs, so a
    key that could not be written costs the next state capture its disc, not
    the swap the player asked for.
    """

    def _still_the_same_claim(session: dict[str, Any]) -> bool:
        if session.get("draining"):
            return False
        return (
            broker_session_id is None
            or session.get("broker_session_id") == broker_session_id
        )

    try:
        written = await mutate_session(
            session_key, {"disc_file_id": file_id}, require=_still_the_same_claim
        )
    except StreamingSessionContended:
        written = None
    if written is None:
        log.warning("could not record disc %s on session %s", file_id, session_key)


def broker_session_id(session: dict[str, Any]) -> str | None:
    """The id activate gave the broker, absent on sessions claimed before it."""
    value = session.get("broker_session_id")
    return str(value) if value else None


def session_disc_id(session: dict[str, Any]) -> int | None:
    """The disc a swap put this session on, if any."""
    value = session.get("disc_file_id")
    return value if isinstance(value, int) else None


def session_is_stale(session: dict[str, Any]) -> bool:
    """True when the owner's heartbeat stopped long enough ago that the session
    counts as abandoned. Sessions written before heartbeats existed carry no
    `last_seen`; their `claimed_at` stands in. An unparseable stamp counts as
    stale so a corrupt record cannot wedge the container."""
    stamp = session.get("last_seen") or session.get("claimed_at")
    if not isinstance(stamp, str):
        return True
    try:
        seen = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - seen).total_seconds()
    return age > _STREAMING_SESSION_STALE_SECONDS


# ── Termination notices ───────────────────────────────────────────────────────

# An admin force-release deletes the session key, but the displaced player's
# browser is still showing a stream that no longer exists. A tombstone keyed by
# container and displaced user lets their next poll say who ended it and why,
# instead of the picture simply stopping. Cleared when that user claims again;
# the TTL covers the case where they never come back.
_TERMINATION_KEY_PREFIX = "romm:streaming:terminated:"
_TERMINATION_TTL_SECONDS = 15 * 60


def _termination_redis_key(session_key: str, user_id: int) -> str:
    return f"{_TERMINATION_KEY_PREFIX}{session_key}:{user_id}"


async def record_termination(
    session: dict[str, Any],
    session_key: str,
    *,
    ended_by: str | None,
    reason: str | None,
) -> None:
    """Leave a note for the player whose session was taken away, and push it
    over the socket so the poll isn't the only way that tab finds out. No-op
    when the session records no owner, since there is nobody to notify."""
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return
    notice = {
        "ended_by": ended_by,
        "reason": reason or None,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "platform": session.get("platform"),
        "rom_id": session.get("rom_id"),
        "rom_name": session.get("rom_name"),
    }
    await async_cache.set(
        _termination_redis_key(session_key, user_id),
        json.dumps(notice),
        ex=_TERMINATION_TTL_SECONDS,
    )
    await push_to_user(user_id, "streaming:session-ended", notice)


async def push_to_user(user_id: Any, event: str, payload: dict[str, Any]) -> None:
    """Tell one user's open tabs something happened to their session.

    Best-effort by design: every event pushed here also has a poll behind it,
    so a dropped socket costs latency rather than correctness.
    """
    if not isinstance(user_id, int):
        return
    try:
        await socket_handler.socket_server.emit(event, payload, room=f"user:{user_id}")
    except Exception:  # noqa: BLE001
        log.warning("Failed to push %s", event, exc_info=True)


async def get_termination(session_key: str, user_id: int) -> dict[str, Any] | None:
    raw = await async_cache.get(_termination_redis_key(session_key, user_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        await async_cache.delete(_termination_redis_key(session_key, user_id))
        return None


async def clear_termination(session_key: str, user_id: int) -> None:
    await async_cache.delete(_termination_redis_key(session_key, user_id))
