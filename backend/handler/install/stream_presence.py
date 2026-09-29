"""Live "how many clients are pulling this install right now" presence.

Same Redis TTL + heartbeat shape as handler.activity_handler (there: "who's
playing this ROM right now"; here: "who's actively downloading this install
session's files right now"). An active pull against the stream-download
endpoint IS the heartbeat - no separate heartbeat endpoint or extra frontend
polling loop needed, and a client that goes to sleep mid-download simply
ages out of the count on its own once its heartbeats stop, the same way a
play session does.
"""

from __future__ import annotations

from handler.redis_handler import async_cache

# An active download re-heartbeats on every chunk request, far more often
# than this - short enough that a genuinely gone client drops off quickly,
# long enough to tolerate a brief stall between chunks.
VIEWER_TTL = 15
VIEWER_INDEX_TTL = 30
_KEY_PREFIX = "install_stream:viewer:"
_INDEX_PREFIX = "install_stream:viewers:"


def _viewer_key(session_id: int, user_id: int, device_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}:{user_id}:{device_id}"


def _index_key(session_id: int) -> str:
    return f"{_INDEX_PREFIX}{session_id}"


def _member(user_id: int, device_id: str) -> str:
    return f"{user_id}:{device_id}"


async def heartbeat(session_id: int, user_id: int, device_id: str) -> None:
    """Refresh (or create) this client's presence for `session_id`."""
    member = _member(user_id, device_id)
    async with async_cache.pipeline() as pipe:
        await pipe.set(_viewer_key(session_id, user_id, device_id), "1", ex=VIEWER_TTL)
        await pipe.sadd(_index_key(session_id), member)
        await pipe.expire(_index_key(session_id), VIEWER_INDEX_TTL)
        await pipe.execute()


async def count_viewers(session_id: int) -> int:
    """Current viewer count, self-healing: an expired member is dropped from
    the index as soon as it's found, same as
    activity_handler.get_active_for_rom."""
    index_key = _index_key(session_id)
    members = await async_cache.smembers(index_key)
    if not members:
        return 0

    stale: list[str] = []
    active = 0
    for member in members:
        # fakeredis (used under pytest) doesn't honor decode_responses the
        # way a real Redis connection does, so a member can arrive as bytes
        # there even though production always hands back str.
        if isinstance(member, bytes):
            member = member.decode()
        try:
            user_id_str, device_id = member.rsplit(":", 1)
            user_id = int(user_id_str)
        except ValueError, AttributeError:
            stale.append(member)
            continue
        if await async_cache.exists(_viewer_key(session_id, user_id, device_id)):
            active += 1
        else:
            stale.append(member)

    if stale:
        await async_cache.srem(index_key, *stale)
    return active
