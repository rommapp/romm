"""ROM id lists too long for a URL, held for `GET /roms/download?selection=`."""

import json
import secrets
from typing import Final, cast

from handler.redis_handler import async_cache

# Outlives the download itself so a resumed transfer still resolves.
DOWNLOAD_SELECTION_TTL: Final[int] = 3600


def _selection_key(user_id: int | None) -> str:
    return f"romm:bulk-download-selection:{user_id}"


async def store_download_selection(user_id: int | None, rom_ids: list[int]) -> str:
    """Store a user's selection, replacing their previous one.

    One selection per user keeps Redis bounded however often this is called.

    Returns:
        The token that names the selection.
    """
    token = secrets.token_urlsafe(16)
    await async_cache.set(
        _selection_key(user_id),
        json.dumps({"token": token, "rom_ids": rom_ids}),
        ex=DOWNLOAD_SELECTION_TTL,
    )
    return token


async def resolve_download_selection(
    user_id: int | None, token: str
) -> list[int] | None:
    """The ROM ids stored under `token` for this user, or None."""
    raw = await async_cache.get(_selection_key(user_id))
    stored = json.loads(raw) if raw else None
    if not stored or not secrets.compare_digest(stored["token"], token):
        return None
    return cast(list[int], stored["rom_ids"])
