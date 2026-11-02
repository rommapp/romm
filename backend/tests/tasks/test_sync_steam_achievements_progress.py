from typing import Any
from unittest.mock import AsyncMock

import pytest
from tests.factories import make_rom

from handler.database import db_rom_handler, db_user_handler
from handler.database.users_handler import DBUsersHandler
from handler.metadata.steam_handler import SteamHandler
from models.platform import Platform
from models.rom import RomUserStatus
from models.user import User
from tasks.scheduled.sync_steam_achievements_progress import (
    SteamGameDetailsPrivateError,
    SyncSteamAchievementsProgressTask,
    sync_user_progress,
)

STEAM_ID = "76561197960287930"


def _game(app_id: int, total: int, unlocked: int) -> dict[str, Any]:
    return {
        "rom_steam_id": app_id,
        "rtime_last_played": 1700000000,
        "playtime_forever": 60,
        "num_achievements": total,
        "num_unlocked": unlocked,
        "earned_achievements": [],
    }


@pytest.fixture
def steam_user(viewer_user: User) -> User:
    updated = db_user_handler.update_user(viewer_user.id, {"steam_id": STEAM_ID})
    assert updated is not None
    return updated


@pytest.fixture
def achievements_enabled(mocker):
    mocker.patch.object(SteamHandler, "achievements_enabled", return_value=True)


async def test_sync_stores_progression_and_completes_fully_unlocked_games(
    steam_user: User, platform: Platform, mocker
):
    completed = make_rom(platform, "Portal", steam_id=400)
    regional = make_rom(platform, "Portal (EU)", steam_id=400)
    started = make_rom(platform, "Portal 2", steam_id=620)
    progression = {"total": 2, "results": [_game(400, 15, 15), _game(620, 10, 3)]}
    get_progression = mocker.patch.object(
        SteamHandler, "get_user_progression", AsyncMock(return_value=progression)
    )

    await sync_user_progress(steam_user)

    assert get_progression.await_args.args[1] == {400, 620}
    stored = db_user_handler.get_user(steam_user.id)
    assert stored is not None and stored.steam_progression == progression
    for rom, expected in (
        (completed, RomUserStatus.COMPLETED_100),
        (regional, RomUserStatus.COMPLETED_100),
        (started, None),
    ):
        rom_user = db_rom_handler.get_rom_user(rom.id, steam_user.id)
        assert (rom_user.status if rom_user else None) == expected


async def test_sync_passes_the_stored_progression_only_when_incremental(
    steam_user: User, mocker
):
    stored = {"total": 1, "results": [_game(400, 2, 1)]}
    db_user_handler.update_user(steam_user.id, {"steam_progression": stored})
    user = db_user_handler.get_user(steam_user.id)
    assert user is not None
    get_progression = mocker.patch.object(
        SteamHandler,
        "get_user_progression",
        AsyncMock(return_value={"total": 0, "results": []}),
    )

    await sync_user_progress(user)
    await sync_user_progress(user, incremental=False)

    calls = get_progression.await_args_list
    assert calls[0].kwargs["current_progression"] == stored
    assert calls[1].kwargs["current_progression"] is None


async def test_sync_keeps_the_stored_progression_when_game_details_are_private(
    steam_user: User, mocker
):
    stored = {"total": 1, "results": [_game(400, 2, 1)]}
    db_user_handler.update_user(steam_user.id, {"steam_progression": stored})
    mocker.patch.object(
        SteamHandler, "get_user_progression", AsyncMock(return_value=None)
    )

    with pytest.raises(SteamGameDetailsPrivateError):
        await sync_user_progress(steam_user)

    user = db_user_handler.get_user(steam_user.id)
    assert user is not None and user.steam_progression == stored


async def test_run_skips_when_achievements_are_disabled(mocker):
    mocker.patch.object(SteamHandler, "achievements_enabled", return_value=False)
    get_users = mocker.patch.object(DBUsersHandler, "get_users")

    await SyncSteamAchievementsProgressTask().run()

    get_users.assert_not_called()


@pytest.mark.usefixtures("achievements_enabled")
async def test_run_syncs_every_linked_user_despite_a_failure(
    viewer_user: User, editor_user: User, mocker
):
    mocker.patch.object(
        DBUsersHandler, "get_users", return_value=[viewer_user, editor_user]
    )
    sync = mocker.patch(
        "tasks.scheduled.sync_steam_achievements_progress.sync_user_progress",
        AsyncMock(side_effect=[RuntimeError("Steam down"), None]),
    )

    stats = await SyncSteamAchievementsProgressTask().run()

    assert [c.args[0] for c in sync.await_args_list] == [viewer_user, editor_user]
    assert stats["processed"] == stats["total"] == 2


def test_get_users_filters_by_a_linked_steam_profile(
    steam_user: User, editor_user: User
):
    linked = {u.id for u in db_user_handler.get_users(has_steam_id=True)}
    unlinked = {u.id for u in db_user_handler.get_users(has_steam_id=False)}

    assert steam_user.id in linked and steam_user.id not in unlinked
    assert editor_user.id in unlinked and editor_user.id not in linked


def test_get_steam_ids_lists_each_matched_app_once(platform: Platform):
    make_rom(platform, "Portal", steam_id=400)
    make_rom(platform, "Portal (EU)", steam_id=400)
    make_rom(platform, "Unmatched")

    assert db_rom_handler.get_steam_ids() == {400}
