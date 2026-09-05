from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from exceptions.task_exceptions import TaskNotFoundException
from tasks.tasks import PeriodicTask, RemoteFilePullTask, TaskType, run_task_by_name


class ConcretePeriodicTask(PeriodicTask):
    """Concrete implementation for testing abstract PeriodicTask"""

    async def run(self, *args, **kwargs):
        return "test_result"


class TestPeriodicTask:
    @pytest.fixture
    def task(self):
        return ConcretePeriodicTask(
            title="Test Task",
            description="test task",
            task_type=TaskType.GENERIC,
            enabled=True,
            cron_string="0 0 * * *",
        )

    @pytest.fixture
    def disabled_task(self):
        return ConcretePeriodicTask(
            title="Disabled Task",
            description="disabled task",
            task_type=TaskType.GENERIC,
            enabled=False,
            cron_string="0 0 * * *",
        )

    def test_init(self, task):
        """Test task initialization"""
        assert task.title == "Test Task"
        assert task.description == "test task"
        assert task.enabled is True
        assert task.cron_string == "0 0 * * *"

    async def test_run_abstract_method(self, task):
        """Test that run method works in concrete implementation"""
        result = await task.run()
        assert result == "test_result"


class TestRemoteFilePullTask:
    @pytest.fixture
    def task(self):
        return RemoteFilePullTask(
            title="Remote Test Task",
            task_type=TaskType.UPDATE,
            description="remote test task",
            enabled=True,
            cron_string="0 0 * * *",
            url="https://example.com/data.json",
        )

    @pytest.fixture
    def disabled_task(self):
        return RemoteFilePullTask(
            title="Disabled Remote Task",
            task_type=TaskType.UPDATE,
            description="disabled remote task",
            enabled=False,
            url="https://example.com/data.json",
        )

    def test_init(self, task):
        """Test RemoteFilePullTask initialization"""
        assert task.task_type == TaskType.UPDATE
        assert task.description == "remote test task"
        assert task.enabled is True
        assert task.url == "https://example.com/data.json"

    @patch("tasks.tasks.ctx_httpx_client")
    @patch("tasks.tasks.log")
    async def test_run_success(self, mock_log, mock_ctx_httpx_client, task):
        """Test successful remote file pull"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = b"test content"
        mock_client.get.return_value = mock_response
        mock_ctx_httpx_client.get.return_value = mock_client

        result = await task.run(force=True)

        mock_client.get.assert_called_once_with(
            "https://example.com/data.json", timeout=120
        )
        mock_response.raise_for_status.assert_called_once()
        mock_log.info.assert_called_once_with("Scheduled remote test task started...")
        assert result == b"test content"

    @patch("tasks.tasks.ctx_httpx_client")
    @patch("tasks.tasks.log")
    async def test_run_http_error(self, mock_log, mock_ctx_httpx_client, task):
        """Test handling of HTTP errors"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")
        mock_ctx_httpx_client.get.return_value = mock_client

        result = await task.run(force=True)

        mock_log.error.assert_called()
        assert result is None

    @patch("tasks.tasks.ctx_httpx_client")
    @patch("tasks.tasks.log")
    async def test_run_response_error(self, mock_log, mock_ctx_httpx_client, task):
        """Test handling of response status errors"""
        mock_client = AsyncMock()
        mock_response = MagicMock()

        # Create a proper HTTPStatusError
        http_error = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        mock_response.raise_for_status.side_effect = http_error
        mock_client.get.return_value = mock_response
        mock_ctx_httpx_client.get.return_value = mock_client

        result = await task.run(force=True)

        # Verify the specific error logging calls
        mock_log.error.assert_any_call(
            "Scheduled remote test task failed", exc_info=True
        )
        mock_log.error.assert_any_call(http_error)
        assert result is None

    @patch("tasks.tasks.log")
    async def test_run_disabled_not_forced(self, mock_log, disabled_task):
        """Test run when task is disabled and not forced"""
        result = await disabled_task.run(force=False)

        mock_log.info.assert_called_once_with(
            "Scheduled disabled remote task not enabled, skipping..."
        )
        assert result is None

    @patch("tasks.tasks.ctx_httpx_client")
    async def test_run_disabled_but_forced(self, mock_ctx_httpx_client, disabled_task):
        """Test run when task is disabled but forced"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = b"forced content"
        mock_client.get.return_value = mock_response
        mock_ctx_httpx_client.get.return_value = mock_client

        result = await disabled_task.run(force=True)

        assert result == b"forced content"


class TestRunTaskByName:
    """Jobs carry a task's name, so the runner has to resolve it."""

    async def test_runs_the_registered_task(self, mocker):
        task = MagicMock()
        task.run = AsyncMock(return_value="ran")
        mocker.patch("tasks.registry.get_task", return_value=task)

        assert await run_task_by_name("some_task") == "ran"
        task.run.assert_awaited_once_with()

    async def test_forwards_keyword_arguments(self, mocker):
        task = MagicMock()
        task.run = AsyncMock(return_value=None)
        mocker.patch("tasks.registry.get_task", return_value=task)

        await run_task_by_name("some_task", {"force": True})

        task.run.assert_awaited_once_with(force=True)

    async def test_forwarded_arguments_cannot_name_another_task(self, mocker):
        # The arguments reach the task rather than this function's own name, so a
        # request body cannot redirect the run to a task it was not allowed.
        task = MagicMock()
        task.run = AsyncMock(return_value=None)
        get_task = mocker.patch("tasks.registry.get_task", return_value=task)

        await run_task_by_name("allowed_task", {"name": "hidden_task"})

        get_task.assert_called_once_with("allowed_task")
        task.run.assert_awaited_once_with(name="hidden_task")

    async def test_raises_for_a_name_that_is_not_registered(self, mocker):
        mocker.patch("tasks.registry.get_task", return_value=None)

        with pytest.raises(TaskNotFoundException, match="some_task"):
            await run_task_by_name("some_task")
