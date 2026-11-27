"""The achievements overview returns stored progress without waiting on artwork."""

import asyncio
from types import SimpleNamespace

import pytest

import handler.achievements_handler as achievements_handler
from handler.achievements_handler import library_overview


@pytest.fixture(autouse=True)
def _reset_media_task():
    achievements_handler._media_task = None
    yield
    task = achievements_handler._media_task
    achievements_handler._media_task = None
    if task is not None and not task.done():
        task.cancel()


@pytest.mark.asyncio
async def test_overview_returns_before_artwork_lookup(monkeypatch: pytest.MonkeyPatch):
    release = asyncio.Event()

    async def blocked() -> None:
        await release.wait()

    monkeypatch.setattr(
        "handler.metadata.meta_ra_handler.persist_missing_image_icons",
        blocked,
    )
    monkeypatch.setattr(
        "handler.database.db_rom_handler.get_library_achievement_sources",
        lambda: [
            {
                "id": 1,
                "name": "Tetris",
                "ra_id": 1,
                "platform_id": 1,
                "min_age": None,
                "platform_name": "NES",
                "platform_slug": "nes",
                "platform_fs_slug": "nes",
                "path_cover_l": None,
                "path_cover_s": None,
                "url_cover": None,
                "image_icon": "/Images/047227.png",
                "achievements": [
                    {
                        "badge_id": "a",
                        "title": "Start",
                        "points": 5,
                        "type": "progression",
                    }
                ],
            }
        ],
    )
    user = SimpleNamespace(ra_username="player", ra_progression={"results": []})

    overview = await asyncio.wait_for(
        library_overview(user, lambda _rom: True),
        timeout=1,
    )

    assert overview["games"][0]["name"] == "Tetris"
    assert overview["games"][0]["earned"] == 0
    release.set()
    task = achievements_handler._media_task
    if task is not None:
        await task
