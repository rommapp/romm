from unittest.mock import Mock, patch

import pytest
from fastapi import status
from rq.exceptions import NoSuchJobError

from handler.redis_handler import redis_client
from tasks.tasks import Task, TaskType


@pytest.fixture
def mock_task():
    """Create a mock task for testing"""
    task = Mock(spec=Task)
    task.title = "Test Task"
    task.description = "A test task for unit testing"
    task.task_type = TaskType.CLEANUP
    task.enabled = True
    task.manual_run = True
    task.can_run_manually = True
    task.cron_string = "0 0 * * *"
    task.timeout = 300
    task.run = Mock()
    return task


@pytest.fixture
def mock_disabled_task():
    """Create a mock disabled task for testing"""
    task = Mock(spec=Task)
    task.title = "Disabled Task"
    task.description = "A disabled task for testing"
    task.task_type = TaskType.CLEANUP
    task.enabled = False
    task.manual_run = True
    task.can_run_manually = False
    task.cron_string = None
    task.timeout = 300
    task.run = Mock()
    return task


@pytest.fixture
def mock_non_manual_task():
    """Create a mock task that cannot be run manually"""
    task = Mock(spec=Task)
    task.title = "Non-Manual Task"
    task.description = "A task that cannot be run manually"
    task.task_type = TaskType.CLEANUP
    task.enabled = True
    task.manual_run = False
    task.can_run_manually = False
    task.cron_string = "0 0 * * *"
    task.timeout = 300
    task.run = Mock()
    return task


def create_mock_job(job_id="1", status="queued"):
    """Helper function to create a mock job with proper datetime attributes"""
    from datetime import datetime

    mock_job = Mock()
    mock_job.id = job_id
    mock_job.get_status.return_value = status

    # Create mock datetime objects with isoformat methods
    mock_created_at = Mock()
    mock_created_at.isoformat = lambda: datetime.now().isoformat()
    mock_job.created_at = mock_created_at

    mock_enqueued_at = Mock()
    mock_enqueued_at.isoformat = lambda: datetime.now().isoformat()
    mock_job.enqueued_at = mock_enqueued_at

    return mock_job


class TestListTasks:
    """Test suite for the list_tasks endpoint"""

    @patch("endpoints.tasks.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", True)
    @patch("endpoints.tasks.RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 5)
    @patch(
        "endpoints.tasks.MANUAL_TASKS",
        {
            "test_manual": Mock(
                spec=Task,
                task_type=TaskType.CLEANUP,
                title="Manual Task",
                description="Manual task",
                enabled=True,
                manual_run=True,
                can_run_manually=True,
                timeout=300,
                cron_string=None,
            ),
        },
    )
    @patch(
        "endpoints.tasks.VISIBLE_SCHEDULED_TASKS",
        {
            "test_scheduled": Mock(
                spec=Task,
                task_type=TaskType.UPDATE,
                title="Scheduled Task",
                description="Scheduled task",
                enabled=True,
                manual_run=False,
                can_run_manually=False,
                timeout=300,
                cron_string="0 0 * * *",
            ),
        },
    )
    def test_list_tasks_success(self, client, access_token):
        """Test successful listing of all tasks"""
        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check structure
        assert "scheduled" in data
        assert "manual" in data
        assert "watcher" in data

        # Check scheduled tasks
        assert len(data["scheduled"]) == 1
        scheduled_task = data["scheduled"][0]
        assert scheduled_task["name"] == "test_scheduled"
        assert scheduled_task["title"] == "Scheduled Task"
        assert scheduled_task["description"] == "Scheduled task"
        assert scheduled_task["enabled"] is True
        assert scheduled_task["manual_run"] is False
        assert scheduled_task["cron_string"] == "0 0 * * *"

        # Check manual tasks
        assert len(data["manual"]) == 1
        manual_task = data["manual"][0]
        assert manual_task["name"] == "test_manual"
        assert manual_task["title"] == "Manual Task"
        assert manual_task["description"] == "Manual task"
        assert manual_task["enabled"] is True
        assert manual_task["manual_run"] is True
        assert manual_task["cron_string"] == ""

        # Check watcher task
        assert len(data["watcher"]) == 1
        watcher_task = data["watcher"][0]
        assert watcher_task["name"] == "filesystem_watcher"
        assert watcher_task["title"] == "Rescan on filesystem change"
        assert "5 minute delay" in watcher_task["description"]
        assert watcher_task["enabled"] is True
        assert watcher_task["manual_run"] is False
        assert watcher_task["cron_string"] == ""

    @patch("endpoints.tasks.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", False)
    @patch("endpoints.tasks.RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 10)
    @patch("endpoints.tasks.MANUAL_TASKS", {})
    @patch("endpoints.tasks.VISIBLE_SCHEDULED_TASKS", {})
    def test_list_tasks_empty(self, client, access_token):
        """Test listing tasks when no tasks are available"""
        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["scheduled"] == []
        assert data["manual"] == []
        assert len(data["watcher"]) == 1
        assert data["watcher"][0]["enabled"] is False
        assert "10 minute delay" in data["watcher"][0]["description"]

    def test_missing_firmware_cleanup_is_registered(self, client, access_token):
        """Unpatched registry: the Missing tab runs this task by name, so a
        missing registration is a 404 at the point of use (issue #4075)."""
        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        manual = {t["name"]: t for t in response.json()["manual"]}
        assert "cleanup_missing_firmware" in manual
        assert manual["cleanup_missing_firmware"]["manual_run"] is True
        assert manual["cleanup_missing_firmware"]["type"] == TaskType.CLEANUP.value

    def test_list_tasks_unauthorized(self, client):
        """Test that unauthorized requests are rejected"""
        response = client.get("/api/tasks")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_tasks_insufficient_scope(self, client, admin_user):
        """Test that requests without proper scope are rejected"""
        # Create a token without TASKS_RUN scope
        from datetime import timedelta

        from endpoints.auth import oauth_handler

        data = {
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": "roms:read",  # Missing TASKS_RUN scope
        }

        token = oauth_handler.create_access_token(
            data=data, expires_delta=timedelta(minutes=30)
        )

        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRunSingleTask:
    """Test suite for the run_single_task endpoint"""

    @patch("endpoints.tasks.enqueue_task", return_value=create_mock_job())
    @patch(
        "endpoints.tasks.RUNNABLE_TASKS",
        {
            "test_task": Mock(
                spec=Task,
                task_type=TaskType.CLEANUP,
                title="Test Task",
                description="Test Description",
                enabled=True,
                manual_run=True,
                can_run_manually=True,
                timeout=300,
                run=Mock(),
            ),
        },
    )
    def test_run_single_task_success(self, mock_enqueue, client, access_token):
        """Test successful running of a single task"""
        response = client.post(
            "/api/tasks/run/test_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["task_name"] == "Test Task"
        assert data["task_id"] == "1"
        assert data["status"] == "queued"
        assert "created_at" in data
        assert "enqueued_at" in data

        mock_enqueue.assert_called_once()

    @patch("endpoints.tasks.RUNNABLE_TASKS", {})
    def test_run_single_task_not_found(self, client, access_token):
        """Test running a non-existent task"""
        response = client.post(
            "/api/tasks/run/nonexistent_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch("endpoints.tasks.enqueue_task")
    @patch(
        "endpoints.tasks.RUNNABLE_TASKS",
        {
            "disabled_task": Mock(
                spec=Task,
                task_type=TaskType.CLEANUP,
                title="Disabled Task",
                description="Disabled Description",
                enabled=False,
                manual_run=True,
                can_run_manually=False,
                timeout=300,
                run=Mock(),
            ),
        },
    )
    def test_run_single_task_disabled(self, mock_enqueue, client, access_token):
        """Test running a disabled task"""
        response = client.post(
            "/api/tasks/run/disabled_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "cannot be run" in data["detail"].lower()

    @patch("endpoints.tasks.enqueue_task")
    @patch(
        "endpoints.tasks.RUNNABLE_TASKS",
        {
            "non_manual_task": Mock(
                spec=Task,
                task_type=TaskType.CLEANUP,
                title="Non-Manual Task",
                description="Non-Manual Description",
                enabled=True,
                manual_run=False,
                can_run_manually=False,
                timeout=300,
                run=Mock(),
            ),
        },
    )
    def test_run_single_task_non_manual(self, mock_enqueue, client, access_token):
        """Test running a task that cannot be run manually"""
        response = client.post(
            "/api/tasks/run/non_manual_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "cannot be run" in data["detail"].lower()

    def test_run_single_task_unauthorized(self, client):
        """Test running a task without authentication"""
        response = client.post("/api/tasks/run/test_task")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetTasksStatus:
    """Test suite for the get_tasks_status endpoint"""

    @patch("endpoints.tasks.Worker.all", return_value=[])
    @patch("endpoints.tasks.ALL_QUEUES", new=())
    @patch("endpoints.tasks.Job.fetch")
    def test_get_tasks_status_skips_expired_jobs(
        self, mock_job_fetch, mock_worker_all, client, access_token
    ):
        """Test that get_tasks_status skips jobs that have expired from Redis"""
        mock_finished_registry = Mock()
        mock_finished_registry.get_job_ids.return_value = ["expired-job-id"]
        mock_failed_registry = Mock()
        mock_failed_registry.get_job_ids.return_value = []

        mock_job_fetch.side_effect = NoSuchJobError(
            "No such job: rq:job:expired-job-id"
        )

        with patch(
            "endpoints.tasks.FinishedJobRegistry", return_value=mock_finished_registry
        ):
            with patch(
                "endpoints.tasks.FailedJobRegistry", return_value=mock_failed_registry
            ):
                response = client.get(
                    "/api/tasks/status",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestGetTaskById:
    """Test suite for the get_task_by_id endpoint"""

    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_success(self, mock_job_fetch, client, access_token):
        """Test successful retrieval of a task by job ID"""
        # Mock job object with all necessary attributes
        mock_job = Mock()
        mock_job.enqueued_at = Mock()
        mock_job.enqueued_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_job.created_at = Mock()
        mock_job.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_job.started_at = Mock()
        mock_job.started_at.isoformat.return_value = "2023-01-01T00:01:00"
        mock_job.ended_at = Mock()
        mock_job.ended_at.isoformat.return_value = "2023-01-01T00:02:00"
        mock_job.get_meta.return_value = {
            "task_name": "test_task",
            "task_type": TaskType.CLEANUP,
        }
        mock_job.func_name = "test_task"
        mock_job.get_status.return_value = "finished"
        mock_job.id = "test-job-id-123"
        mock_job.result = {"status": "completed"}

        mock_job_fetch.return_value = mock_job

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["task_name"] == "test_task"
        assert data["task_id"] == "test-job-id-123"
        assert data["status"] == "finished"
        assert data["created_at"] == "2023-01-01T00:00:00"
        assert data["enqueued_at"] == "2023-01-01T00:00:00"
        assert data["started_at"] == "2023-01-01T00:01:00"
        assert data["ended_at"] == "2023-01-01T00:02:00"

        mock_job_fetch.assert_called_once_with(
            "test-job-id-123", connection=redis_client
        )

    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_not_found(self, mock_job_fetch, client, access_token):
        """Test retrieval of a non-existent task by job ID"""
        mock_job_fetch.side_effect = Exception("Job not found")

        response = client.get(
            "/api/tasks/nonexistent-job-id",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_with_exception_info(
        self, mock_job_fetch, client, access_token
    ):
        """Test retrieval of a task that failed with exception"""
        mock_job = Mock()
        mock_job.enqueued_at = Mock()
        mock_job.enqueued_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_job.created_at = Mock()
        mock_job.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_job.started_at = Mock()
        mock_job.started_at.isoformat.return_value = "2023-01-01T00:01:00"
        mock_job.ended_at = Mock()
        mock_job.ended_at.isoformat.return_value = "2023-01-01T00:01:30"
        mock_job.get_meta.return_value = {
            "task_name": "test_task",
            "task_type": TaskType.CLEANUP,
        }
        mock_job.func_name = "test_task"
        mock_job.get_status.return_value = "failed"
        mock_job.id = "failed-job-id"
        mock_job.result = {"error": "Task failed"}

        mock_job_fetch.return_value = mock_job

        response = client.get(
            "/api/tasks/failed-job-id",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "failed"

    def test_get_task_by_id_unauthorized(self, client):
        """Test retrieval of a task without authentication"""
        response = client.get("/api/tasks/test-job-id")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTaskInfoBuilding:
    """Test suite for the _build_task_info helper function"""

    @patch("endpoints.tasks._build_task_info")
    def test_build_task_info_structure(
        self, mock_build_task_info, client, access_token
    ):
        """Test that _build_task_info creates correct TaskInfo structure"""
        # Mock the helper function to return a known structure
        mock_build_task_info.return_value = {
            "name": "test_task",
            "type": TaskType.CLEANUP,
            "title": "Test Task",
            "description": "Test Description",
            "enabled": True,
            "manual_run": True,
            "cron_string": "0 0 * * *",
        }

        with patch(
            "endpoints.tasks.MANUAL_TASKS",
            {
                "test_task": Mock(
                    spec=Task,
                    title="Test Task",
                    description="Test Description",
                    enabled=True,
                    manual_run=True,
                    can_run_manually=True,
                    timeout=300,
                    cron_string="0 0 * * *",
                ),
            },
        ):
            with patch("endpoints.tasks.VISIBLE_SCHEDULED_TASKS", {}):
                response = client.get(
                    "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
                )

                assert response.status_code == status.HTTP_200_OK
                # The mock ensures the structure is correct


class TestIntegration:
    """Integration tests for the tasks endpoints"""

    @patch("endpoints.tasks.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", True)
    @patch("endpoints.tasks.RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 5)
    @patch("endpoints.tasks.enqueue_task", return_value=create_mock_job())
    def test_full_workflow(self, mock_enqueue, client, access_token):
        """Test a complete workflow: list tasks, then run a specific task"""
        # First, list all tasks
        list_response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert list_response.status_code == status.HTTP_200_OK

        # Then run a specific task (if any exist)
        with patch(
            "endpoints.tasks.RUNNABLE_TASKS",
            {
                "workflow_task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Workflow Task",
                    description="Workflow Description",
                    enabled=True,
                    manual_run=True,
                    can_run_manually=True,
                    timeout=300,
                    run=Mock(),
                ),
            },
        ):
            run_response = client.post(
                "/api/tasks/run/workflow_task",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert run_response.status_code == status.HTTP_200_OK
            assert mock_enqueue.called

    def test_error_handling(self, client, access_token):
        """Test error handling for various scenarios"""
        # Test with invalid task name
        response = client.post(
            "/api/tasks/run/invalid_task_name_with_special_chars!@#",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRunSingleTaskArgumentHandling:
    """A request body must not be able to choose which task runs."""

    @patch("endpoints.tasks.enqueue_task", return_value=create_mock_job())
    @patch(
        "endpoints.tasks.RUNNABLE_TASKS",
        {
            "allowed_task": Mock(
                spec=Task,
                task_type=TaskType.CLEANUP,
                title="Allowed Task",
                description="Allowed",
                enabled=True,
                manual_run=True,
                can_run_manually=True,
                timeout=300,
            ),
        },
    )
    def test_body_cannot_override_the_task_name(
        self, mock_enqueue, client, access_token
    ):
        response = client.post(
            "/api/tasks/run/allowed_task",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"name": "sync_push_pull"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert mock_enqueue.call_args.args == ("allowed_task",)
        assert mock_enqueue.call_args.kwargs["task_kwargs"] == {
            "name": "sync_push_pull"
        }
