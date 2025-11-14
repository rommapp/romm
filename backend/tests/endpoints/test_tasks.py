from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from tasks.tasks import Task, TaskType


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_task():
    """Create a mock task for testing"""
    task = Mock(spec=Task)
    task.title = "Test Task"
    task.description = "A test task for unit testing"
    task.task_type = TaskType.CLEANUP
    task.enabled = True
    task.manual_run = True
    task.cron_string = "0 0 * * *"
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
    task.cron_string = None
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
    task.cron_string = "0 0 * * *"
    task.run = Mock()
    return task


def create_mock_job(job_id="1", status="queued"):
    """Helper function to create a mock job with proper datetime attributes"""
    from datetime import datetime

    mock_job = Mock()
    mock_job.get_id.return_value = job_id
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
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "test_manual",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Manual Task",
                    description="Manual task",
                    enabled=True,
                    manual_run=True,
                    cron_string=None,
                ),
            }
        ],
    )
    @patch(
        "endpoints.tasks.scheduled_tasks",
        [
            {
                "name": "test_scheduled",
                "type": TaskType.UPDATE,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.UPDATE,
                    title="Scheduled Task",
                    description="Scheduled task",
                    enabled=True,
                    manual_run=False,
                    cron_string="0 0 * * *",
                ),
            }
        ],
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
    @patch("endpoints.tasks.manual_tasks", [])
    @patch("endpoints.tasks.scheduled_tasks", [])
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

    def test_list_tasks_unauthorized(self, client):
        """Test that unauthorized requests are rejected"""
        response = client.get("/api/tasks")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_tasks_insufficient_scope(self, client, admin_user):
        """Test that requests without proper scope are rejected"""
        # Create a token without TASKS_RUN scope
        from datetime import timedelta

        from endpoints.auth import oauth_handler

        data = {
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": "roms:read",  # Missing TASKS_RUN scope
            "type": "access",
        }

        token = oauth_handler.create_oauth_token(
            data=data, expires_delta=timedelta(minutes=30)
        )

        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRunAllTasks:
    """Test suite for the run_all_tasks endpoint"""

    @patch("endpoints.tasks.low_prio_queue.enqueue", return_value=create_mock_job())
    @patch(
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "task1",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Test Task",
                    description="Test Description",
                    enabled=True,
                    manual_run=True,
                    run=Mock(),
                ),
            },
            {
                "name": "task2",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Test Task",
                    description="Test Description",
                    enabled=True,
                    manual_run=True,
                    run=Mock(),
                ),
            },
        ],
    )
    @patch(
        "endpoints.tasks.scheduled_tasks",
        [
            {
                "name": "task3",
                "type": TaskType.UPDATE,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.UPDATE,
                    title="Update Task",
                    description="Update Description",
                    enabled=True,
                    manual_run=True,
                    run=Mock(),
                ),
            },
            {
                "name": "task4",
                "type": TaskType.UPDATE,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.UPDATE,
                    title="Disabled Update Task",
                    description="Disabled Update Description",
                    enabled=False,
                    manual_run=True,
                    run=Mock(),
                ),  # Disabled
            },
        ],
    )
    def test_run_all_tasks_success(self, mock_queue, client, access_token):
        """Test successful running of all runnable tasks"""
        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert data[0]["task_name"] == "task1"
        assert data[1]["task_name"] == "task2"
        assert data[2]["task_name"] == "task3"

    @patch("endpoints.tasks.low_prio_queue")
    @patch("endpoints.tasks.manual_tasks", [])
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_all_tasks_no_runnable_tasks(self, mock_queue, client, access_token):
        """Test running all tasks when no tasks are runnable"""
        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"] == "No runnable tasks available to run"

        # Verify that enqueue was not called
        mock_queue.assert_not_called()

    @patch("endpoints.tasks.low_prio_queue")
    @patch(
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "task1",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task, enabled=True, manual_run=False, run=Mock()
                ),  # Not manual
            },
            {
                "name": "task2",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task, enabled=False, manual_run=True, run=Mock()
                ),  # Disabled
            },
        ],
    )
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_all_tasks_mixed_conditions(self, mock_queue, client, access_token):
        """Test running all tasks with mixed enabled/disabled and manual/non-manual tasks"""
        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"] == "No runnable tasks available to run"

        # Verify that enqueue was not called since no tasks are both enabled and manual
        mock_queue.enqueue.assert_not_called()

    def test_run_all_tasks_unauthorized(self, client):
        """Test that unauthorized requests are rejected"""
        response = client.post("/api/tasks/run")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRunSingleTask:
    """Test suite for the run_single_task endpoint"""

    @patch("endpoints.tasks.low_prio_queue.enqueue", return_value=create_mock_job())
    @patch(
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "test_task",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Test Task",
                    description="Test Description",
                    enabled=True,
                    manual_run=True,
                    run=Mock(),
                ),
            }
        ],
    )
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_single_task_success(self, mock_queue, client, access_token):
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

        mock_queue.assert_called_once()

    @patch("endpoints.tasks.manual_tasks", [])
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_single_task_not_found(self, client, access_token):
        """Test running a non-existent task"""
        response = client.post(
            "/api/tasks/run/nonexistent_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch("endpoints.tasks.low_prio_queue")
    @patch(
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "disabled_task",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Disabled Task",
                    description="Disabled Description",
                    enabled=False,
                    manual_run=True,
                    run=Mock(),
                ),
            }
        ],
    )
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_single_task_disabled(self, mock_queue, client, access_token):
        """Test running a disabled task"""
        response = client.post(
            "/api/tasks/run/disabled_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "cannot be run" in data["detail"].lower()

    @patch("endpoints.tasks.low_prio_queue")
    @patch(
        "endpoints.tasks.manual_tasks",
        [
            {
                "name": "non_manual_task",
                "type": TaskType.CLEANUP,
                "task": Mock(
                    spec=Task,
                    task_type=TaskType.CLEANUP,
                    title="Non-Manual Task",
                    description="Non-Manual Description",
                    enabled=True,
                    manual_run=False,
                    run=Mock(),
                ),
            }
        ],
    )
    @patch("endpoints.tasks.scheduled_tasks", [])
    def test_run_single_task_non_manual(self, mock_queue, client, access_token):
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
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetTaskById:
    """Test suite for the get_task_by_id endpoint"""

    @patch("endpoints.tasks.low_prio_queue")
    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_success(
        self, mock_job_fetch, mock_queue, client, access_token
    ):
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
        mock_job.get_id.return_value = "test-job-id-123"
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
            "test-job-id-123", connection=mock_queue.connection
        )

    @patch("endpoints.tasks.low_prio_queue")
    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_not_found(
        self, mock_job_fetch, mock_queue, client, access_token
    ):
        """Test retrieval of a non-existent task by job ID"""
        mock_job_fetch.side_effect = Exception("Job not found")

        response = client.get(
            "/api/tasks/nonexistent-job-id",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch("endpoints.tasks.low_prio_queue")
    @patch("endpoints.tasks.Job.fetch")
    def test_get_task_by_id_with_exception_info(
        self, mock_job_fetch, mock_queue, client, access_token
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
        mock_job.get_id.return_value = "failed-job-id"
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
        assert response.status_code == status.HTTP_403_FORBIDDEN


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
            "endpoints.tasks.manual_tasks",
            [
                {
                    "name": "test_task",
                    "type": TaskType.CLEANUP,
                    "task": Mock(
                        spec=Task,
                        title="Test Task",
                        description="Test Description",
                        enabled=True,
                        manual_run=True,
                        cron_string="0 0 * * *",
                    ),
                }
            ],
        ):
            with patch("endpoints.tasks.scheduled_tasks", []):
                response = client.get(
                    "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
                )

                assert response.status_code == status.HTTP_200_OK
                # The mock ensures the structure is correct


class TestIntegration:
    """Integration tests for the tasks endpoints"""

    @patch("endpoints.tasks.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", True)
    @patch("endpoints.tasks.RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 5)
    @patch(
        "endpoints.tasks.low_prio_queue.enqueue",
        return_value=create_mock_job(),
    )
    def test_full_workflow(self, mock_queue, client, access_token):
        """Test a complete workflow: list tasks, then run a specific task"""
        # First, list all tasks
        list_response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert list_response.status_code == status.HTTP_200_OK

        # Then run a specific task (if any exist)
        with patch(
            "endpoints.tasks.manual_tasks",
            [
                {
                    "name": "workflow_task",
                    "type": TaskType.CLEANUP,
                    "task": Mock(
                        spec=Task,
                        task_type=TaskType.CLEANUP,
                        title="Workflow Task",
                        description="Workflow Description",
                        enabled=True,
                        manual_run=True,
                        run=Mock(),
                    ),
                }
            ],
        ):
            with patch("endpoints.tasks.scheduled_tasks", []):
                run_response = client.post(
                    "/api/tasks/run/workflow_task",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert run_response.status_code == status.HTTP_200_OK
                assert mock_queue.called

    def test_error_handling(self, client, access_token):
        """Test error handling for various scenarios"""
        # Test with invalid task name
        response = client.post(
            "/api/tasks/run/invalid_task_name_with_special_chars!@#",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
