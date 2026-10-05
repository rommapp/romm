from unittest.mock import MagicMock

import pytest

from adapters.services.retroachievements_types import RAUserCompletionProgressKind
from handler.database.roms_handler import DBRomsHandler
from handler.database.users_handler import DBUsersHandler
from handler.metadata.ra_handler import RAHandler
from models.rom import RomUser, RomUserStatus
from tasks.scheduled.sync_retroachievements_progress import (
    SyncRetroAchievementsProgressTask,
    _get_rom_user_status_from_ra_award_kind,
)


@pytest.fixture
def task() -> SyncRetroAchievementsProgressTask:
    """Create a task instance for testing."""
    return SyncRetroAchievementsProgressTask()


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

    async def test_run_sets_rom_user_status_when_unset(
        self, task, viewer_user, rom, mocker
    ):
        """Test that rom_user.status is set from RA award kind when currently unset."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "max_possible": 50,
                    "num_awarded": 50,
                    "num_awarded_hardcore": 50,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                    "earned_achievements": [],
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = None
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_rom.id: mock_rom_user},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_called_once_with(
            mock_rom_user.id, {"status": RomUserStatus.COMPLETED_100}
        )

    async def test_run_updates_existing_rom_user_status_when_changed(
        self, task, viewer_user, rom, mocker
    ):
        """Test that rom_user.status is updated when the RA award kind changes."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "max_possible": 50,
                    "num_awarded": 50,
                    "num_awarded_hardcore": 50,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                    "earned_achievements": [],
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        # Previously INCOMPLETE (set by an earlier sync), now mastered in RA
        mock_rom_user.status = RomUserStatus.INCOMPLETE
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_rom.id: mock_rom_user},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_called_once_with(
            mock_rom_user.id, {"status": RomUserStatus.COMPLETED_100}
        )

    async def test_run_skips_update_when_status_already_matches(
        self, task, viewer_user, rom, mocker
    ):
        """Test that rom_user.status is not written again when it already matches RA."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "max_possible": 50,
                    "num_awarded": 50,
                    "num_awarded_hardcore": 50,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                    "earned_achievements": [],
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = RomUserStatus.COMPLETED_100  # Already up-to-date
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_rom.id: mock_rom_user},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_not_called()

    async def test_run_sets_incomplete_status_for_started_games(
        self, task, viewer_user, rom, mocker
    ):
        """Test that INCOMPLETE status is set for games started but not beaten in RA."""
        ra_id = 99999
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "max_possible": 100,
                    "num_awarded": 10,
                    "num_awarded_hardcore": 0,
                    "highest_award_kind": None,
                    "earned_achievements": [],
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = None
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_rom.id: mock_rom_user},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_called_once_with(
            mock_rom_user.id, {"status": RomUserStatus.INCOMPLETE}
        )

    async def test_run_skips_status_update_when_rom_not_found(
        self, task, viewer_user, mocker
    ):
        """Test that status update is skipped when the ROM is not in the database."""
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": 99999,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                    "earned_achievements": [],
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mocker.patch.object(DBRomsHandler, "get_roms_by_ra_ids", return_value=[])
        mock_rom_users = mocker.patch.object(DBRomsHandler, "get_rom_users_by_rom_ids")
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_not_called()
        mock_rom_users.assert_not_called()

    async def test_run_batches_reads_to_single_calls_per_user(
        self, task, viewer_user, rom, mocker
    ):
        """Two games in one feed issue one batched ROM read and one rom_user read."""
        ra_ids = [12345, 67890]
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 2,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                }
                for ra_id in ra_ids
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_roms = []
        for i, ra_id in enumerate(ra_ids):
            mock_rom = MagicMock()
            mock_rom.id = rom.id + i
            mock_rom.ra_id = ra_id
            mock_roms.append(mock_rom)
        mock_get_roms = mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=mock_roms
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = None
        mock_get_rom_users = mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_roms[0].id: mock_rom_user},
        )
        mock_add_rom_user = mocker.patch.object(
            DBRomsHandler, "add_rom_user", return_value=mock_rom_user
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_get_roms.assert_called_once_with(ra_ids)
        mock_get_rom_users.assert_called_once()
        assert mock_get_rom_users.call_args[0][0] == viewer_user.id
        assert sorted(mock_get_rom_users.call_args[0][1]) == sorted(
            [mock_rom.id for mock_rom in mock_roms]
        )
        mock_add_rom_user.assert_called_once_with(mock_roms[1].id, viewer_user.id)
        assert mock_update_rom_user.call_count == 2

    async def test_run_syncs_all_roms_sharing_one_ra_id(
        self, task, viewer_user, rom, mocker
    ):
        """Two regional ROM rows on one ra_id are each synced, not just one."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                },
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_roms = []
        for i in range(2):
            mock_rom = MagicMock()
            mock_rom.id = rom.id + i
            mock_rom.ra_id = ra_id
            mock_roms.append(mock_rom)
        mocker.patch.object(DBRomsHandler, "get_roms_by_ra_ids", return_value=mock_roms)
        mock_rom_users = []
        for mock_rom in mock_roms:
            mock_rom_user = MagicMock(spec=RomUser)
            mock_rom_user.id = mock_rom.id
            mock_rom_user.status = None
            mock_rom_users.append(mock_rom_user)
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={u.id: u for u in mock_rom_users},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        assert mock_update_rom_user.call_count == 2
        mock_update_rom_user.assert_any_call(
            mock_rom_users[0].id, {"status": RomUserStatus.COMPLETED_100}
        )
        mock_update_rom_user.assert_any_call(
            mock_rom_users[1].id, {"status": RomUserStatus.COMPLETED_100}
        )

    async def test_run_unknown_award_issues_no_db_calls(
        self, task, viewer_user, mocker
    ):
        """An unrecognised award kind skips the DB entirely."""
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": 12345,
                    "highest_award_kind": "unknown_award",
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_get_roms = mocker.patch.object(DBRomsHandler, "get_roms_by_ra_ids")
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_get_roms.assert_not_called()
        mock_update_rom_user.assert_not_called()

    async def test_run_skips_update_for_retired_status(
        self, task, viewer_user, rom, mocker
    ):
        """RETIRED rom_user rows are never overwritten by the sync."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = RomUserStatus.RETIRED
        mocker.patch.object(
            DBRomsHandler,
            "get_rom_users_by_rom_ids",
            return_value={mock_rom.id: mock_rom_user},
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_update_rom_user.assert_not_called()

    async def test_run_creates_missing_rom_user_then_updates(
        self, task, viewer_user, rom, mocker
    ):
        """A missing rom_user row is created with defaults, then updated."""
        ra_id = 12345
        mocker.patch.object(DBUsersHandler, "get_users", return_value=[viewer_user])
        mocker.patch.object(DBUsersHandler, "update_user")
        user_progression = {
            "total": 1,
            "results": [
                {
                    "rom_ra_id": ra_id,
                    "highest_award_kind": RAUserCompletionProgressKind.MASTERED,
                }
            ],
        }
        mocker.patch.object(
            RAHandler, "get_user_progression", return_value=user_progression
        )
        mock_rom = MagicMock()
        mock_rom.id = rom.id
        mock_rom.ra_id = ra_id
        mocker.patch.object(
            DBRomsHandler, "get_roms_by_ra_ids", return_value=[mock_rom]
        )
        mocker.patch.object(DBRomsHandler, "get_rom_users_by_rom_ids", return_value={})
        mock_rom_user = MagicMock(spec=RomUser)
        mock_rom_user.id = 1
        mock_rom_user.status = None
        mock_add_rom_user = mocker.patch.object(
            DBRomsHandler, "add_rom_user", return_value=mock_rom_user
        )
        mock_update_rom_user = mocker.patch.object(DBRomsHandler, "update_rom_user")

        await task.run()

        mock_add_rom_user.assert_called_once_with(rom.id, viewer_user.id)
        mock_update_rom_user.assert_called_once_with(
            mock_rom_user.id, {"status": RomUserStatus.COMPLETED_100}
        )
