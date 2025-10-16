from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from rq.job import Job

from exceptions.task_exceptions import SchedulerException
from tasks.tasks import PeriodicTask, RemoteFilePullTask, TaskType, tasks_scheduler


class ConcretePeriodicTask(PeriodicTask):
    """Concrete implementation for testing abstract PeriodicTask"""

    async def run(self, *args, **kwargs):
        return "test_result"


class TestPeriodicTask:
    @pytest.fixture
    def task(self):
        return ConcretePeriodicTask(
            func="test.function",
            title="Test Task",
            description="test task",
            task_type=TaskType.GENERIC,
            enabled=True,
            cron_string="0 0 * * *",
        )

    @pytest.fixture
    def disabled_task(self):
        return ConcretePeriodicTask(
            func="test.disabled.function",
            title="Disabled Task",
            description="disabled task",
            task_type=TaskType.GENERIC,
            enabled=False,
            cron_string="0 0 * * *",
        )

    def test_init(self, task):
        """Test task initialization"""
        assert task.func == "test.function"
        assert task.title == "Test Task"
        assert task.description == "test task"
        assert task.enabled is True
        assert task.cron_string == "0 0 * * *"

    @patch.object(tasks_scheduler, "get_jobs")
    def test_get_existing_job_found(self, mock_get_jobs, task):
        """Test finding an existing job"""
        mock_job = MagicMock(spec=Job)
        mock_job.func_name = "test.function"
        mock_get_jobs.return_value = [mock_job]

        result = task._get_existing_job()
        assert result == mock_job

    @patch.object(tasks_scheduler, "get_jobs")
    def test_get_existing_job_not_found(self, mock_get_jobs, task):
        """Test when no existing job is found"""
        mock_job = MagicMock(spec=Job)
        mock_job.func_name = "other.function"
        mock_get_jobs.return_value = [mock_job]

        result = task._get_existing_job()
        assert result is None

    @patch.object(tasks_scheduler, "get_jobs")
    def test_get_existing_job_empty_list(self, mock_get_jobs, task):
        """Test when no jobs exist"""
        mock_get_jobs.return_value = []

        result = task._get_existing_job()
        assert result is None

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch.object(ConcretePeriodicTask, "schedule")
    @patch.object(ConcretePeriodicTask, "unschedule")
    def test_init_enabled_no_existing_job(
        self, mock_unschedule, mock_schedule, mock_get_existing_job, task
    ):
        """Test init when task is enabled and no existing job"""
        mock_job = MagicMock(spec=Job)
        mock_get_existing_job.return_value = None
        mock_schedule.return_value = mock_job

        result = task.init()

        mock_schedule.assert_called_once()
        mock_unschedule.assert_not_called()
        assert result == mock_job

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch.object(ConcretePeriodicTask, "schedule")
    @patch.object(ConcretePeriodicTask, "unschedule")
    def test_init_disabled_with_existing_job(
        self, mock_unschedule, mock_schedule, mock_get_existing_job, disabled_task
    ):
        """Test init when task is disabled but has existing job"""
        mock_job = MagicMock(spec=Job)
        mock_get_existing_job.return_value = mock_job
        mock_unschedule.return_value = None

        result = disabled_task.init()

        mock_unschedule.assert_called_once()
        mock_schedule.assert_not_called()
        assert result is None

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch.object(ConcretePeriodicTask, "schedule")
    @patch.object(ConcretePeriodicTask, "unschedule")
    def test_init_enabled_with_existing_job(
        self, mock_unschedule, mock_schedule, mock_get_existing_job, task
    ):
        """Test init when task is enabled and job already exists"""
        mock_job = MagicMock(spec=Job)
        mock_get_existing_job.return_value = mock_job

        result = task.init()

        mock_schedule.assert_not_called()
        mock_unschedule.assert_not_called()
        assert result is None  # Should do nothing

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch.object(tasks_scheduler, "cron")
    def test_schedule_success(self, mock_cron, mock_get_existing_job, task):
        """Test successful scheduling"""
        mock_job = MagicMock(spec=Job)
        mock_get_existing_job.return_value = None
        mock_cron.return_value = mock_job

        result = task.schedule()

        mock_cron.assert_called_once_with(
            "0 0 * * *",
            func="test.function",
            repeat=None,
            timeout=5 * 60,
            meta={"task_name": "Test Task", "task_type": "generic"},
        )
        assert result == mock_job

    def test_schedule_not_enabled(self, disabled_task):
        """Test scheduling when task is not enabled"""
        with pytest.raises(
            SchedulerException, match="Scheduled disabled task is not enabled."
        ):
            disabled_task.schedule()

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch("tasks.tasks.log")
    def test_schedule_already_scheduled(self, mock_log, mock_get_existing_job, task):
        """Test scheduling when job already exists"""
        mock_job = MagicMock()
        mock_get_existing_job.return_value = mock_job

        result = task.schedule()

        mock_log.info.assert_called_once_with("Test task is already scheduled.")
        assert result is None

    def test_schedule_no_cron_string(self):
        """Test scheduling with no cron string"""
        task = ConcretePeriodicTask(
            func="test.function",
            title="Test Task",
            task_type=TaskType.GENERIC,
            description="test task",
            enabled=True,
            cron_string=None,
        )

        with patch.object(task, "_get_existing_job", return_value=None):
            result = task.schedule()
            assert result is None

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch.object(tasks_scheduler, "cancel")
    @patch("tasks.tasks.log")
    def test_unschedule_success(
        self, mock_log, mock_cancel, mock_get_existing_job, task
    ):
        """Test successful unscheduling"""
        mock_job = MagicMock(spec=Job)
        mock_get_existing_job.return_value = mock_job

        task.unschedule()

        mock_cancel.assert_called_once_with(mock_job)
        mock_log.info.assert_called_once_with("Test task unscheduled.")

    @patch.object(ConcretePeriodicTask, "_get_existing_job")
    @patch("tasks.tasks.log")
    def test_unschedule_not_scheduled(self, mock_log, mock_get_existing_job, task):
        """Test unscheduling when no job exists"""
        mock_get_existing_job.return_value = None

        task.unschedule()

        mock_log.info.assert_called_once_with("Test task is not scheduled.")

    async def test_run_abstract_method(self, task):
        """Test that run method works in concrete implementation"""
        result = await task.run()
        assert result == "test_result"


class TestRemoteFilePullTask:
    @pytest.fixture
    def task(self):
        return RemoteFilePullTask(
            func="test.remote.function",
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
            func="test.remote.disabled.function",
            title="Disabled Remote Task",
            task_type=TaskType.UPDATE,
            description="disabled remote task",
            enabled=False,
            url="https://example.com/data.json",
        )

    def test_init(self, task):
        """Test RemoteFilePullTask initialization"""
        assert task.func == "test.remote.function"
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

    @patch.object(RemoteFilePullTask, "unschedule")
    @patch("tasks.tasks.log")
    async def test_run_disabled_not_forced(
        self, mock_log, mock_unschedule, disabled_task
    ):
        """Test run when task is disabled and not forced"""
        result = await disabled_task.run(force=False)

        mock_log.info.assert_called_once_with(
            "Scheduled disabled remote task not enabled, unscheduling..."
        )
        mock_unschedule.assert_called_once()
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
