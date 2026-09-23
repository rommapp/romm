from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from rq.exceptions import AbandonedJobError
from rq.timeouts import JobTimeoutException

from exceptions.task_exceptions import TaskNotFoundException
from models.notification import NotificationKind, NotificationLevel
from tasks.tasks import (
    PeriodicTask,
    RemoteFilePullTask,
    TaskType,
    report_task_failure,
    run_task_by_name,
)


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

        result = await task.run()

        mock_client.get.assert_called_once_with(
            "https://example.com/data.json", timeout=120
        )
        mock_response.raise_for_status.assert_called_once()
        mock_log.info.assert_called_once_with("Scheduled remote test task started...")
        assert result == b"test content"

    @patch("tasks.tasks.ctx_httpx_client")
    async def test_run_http_error(self, mock_ctx_httpx_client, task):
        """A download that never lands fails the run, saying why."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_ctx_httpx_client.get.return_value = mock_client

        with pytest.raises(
            RuntimeError,
            match="Could not reach https://example.com/data.json: Connection failed",
        ):
            await task.run()

    @patch("tasks.tasks.ctx_httpx_client")
    async def test_run_response_error(self, mock_ctx_httpx_client, task):
        """A refused download fails the run with the status."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        mock_client.get.return_value = mock_response
        mock_ctx_httpx_client.get.return_value = mock_client

        with pytest.raises(
            RuntimeError, match="https://example.com/data.json answered 404"
        ):
            await task.run()

    @patch("tasks.tasks.ctx_httpx_client")
    async def test_run_disabled_still_pulls(self, mock_ctx_httpx_client, disabled_task):
        """A caller that got this far wants the pull, whatever the setting says."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = b"remote content"
        mock_client.get.return_value = mock_response
        mock_ctx_httpx_client.get.return_value = mock_client

        result = await disabled_task.run()

        assert result == b"remote content"


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


@pytest.fixture
def notify(mocker):
    return mocker.patch("handler.notification_handler.notify", AsyncMock())


@pytest.fixture
def notify_admins(mocker):
    return mocker.patch("handler.notification_handler.notify_admins", AsyncMock())


def _task(mocker, task_type=TaskType.CLEANUP, **run_kwargs):
    task = MagicMock(title="Cleanup Missing ROMs", task_type=task_type, timeout=300)
    task.run = AsyncMock(**run_kwargs)
    mocker.patch("tasks.registry.get_task", return_value=task)
    return task


class TestRunTaskByNameNotifications:
    """A run tells whoever ran it that it finished, and leaves failures to RQ."""

    async def test_tells_the_runner_it_finished(self, mocker, notify, notify_admins):
        _task(mocker, return_value=None)

        await run_task_by_name("cleanup_missing_roms", run_by_user_id=4)

        user_id, kind, level, data = notify.await_args.args
        assert (user_id, kind, level) == (
            4,
            NotificationKind.TASK_COMPLETED,
            NotificationLevel.SUCCESS,
        )
        assert data == {"task": "cleanup_missing_roms", "title": "Cleanup Missing ROMs"}
        notify_admins.assert_not_awaited()

    async def test_a_scheduled_success_stays_quiet(self, mocker, notify, notify_admins):
        _task(mocker, return_value=None)

        await run_task_by_name("cleanup_missing_roms")

        notify.assert_not_awaited()
        notify_admins.assert_not_awaited()

    async def test_a_failure_is_raised_to_rq_unreported(
        self, mocker, notify, notify_admins
    ):
        _task(mocker, side_effect=RuntimeError("disk full"))

        with pytest.raises(RuntimeError):
            await run_task_by_name("cleanup_missing_roms", run_by_user_id=4)

        notify.assert_not_awaited()
        notify_admins.assert_not_awaited()


def _job(name="cleanup_missing_roms", run_by_user_id=None, **overrides):
    fields = {
        "id": "job-1",
        "func_name": "tasks.tasks.run_task_by_name",
        "kwargs": {"name": name, "task_kwargs": {}, "run_by_user_id": run_by_user_id},
    }
    return MagicMock(**{**fields, **overrides})


class TestReportTaskFailure:
    """The worker's exception handler reports every way a task can fail."""

    def test_tells_the_runner_why_it_failed(self, mocker, notify, notify_admins):
        _task(mocker)

        report_task_failure(
            _job(run_by_user_id=4), RuntimeError, RuntimeError("disk full"), None
        )

        user_id, kind, level, data = notify.await_args.args
        assert (user_id, kind, level) == (
            4,
            NotificationKind.TASK_FAILED,
            NotificationLevel.ERROR,
        )
        assert data == {
            "task": "cleanup_missing_roms",
            "title": "Cleanup Missing ROMs",
            "error": "disk full",
        }
        notify_admins.assert_not_awaited()

    def test_a_scheduled_failure_goes_to_the_admins(
        self, mocker, notify, notify_admins
    ):
        _task(mocker)

        report_task_failure(_job(), RuntimeError, RuntimeError("disk full"), None)

        kind, level, data = notify_admins.await_args.args
        assert (kind, level) == (NotificationKind.TASK_FAILED, NotificationLevel.ERROR)
        assert data["error"] == "disk full"
        notify.assert_not_awaited()

    @pytest.mark.parametrize(
        "exc_type,reason",
        [
            (JobTimeoutException, "It ran past its 300s timeout"),
            (AbandonedJobError, "The worker running it stopped unexpectedly"),
        ],
    )
    def test_words_a_death_the_task_never_saw(
        self, mocker, notify, notify_admins, exc_type, reason
    ):
        _task(mocker)

        report_task_failure(_job(run_by_user_id=4), exc_type, exc_type(), None)

        assert notify.await_args.args[3]["error"] == reason

    def test_a_scan_is_left_to_report_itself(self, mocker, notify, notify_admins):
        _task(mocker, task_type=TaskType.SCAN)

        report_task_failure(
            _job("scan_library", 4), RuntimeError, RuntimeError("boom"), None
        )

        notify.assert_not_awaited()
        notify_admins.assert_not_awaited()

    def test_ignores_a_job_that_is_not_a_task(self, mocker, notify, notify_admins):
        get_task = mocker.patch("tasks.registry.get_task")

        report_task_failure(
            _job(func_name="endpoints.sockets.scan.scan_platforms"),
            RuntimeError,
            RuntimeError("boom"),
            None,
        )

        get_task.assert_not_called()
        notify.assert_not_awaited()

    def test_never_raises_into_the_worker(self, mocker):
        _task(mocker)
        mocker.patch(
            "handler.notification_handler.notify_admins",
            AsyncMock(side_effect=RuntimeError("redis gone")),
        )

        report_task_failure(_job(), RuntimeError, RuntimeError("boom"), None)
