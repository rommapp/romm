"""Library RetroAchievements overview for the signed-in user."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from logger.logger import log

_media_task: asyncio.Task[None] | None = None


def schedule_achievement_media_fill() -> None:
    """Fill missing icons and screen art after the response, one fill at a time."""
    global _media_task
    if _media_task is not None and not _media_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _media_task = loop.create_task(_fill_achievement_media())


async def _fill_achievement_media() -> None:
    from handler.metadata import meta_ra_handler

    try:
        await meta_ra_handler.persist_missing_image_icons()
    except Exception:
        log.exception("RetroAchievements artwork fill failed")


async def library_overview(
    user: Any, can_see_rom: Callable[[Any], bool]
) -> dict[str, Any]:
    """Visible RetroAchievements progress from data already stored on each ROM."""
    from handler.database import db_rom_handler
    from handler.metadata.earned_achievements import build_achievement_overview

    progression = user.ra_progression if isinstance(user.ra_progression, dict) else None
    linked = bool((getattr(user, "ra_username", None) or "").strip())
    synced = linked and isinstance(progression, dict) and "results" in progression
    visible: list[dict[str, Any]] = []
    if synced:
        visible = [
            source
            for source in db_rom_handler.get_library_achievement_sources()
            if can_see_rom(
                SimpleNamespace(
                    id=source["id"],
                    platform_id=source["platform_id"],
                    min_age=source["min_age"],
                )
            )
        ]
        schedule_achievement_media_fill()
    return build_achievement_overview(
        ra_username=getattr(user, "ra_username", None),
        ra_progression=progression,
        roms=visible,
    )
