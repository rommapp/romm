from unittest.mock import MagicMock

import pytest

from handler.database.users_handler import DBUsersHandler
from handler.metadata.ra_handler import RAHandler
from tasks.scheduled.sync_retroachievements_progress import (
    SyncRetroAchievementsProgressTask,
)


@pytest.fixture
def task() -> SyncRetroAchievementsProgressTask:
    """Create a task instance for testing."""
    return SyncRetroAchievementsProgressTask()


class TestSyncRetroAchievementsProgressTask:
    """Test suite for SyncRetroAchievementsProgressTask."""

    def test_task_initialization(self, task):
        """Test task initialization with correct parameters."""
        assert (
            task.func
            == "tasks.scheduled.sync_retroachievements_progress.sync_retroachievements_progress_task.run"
        )
        assert task.description == "Updates RetroAchievements progress for all users"

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
        user_progression = MagicMock()
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
        user_progression = MagicMock()
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
