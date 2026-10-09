from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from tests.factories import make_rom

from adapters.services.retroachievements_types import RAUserCompletionProgressKind
from handler.database import db_rom_handler
from handler.database.roms_handler import DBRomsHandler
from handler.database.users_handler import DBUsersHandler
from handler.metadata.ra_handler import RAHandler
from models.rom import RomUserStatus
from models.user import User
from tasks.scheduled.sync_retroachievements_progress import (
    SyncRetroAchievementsProgressTask,
    _get_rom_user_status_from_ra_award_kind,
)


@pytest.fixture
def task() -> SyncRetroAchievementsProgressTask:
    """Create a task instance for testing."""
    return SyncRetroAchievementsProgressTask()


def _progression(*games: tuple[int, str | None]) -> dict[str, Any]:
    return {
        "total": len(games),
        "results": [
            {"rom_ra_id": ra_id, "highest_award_kind": award_kind}
            for ra_id, award_kind in games
        ],
    }


def _mock_sync(
    mocker,
    user: User,
    progression: dict[str, Any],
    roms: list[tuple[int, int]],
) -> tuple[MagicMock, MagicMock]:
    """Patch one user's RA feed and the sync's DB calls.

    Returns:
        The `get_roms_by_ra_ids` and `set_rom_user_statuses` mocks.
    """
    mocker.patch.object(DBUsersHandler, "get_users", return_value=[user])
    mocker.patch.object(DBUsersHandler, "update_user")
    mocker.patch.object(RAHandler, "get_user_progression", return_value=progression)
    return (
        mocker.patch.object(
            DBRomsHandler,
            "get_roms_by_ra_ids",
            return_value=[SimpleNamespace(id=i, ra_id=r) for i, r in roms],
        ),
        mocker.patch.object(DBRomsHandler, "set_rom_user_statuses", return_value=0),
    )


class TestGetRomUserStatusFromRaAwardKind:
    """Tests for the _get_rom_user_status_from_ra_award_kind helper."""

    def test_mastered_returns_completed_100(self):
        assert (
            _get_rom_user_status_from_ra_award_kind(
                RAUserCompletionProgressKind.MASTERED
            )
            == RomUserStatus.COMPLETED_100
        )

    def test_completed_returns_completed_100(self):
        assert (
            _get_rom_user_status_from_ra_award_kind(
                RAUserCompletionProgressKind.COMPLETED
            )
            == RomUserStatus.COMPLETED_100
        )

    def test_beaten_hardcore_returns_finished(self):
        assert (
            _get_rom_user_status_from_ra_award_kind(
                RAUserCompletionProgressKind.BEATEN_HARDCORE
            )
            == RomUserStatus.FINISHED
        )

    def test_beaten_softcore_returns_finished(self):
        assert (
            _get_rom_user_status_from_ra_award_kind(
                RAUserCompletionProgressKind.BEATEN_SOFTCORE
            )
            == RomUserStatus.FINISHED
        )

    def test_none_returns_incomplete(self):
        assert _get_rom_user_status_from_ra_award_kind(None) == RomUserStatus.INCOMPLETE

    def test_unknown_value_returns_none(self):
        assert _get_rom_user_status_from_ra_award_kind("unknown_award") is None


class TestSyncRetroAchievementsProgressTask:
    """Test suite for SyncRetroAchievementsProgressTask."""

    def test_task_initialization(self, task):
        """Test task initialization with correct parameters."""
        assert (
            task.spec.description == "Updates RetroAchievements progress for all users"
        )

    async def test_run_when_retroachievements_api_disabled(self, task, mocker):
        """Test run method when RetroAchievements API is disabled."""
        mocker.patch.object(RAHandler, "is_enabled", return_value=False)
        mock_log = mocker.patch("tasks.scheduled.sync_retroachievements_progress.log")

        await task.run()

        mock_log.warning.assert_called_once_with(
            "RetroAchievements API is not enabled, skipping progress sync"
        )

    async def test_run_when_no_users_set(self, task, mocker):
        """Test run method when no users have RetroAchievements usernames set"""
        mock_get_users = mocker.patch.object(
            DBUsersHandler, "get_users", return_value=[]
        )
        mock_get_user_progression = mocker.patch.object(
            RAHandler, "get_user_progression"
        )

        await task.run()

        mock_get_users.assert_called_once_with(has_ra_username=True)
        mock_get_user_progression.assert_not_called()

    async def test_run_saves_progress(self, task, viewer_user, mocker):
        """Test run method saves retrieved progress."""
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mock_update_user = mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {"total": 0, "results": []}
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )

        await task.run()

        mock_update_user.assert_called_once_with(
            viewer_user.id,
            {"ra_progression": user_progression},
        )

    async def test_run_is_resilient_to_errors(
        self, task, viewer_user, editor_user, mocker
    ):
        """Test run method saves retrieved progress for a user even if another user fails."""
        mocker.patch.object(
            DBUsersHandler, "get_users", return_value=[viewer_user, editor_user]
        )
        user_progression = {"total": 0, "results": []}
        mocker.patch.object(
            RAHandler,
            "get_user_progression",
            side_effect=[
                # Call for first user raises an exception.
                Exception("API error"),
                # Call for second user returns valid progression.
                user_progression,
            ],
        )
        mock_update_user = mocker.patch.object(DBUsersHandler, "update_user")

        await task.run()

        mock_update_user.assert_called_once_with(
            editor_user.id,
            {"ra_progression": user_progression},
        )

    @pytest.mark.parametrize(
        ("award_kind", "expected_status"),
        [
            (RAUserCompletionProgressKind.MASTERED, RomUserStatus.COMPLETED_100),
            (RAUserCompletionProgressKind.BEATEN_SOFTCORE, RomUserStatus.FINISHED),
            (None, RomUserStatus.INCOMPLETE),
        ],
    )
    async def test_run_maps_award_to_rom_user_status(
        self, task, viewer_user, mocker, award_kind, expected_status
    ):
        _, mock_set_statuses = _mock_sync(
            mocker,
            viewer_user,
            _progression((12345, award_kind)),
            roms=[(1, 12345)],
        )

        await task.run()

        mock_set_statuses.assert_called_once_with(viewer_user.id, {1: expected_status})

    async def test_run_skips_status_update_when_rom_not_found(
        self, task, viewer_user, mocker
    ):
        """Test that status update is skipped when the ROM is not in the database."""
        _, mock_set_statuses = _mock_sync(
            mocker,
            viewer_user,
            _progression((99999, RAUserCompletionProgressKind.MASTERED)),
            roms=[],
        )

        await task.run()

        mock_set_statuses.assert_called_once_with(viewer_user.id, {})

    async def test_run_skips_unknown_award(self, task, viewer_user, mocker):
        """An unrecognised award kind is skipped without a write."""
        mock_get_roms, mock_set_statuses = _mock_sync(
            mocker,
            viewer_user,
            _progression((12345, "unknown_award")),
            roms=[],
        )

        await task.run()

        mock_get_roms.assert_called_once_with([])
        mock_set_statuses.assert_called_once_with(viewer_user.id, {})

    async def test_run_batches_one_read_and_one_write_per_user(
        self, task, viewer_user, mocker
    ):
        """Regional ROMs sharing an ra_id all get that game's status."""
        mock_get_roms, mock_set_statuses = _mock_sync(
            mocker,
            viewer_user,
            _progression(
                (12345, RAUserCompletionProgressKind.MASTERED),
                (67890, None),
            ),
            roms=[(1, 12345), (2, 12345), (3, 67890)],
        )

        await task.run()

        mock_get_roms.assert_called_once_with([12345, 67890])
        mock_set_statuses.assert_called_once_with(
            viewer_user.id,
            {
                1: RomUserStatus.COMPLETED_100,
                2: RomUserStatus.COMPLETED_100,
                3: RomUserStatus.INCOMPLETE,
            },
        )

    async def test_run_continues_after_status_sync_error(
        self, task, viewer_user, editor_user, mocker
    ):
        """A status-sync failure for one user still syncs the next user."""
        mock_get_roms, mock_set_statuses = _mock_sync(
            mocker,
            viewer_user,
            _progression((12345, RAUserCompletionProgressKind.MASTERED)),
            roms=[],
        )
        mocker.patch.object(
            DBUsersHandler, "get_users", return_value=[viewer_user, editor_user]
        )
        mock_get_roms.side_effect = [
            Exception("DB error"),
            [SimpleNamespace(id=1, ra_id=12345)],
        ]

        await task.run()

        mock_set_statuses.assert_called_once_with(
            editor_user.id, {1: RomUserStatus.COMPLETED_100}
        )

    async def test_run_syncs_real_rows(self, task, viewer_user, platform, mocker):
        """Unmocked getters: every regional ROM is synced and RETIRED is kept."""
        usa_rom = make_rom(platform, "Game USA", ra_id=12345)
        eur_rom = make_rom(platform, "Game Europe", ra_id=12345)
        retired_rom = make_rom(platform, "Retired Game", ra_id=67890)
        retired_rom_user = db_rom_handler.add_rom_user(retired_rom.id, viewer_user.id)
        db_rom_handler.update_rom_user(
            retired_rom_user.id, {"status": RomUserStatus.RETIRED}
        )
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        mocker.patch.object(
            RAHandler,
            "get_user_progression",
            return_value=_progression(
                (12345, RAUserCompletionProgressKind.MASTERED),
                (67890, RAUserCompletionProgressKind.MASTERED),
            ),
        )

        await task.run()

        for synced_rom in (usa_rom, eur_rom):
            rom_user = db_rom_handler.get_rom_user(synced_rom.id, viewer_user.id)
            assert rom_user is not None
            assert rom_user.status == RomUserStatus.COMPLETED_100
        rom_user = db_rom_handler.get_rom_user(retired_rom.id, viewer_user.id)
        assert rom_user is not None
        assert rom_user.status == RomUserStatus.RETIRED
