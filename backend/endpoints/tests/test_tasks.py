from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


class MockTask:
    """Mock task class for testing"""

    def __init__(
        self,
        name="test_task",
        manual_run=True,
        title="Test Task",
        description="Test task description",
        enabled=True,
        cron_string="0 0 * * *",
    ):
        self.manual_run = manual_run
        self.title = title
        self.description = description
        self.enabled = enabled
        self.cron_string = cron_string
        self.run = AsyncMock()


class TestTasksEndpoints:
    """Test class for tasks endpoints"""

    @patch("endpoints.tasks._get_available_tasks")
    def test_list_tasks_success(self, mock_get_tasks, client, access_token):
        """Test successful task listing"""
        # Mock the available tasks
        mock_get_tasks.return_value = {
            "test_manual_task": MockTask(name="test_manual_task", manual_run=True),
            "test_scheduled_task": MockTask(
                name="test_scheduled_task", manual_run=False
            ),
        }

        # Mock the filesystem structure
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = lambda: True  # All task files exist

            response = client.get(
                "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
            )

        assert response.status_code == 200
        data = response.json()

        # Should have manual, scheduled, and watcher sections
        assert "manual" in data
        assert "scheduled" in data
        assert "watcher" in data

        # Check watcher task is always present
        assert len(data["watcher"]) == 1
        assert data["watcher"][0]["name"] == "filesystem_watcher"
        assert data["watcher"][0]["title"] == "Rescan on filesystem change"

    @patch("endpoints.tasks._get_available_tasks")
    def test_list_tasks_empty(self, mock_get_tasks, client, access_token):
        """Test task listing when no tasks are available"""
        mock_get_tasks.return_value = {}

        response = client.get(
            "/api/tasks", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should still have watcher task
        assert "watcher" in data
        assert len(data["watcher"]) == 1

    def test_list_tasks_unauthorized(self, client):
        """Test task listing without authentication"""
        response = client.get("/api/tasks")
        assert response.status_code == 403

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_all_tasks_success(self, mock_get_tasks, client, access_token):
        """Test successful execution of all runnable tasks"""
        mock_task1 = MockTask(name="task1", manual_run=True)
        mock_task2 = MockTask(name="task2", manual_run=True)
        mock_task3 = MockTask(name="task3", manual_run=False)  # Not runnable

        mock_get_tasks.return_value = {
            "task1": mock_task1,
            "task2": mock_task2,
            "task3": mock_task3,
        }

        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "2 triggerable tasks ran successfully" in data["msg"]
        assert "task1, task2" in data["msg"]

        # Verify only runnable tasks were called
        mock_task1.run.assert_called_once()
        mock_task2.run.assert_called_once()
        mock_task3.run.assert_not_called()

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_all_tasks_some_fail(self, mock_get_tasks, client, access_token):
        """Test when some tasks fail during execution"""
        mock_task1 = MockTask(name="task1", manual_run=True)
        mock_task2 = MockTask(name="task2", manual_run=True)
        mock_task2.run.side_effect = Exception("Task 2 failed")

        mock_get_tasks.return_value = {
            "task1": mock_task1,
            "task2": mock_task2,
        }

        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "Some tasks failed" in data["msg"]
        assert "task1" in data["msg"]  # Successful
        assert "task2: Task 2 failed" in data["msg"]  # Failed

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_all_tasks_no_tasks(self, mock_get_tasks, client, access_token):
        """Test when no tasks are available"""
        mock_get_tasks.return_value = {}

        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["msg"] == "No tasks available to run"

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_all_tasks_no_runnable_tasks(
        self, mock_get_tasks, client, access_token
    ):
        """Test when no tasks are manually runnable"""
        mock_task = MockTask(name="task1", manual_run=False)
        mock_get_tasks.return_value = {"task1": mock_task}

        response = client.post(
            "/api/tasks/run", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["msg"] == "No runnable tasks available to run"

    def test_run_all_tasks_unauthorized(self, client):
        """Test running all tasks without authentication"""
        response = client.post("/api/tasks/run")
        assert response.status_code == 403

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_single_task_success(self, mock_get_tasks, client, access_token):
        """Test successful execution of a single task"""
        mock_task = MockTask(name="test_task", manual_run=True)
        mock_get_tasks.return_value = {"test_task": mock_task}

        response = client.post(
            "/api/tasks/run/test_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["msg"] == "Task 'test_task' ran successfully!"
        mock_task.run.assert_called_once()

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_single_task_not_found(self, mock_get_tasks, client, access_token):
        """Test running a task that doesn't exist"""
        mock_get_tasks.return_value = {"other_task": MockTask()}

        response = client.post(
            "/api/tasks/run/nonexistent_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "Task 'nonexistent_task' not found" in data["detail"]
        assert "other_task" in data["detail"]

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_single_task_not_runnable(self, mock_get_tasks, client, access_token):
        """Test running a task that is not manually runnable"""
        mock_task = MockTask(name="scheduled_task", manual_run=False)
        mock_get_tasks.return_value = {"scheduled_task": mock_task}

        response = client.post(
            "/api/tasks/run/scheduled_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Task 'scheduled_task' is not triggerable manually" in data["detail"]

    @patch("endpoints.tasks._get_available_tasks")
    def test_run_single_task_execution_fails(
        self, mock_get_tasks, client, access_token
    ):
        """Test when a single task execution fails"""
        mock_task = MockTask(name="failing_task", manual_run=True)
        mock_task.run.side_effect = Exception("Task execution failed")
        mock_get_tasks.return_value = {"failing_task": mock_task}

        response = client.post(
            "/api/tasks/run/failing_task",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "Task 'failing_task' failed: Task execution failed" in data["detail"]

    def test_run_single_task_unauthorized(self, client):
        """Test running a single task without authentication"""
        response = client.post("/api/tasks/run/test_task")
        assert response.status_code == 403


class TestGetAvailableTasks:
    """Test class for the _get_available_tasks function"""

    @patch("importlib.import_module")
    @patch("pathlib.Path.glob")
    def test_get_available_tasks_success(self, mock_glob, mock_import):
        """Test successful task discovery"""
        from endpoints.tasks import _get_available_tasks

        # Mock file discovery for both scheduled and manual task types
        mock_file1 = MagicMock()
        mock_file1.stem = "test_task"
        mock_file2 = MagicMock()
        mock_file2.stem = "another_task"
        mock_glob.return_value = [mock_file1, mock_file2]

        # Mock modules
        mock_module1 = MagicMock()
        mock_task_instance = MockTask()
        mock_module1.test_task_task = mock_task_instance

        mock_module2 = MagicMock()
        mock_task_instance2 = MockTask()
        mock_module2.another_task_task = mock_task_instance2

        # Mock dir() calls to return the expected attributes
        with patch("builtins.dir") as mock_dir:
            mock_dir.side_effect = [
                ["test_task_task", "other_var"],  # For mock_module1
                ["another_task_task"],  # For mock_module2
            ] * 2  # Multiply by 2 because it runs for both 'scheduled' and 'manual' task types

            mock_import.side_effect = [mock_module1, mock_module2] * 2

            tasks = _get_available_tasks()

        # Should find 2 tasks (one per module)
        assert len(tasks) == 2
        assert "test" in tasks  # Key is task name without _task suffix
        assert "another" in tasks  # Key is task name without _task suffix
        assert tasks["test"] == mock_task_instance
        assert tasks["another"] == mock_task_instance2

    @patch("importlib.import_module")
    @patch("pathlib.Path.glob")
    def test_get_available_tasks_import_error(self, mock_glob, mock_import):
        """Test task discovery with import errors"""
        from endpoints.tasks import _get_available_tasks

        # Mock file discovery
        mock_file = MagicMock()
        mock_file.stem = "broken_task"
        mock_glob.return_value = [mock_file]

        # Mock import error for both task types
        mock_import.side_effect = [ImportError("Module not found")] * 2

        tasks = _get_available_tasks()

        # Should return empty dict when imports fail
        assert len(tasks) == 0

    @patch("importlib.import_module")
    @patch("pathlib.Path.glob")
    def test_get_available_tasks_no_valid_tasks(self, mock_glob, mock_import):
        """Test task discovery when modules don't have valid tasks"""
        from endpoints.tasks import _get_available_tasks

        # Mock file discovery
        mock_file = MagicMock()
        mock_file.stem = "invalid_task"
        mock_glob.return_value = [mock_file]

        # Mock module without valid task attributes
        mock_module = MagicMock()

        with patch("builtins.dir") as mock_dir:
            mock_dir.return_value = ["some_var", "another_var"]  # No _task suffix
            mock_import.side_effect = [mock_module] * 2  # For both task types

            tasks = _get_available_tasks()

        # Should return empty dict
        assert len(tasks) == 0

    @patch("importlib.import_module")
    @patch("pathlib.Path.glob")
    def test_get_available_tasks_invalid_task_object(self, mock_glob, mock_import):
        """Test task discovery when task object doesn't have run method"""
        from endpoints.tasks import _get_available_tasks

        # Mock file discovery
        mock_file = MagicMock()
        mock_file.stem = "invalid_task"
        mock_glob.return_value = [mock_file]

        # Mock module with invalid task object
        mock_module = MagicMock()
        invalid_task = MagicMock()
        del invalid_task.run  # Remove run method
        mock_module.invalid_task_task = invalid_task

        with patch("builtins.dir") as mock_dir:
            mock_dir.return_value = ["invalid_task_task"]
            mock_import.side_effect = [mock_module] * 2  # For both task types

            tasks = _get_available_tasks()

        # Should return empty dict
        assert len(tasks) == 0

    @patch("importlib.import_module")
    @patch("pathlib.Path.glob")
    def test_get_available_tasks_non_callable_run(self, mock_glob, mock_import):
        """Test task discovery when run attribute is not callable"""
        from endpoints.tasks import _get_available_tasks

        # Mock file discovery
        mock_file = MagicMock()
        mock_file.stem = "invalid_task"
        mock_glob.return_value = [mock_file]

        # Mock module with non-callable run attribute
        mock_module = MagicMock()
        invalid_task = MagicMock()
        invalid_task.run = "not callable"  # Not callable
        mock_module.invalid_task_task = invalid_task

        with patch("builtins.dir") as mock_dir:
            mock_dir.return_value = ["invalid_task_task"]
            mock_import.side_effect = [mock_module] * 2  # For both task types

            tasks = _get_available_tasks()

        # Should return empty dict
        assert len(tasks) == 0
