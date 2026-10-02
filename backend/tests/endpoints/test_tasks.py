from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import Mock, PropertyMock, patch

import pytest
from fastapi import status
from rq.exceptions import DeserializationError, NoSuchJobError
from tests.factories import make_device_token
from tests.scan_job_stubs import make_job, make_scoped_job, patch_scan_jobs

from endpoints.sockets.scan import scan_platforms
from endpoints.tasks import SINGLE_INSTANCE_LOCK_PREFIX
from handler.redis_handler import low_prio_queue, redis_client, scan_queue
from handler.scan_handler import ScanType
from handler.scan_jobs import SCAN_PLATFORMS_FUNC
from tasks.manual.cleanup_missing_firmware import CleanupMissingFirmwareStats
from tasks.manual.cleanup_missing_roms import CleanupMissingRomsStats
from tasks.tasks import TaskSpec, TaskType


def _job_with_meta(meta: dict[str, Any]) -> Mock:
    """A finished job carrying `meta`, for asserting on what the response reports."""
    job = Mock()
    job.id = "test-job-id-123"
    job.kwargs = {}
    # What the response falls back to when the meta carries no task name.
    job.func_name = "test_task"
    job.get_meta.return_value = {"task_type": TaskType.CLEANUP, **meta}
    job.get_status.return_value = "finished"
    for attr in ("created_at", "enqueued_at", "started_at", "ended_at"):
        setattr(job, attr, None)
    return job


@pytest.fixture(autouse=True)
def task_worker_listening():
    """A live task worker, so a run is accepted unless a test takes it away."""
    with patch("endpoints.tasks.has_live_worker", return_value=True) as mocked:
        yield mocked


@pytest.fixture
def mock_task():
    """Create a mock task for testing"""
    task = Mock(spec=TaskSpec)
    task.title = "Test Task"
    task.description = "A test task for unit testing"
    task.task_type = TaskType.CLEANUP
    task.enabled = True
    task.manual_run = True
    task.can_run_manually = True
    task.cron_string = "0 0 * * *"
    task.timeout = 300
    task.destructive = False
    task.single_instance = False
    return task


@pytest.fixture
def mock_disabled_task():
    """Create a mock disabled task for testing"""
    task = Mock(spec=TaskSpec)
    task.title = "Disabled Task"
    task.description = "A disabled task for testing"
    task.task_type = TaskType.CLEANUP
    task.enabled = False
    task.manual_run = True
    task.can_run_manually = False
    task.cron_string = None
    task.timeout = 300
    return task


@pytest.fixture
def mock_non_manual_task():
    """Create a mock task that cannot be run manually"""
    task = Mock(spec=TaskSpec)
    task.title = "Non-Manual Task"
    task.description = "A task that cannot be run manually"
    task.task_type = TaskType.CLEANUP
    task.enabled = True
    task.manual_run = False
    task.can_run_manually = False
    task.cron_string = "0 0 * * *"
    task.timeout = 300
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
                spec=TaskSpec,
                task_type=TaskType.CLEANUP,
                title="Manual Task",
                description="Manual task",
                enabled=True,
                manual_run=True,
                can_run_manually=True,
                destructive=True,
                timeout=300,
                cron_string=None,
            ),
        },
    )
    @patch(
        "endpoints.tasks.VISIBLE_SCHEDULED_TASKS",
        {
            "test_scheduled": Mock(
                spec=TaskSpec,
                task_type=TaskType.UPDATE,
                title="Scheduled Task",
                description="Scheduled task",
                enabled=True,
                manual_run=False,
                can_run_manually=False,
                destructive=False,
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
        assert scheduled_task["destructive"] is False
        assert scheduled_task["cron_string"] == "0 0 * * *"

        # Check manual tasks
        assert len(data["manual"]) == 1
        manual_task = data["manual"][0]
        assert manual_task["name"] == "test_manual"
        assert manual_task["title"] == "Manual Task"
        assert manual_task["description"] == "Manual task"
        assert manual_task["enabled"] is True
        assert manual_task["manual_run"] is True
        assert manual_task["destructive"] is True
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

        from handler.auth.base_handler import oauth_handler

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
    def test_run_single_task_success(
        self,
        mock_enqueue,
        client,
        access_token,
        admin_user,
        mock_task,
        task_worker_listening,
    ):
        """Test successful running of a single task"""
        with patch("endpoints.tasks.RUNNABLE_TASKS", {"test_task": mock_task}):
            response = client.post(
                "/api/tasks/run/test_task",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["task_key"] == "test_task"
        assert data["task_name"] == "Test Task"
        assert data["task_id"] == "1"
        assert data["status"] == "queued"
        assert "created_at" in data
        assert "enqueued_at" in data

        # The worker check and the enqueue must name the same queue.
        task_worker_listening.assert_called_once_with(low_prio_queue)
        mock_enqueue.assert_called_once_with(
            "test_task",
            queue=low_prio_queue,
            task_kwargs={},
            run_by_user_id=admin_user.id,
        )

    @patch("endpoints.tasks.enqueue_task")
    def test_run_single_task_without_a_worker_is_refused(
        self, mock_enqueue, client, access_token, mock_task, task_worker_listening
    ):
        task_worker_listening.return_value = False
        with patch("endpoints.tasks.RUNNABLE_TASKS", {"test_task": mock_task}):
            response = client.post(
                "/api/tasks/run/test_task",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "worker" in response.json()["detail"]
        mock_enqueue.assert_not_called()

    @patch("endpoints.tasks.enqueue_task")
    @patch("endpoints.tasks.get_active_task_job", return_value=create_mock_job())
    def test_a_single_instance_task_already_active_is_refused(
        self, _active, mock_enqueue, client, access_token, mock_task
    ):
        mock_task.single_instance = True
        with patch("endpoints.tasks.RUNNABLE_TASKS", {"test_task": mock_task}):
            response = client.post(
                "/api/tasks/run/test_task",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already queued or running" in response.json()["detail"]
        mock_enqueue.assert_not_called()

    @patch("endpoints.tasks.enqueue_task", return_value=create_mock_job())
    @patch("endpoints.tasks.get_active_task_job", return_value=None)
    def test_a_second_run_racing_the_first_is_refused(
        self, _active, mock_enqueue, client, access_token, mock_task
    ):
        mock_task.single_instance = True
        redis_client.delete(f"{SINGLE_INSTANCE_LOCK_PREFIX}test_task")
        with patch("endpoints.tasks.RUNNABLE_TASKS", {"test_task": mock_task}):
            statuses = [
                client.post(
                    "/api/tasks/run/test_task",
                    headers={"Authorization": f"Bearer {access_token}"},
                ).status_code
                for _ in range(2)
            ]
        redis_client.delete(f"{SINGLE_INSTANCE_LOCK_PREFIX}test_task")

        assert statuses == [status.HTTP_200_OK, status.HTTP_409_CONFLICT]
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
                spec=TaskSpec,
                task_type=TaskType.CLEANUP,
                title="Disabled Task",
                description="Disabled Description",
                enabled=False,
                manual_run=True,
                can_run_manually=False,
                timeout=300,
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
                spec=TaskSpec,
                task_type=TaskType.CLEANUP,
                title="Non-Manual Task",
                description="Non-Manual Description",
                enabled=True,
                manual_run=False,
                can_run_manually=False,
                timeout=300,
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

    @pytest.mark.parametrize(
        "stats",
        [
            CleanupMissingRomsStats(platform_ids=[3], roms_found=2, roms_deleted=2),
            CleanupMissingFirmwareStats(firmware_found=1, firmware_deleted=1),
        ],
    )
    @patch("endpoints.tasks.Job.fetch")
    def test_a_finished_cleanup_reports_its_stats(
        self, mock_job_fetch, client, access_token, stats
    ):
        mock_job_fetch.return_value = _job_with_meta({"cleanup_stats": stats.to_dict()})

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["meta"]["cleanup_stats"] == stats.to_dict()

    @pytest.mark.parametrize(("platform_id", "platform_ids"), [(3, [3]), (None, None)])
    @patch("endpoints.tasks.Job.fetch")
    def test_a_cleanup_predating_platform_ids_reports_them(
        self, mock_job_fetch, client, access_token, platform_id, platform_ids
    ):
        """Stats stored by an older release name a single platform."""
        mock_job_fetch.return_value = _job_with_meta(
            {
                # The shape 5.2.0 stored.
                "cleanup_stats": {
                    "platform_id": platform_id,
                    "roms_found": 2,
                    "roms_deleted": 2,
                    "errors": 0,
                },
            }
        )

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["meta"]["cleanup_stats"] == {
            "platform_ids": platform_ids,
            "roms_found": 2,
            "roms_deleted": 2,
            "errors": 0,
        }

    @patch("endpoints.tasks.Job.fetch")
    def test_a_job_whose_kwargs_can_no_longer_be_loaded_still_reports(
        self, mock_job_fetch, client, access_token
    ):
        """A job pickled by an older release may not unpickle after an upgrade."""
        job = _job_with_meta({})
        type(job).kwargs = PropertyMock(side_effect=DeserializationError("stale"))
        mock_job_fetch.return_value = job

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["task_key"] is None

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
        mock_job.kwargs = {}
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

    @pytest.mark.parametrize(
        ("meta", "expected_key"),
        [
            (
                {
                    "task_key": "cleanup_zip_cache",
                    "task_name": "Scheduled ZIP cache cleanup",
                },
                "cleanup_zip_cache",
            ),
            ({"task_name": "Quick Scan"}, None),
        ],
        ids=["catalog entry", "started outside the catalog"],
    )
    @patch("endpoints.tasks.Job.fetch")
    def test_the_response_reports_the_registry_key(
        self, mock_job_fetch, meta, expected_key, client, access_token
    ):
        """The key a run is matched to its catalog entry by, null when it has none."""
        mock_job_fetch.return_value = _job_with_meta(meta)

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.json()["task_key"] == expected_key

    @patch("endpoints.tasks.Job.fetch")
    def test_a_job_predating_the_field_falls_back_to_its_payload(
        self, mock_job_fetch, client, access_token
    ):
        """An in-flight job survives the upgrade matchable, without its meta."""
        job = _job_with_meta({"task_name": "Scheduled ZIP cache cleanup"})
        job.kwargs = {"name": "cleanup_zip_cache", "task_kwargs": {}}
        mock_job_fetch.return_value = job

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.json()["task_key"] == "cleanup_zip_cache"

    @patch("endpoints.tasks.Job.fetch")
    def test_a_scan_predating_a_counter_reports_it_as_zero(
        self, mock_job_fetch, client, access_token
    ):
        """Stats stored by an older release lack the counters it predates."""
        mock_job_fetch.return_value = _job_with_meta(
            {
                "task_type": TaskType.SCAN,
                # The shape 5.2.0 stored, which had neither counter.
                "scan_stats": {
                    "total_platforms": 1,
                    "total_roms": 819,
                    "scanned_platforms": 1,
                    "new_platforms": 1,
                    "identified_platforms": 1,
                    "scanned_roms": 378,
                    "new_roms": 378,
                    "identified_roms": 378,
                    "scanned_firmware": 0,
                    "new_firmware": 0,
                },
            }
        )

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        scan_stats = response.json()["meta"]["scan_stats"]
        assert scan_stats["updated_roms"] == 0
        assert scan_stats["new_files"] == 0
        assert scan_stats["scanned_roms"] == 378

    @patch("endpoints.tasks.Job.fetch")
    def test_a_scan_that_never_reported_stats_keeps_none(
        self, mock_job_fetch, client, access_token
    ):
        """A queued scan has no counters yet, which is not the same as zeroes."""
        mock_job_fetch.return_value = _job_with_meta({"task_type": TaskType.SCAN})

        response = client.get(
            "/api/tasks/test-job-id-123",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["meta"]["scan_stats"] is None

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
        mock_job.kwargs = {}
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
            "destructive": False,
            "cron_string": "0 0 * * *",
        }

        with patch(
            "endpoints.tasks.MANUAL_TASKS",
            {
                "test_task": Mock(
                    spec=TaskSpec,
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
                    spec=TaskSpec,
                    task_type=TaskType.CLEANUP,
                    title="Workflow Task",
                    description="Workflow Description",
                    enabled=True,
                    manual_run=True,
                    can_run_manually=True,
                    timeout=300,
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
                spec=TaskSpec,
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


class TestStartScan:
    """Test suite for the start_scan endpoint"""

    @pytest.fixture
    def enqueue(self, mocker):
        # No scan in flight unless a test patches the scan jobs again.
        patch_scan_jobs(mocker)
        return mocker.patch.object(
            scan_queue, "enqueue", return_value=create_mock_job("scan-job")
        )

    @pytest.fixture
    def post_scan(self, client, access_token):
        def post(token=access_token, **kwargs):
            return client.post(
                "/api/tasks/scan",
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )

        return post

    def test_queues_the_scan_it_was_asked_for(
        self, enqueue, post_scan, admin_user, task_worker_listening
    ):
        response = post_scan(
            json={
                "type": "update",
                "platforms": [1, 2],
                "platform_fs_slugs": ["n64"],
                "apis": ["igdb", "ss"],
                "launchbox_remote_enabled": False,
            },
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["task_id"] == "scan-job"
        assert data["task_key"] is None
        assert data["task_name"] == "Update Scan"
        assert data["status"] == "queued"

        task_worker_listening.assert_called_once_with(scan_queue)
        assert enqueue.call_args.args == (scan_platforms,)
        kwargs = enqueue.call_args.kwargs
        assert kwargs["platform_ids"] == [1, 2]
        assert kwargs["metadata_sources"] == ["igdb", "ss"]
        assert kwargs["scan_type"] == ScanType.UPDATE
        assert kwargs["roms_ids"] == []
        assert kwargs["platform_fs_slugs"] == ["n64"]
        assert kwargs["launchbox_remote_enabled"] is False
        assert kwargs["started_by_user_id"] == admin_user.id
        assert kwargs["at_front"] is False

    @pytest.mark.parametrize("body", [{"json": {}}, {}], ids=["empty", "missing"])
    def test_no_options_queue_a_quick_scan_of_everything(
        self, mocker, enqueue, post_scan, body
    ):
        mocker.patch(
            "endpoints.tasks.get_enabled_metadata_sources", return_value=["igdb"]
        )

        response = post_scan(**body)

        assert response.status_code == status.HTTP_202_ACCEPTED
        kwargs = enqueue.call_args.kwargs
        assert kwargs["scan_type"] == ScanType.QUICK
        assert kwargs["platform_ids"] == []
        assert kwargs["metadata_sources"] == ["igdb"]
        assert kwargs["launchbox_remote_enabled"] is True

    def test_an_empty_apis_list_scans_without_sources(self, mocker, enqueue, post_scan):
        mocker.patch(
            "endpoints.tasks.get_enabled_metadata_sources", return_value=["igdb"]
        )

        response = post_scan(json={"apis": []})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert enqueue.call_args.kwargs["metadata_sources"] == []

    @pytest.mark.parametrize(
        ("scopes", "expected"),
        [
            ("tasks.run", status.HTTP_202_ACCEPTED),
            ("roms.read", status.HTTP_403_FORBIDDEN),
        ],
    )
    def test_a_client_token_needs_tasks_run(
        self, enqueue, post_scan, admin_user, scopes, expected
    ):
        _, raw_token = make_device_token(admin_user, None, scopes=scopes)

        response = post_scan(token=raw_token, json={})

        assert response.status_code == expected
        assert enqueue.called == (expected == status.HTTP_202_ACCEPTED)

    def test_a_library_scan_in_flight_is_refused(self, mocker, enqueue, post_scan):
        patch_scan_jobs(
            mocker,
            running=make_job(SCAN_PLATFORMS_FUNC, task_name="Quick Scan"),
        )

        response = post_scan(json={})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Quick Scan is already running"
        enqueue.assert_not_called()

    def test_a_held_request_lock_is_refused(self, mocker, enqueue, post_scan):
        @asynccontextmanager
        async def held_lock(*args, **kwargs):
            raise TimeoutError
            yield

        mocker.patch("endpoints.sockets.scan.redis_lock", held_lock)

        response = post_scan(json={})

        assert response.status_code == status.HTTP_409_CONFLICT
        enqueue.assert_not_called()

    def test_a_rom_scan_is_accepted_while_a_library_scan_runs(
        self, mocker, enqueue, post_scan
    ):
        patch_scan_jobs(mocker, running=make_job(SCAN_PLATFORMS_FUNC))

        response = post_scan(json={"roms_ids": [7]})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert enqueue.call_args.kwargs["at_front"] is True

    def test_a_running_rom_scan_does_not_block_a_library_scan(
        self, mocker, enqueue, post_scan
    ):
        patch_scan_jobs(mocker, running=make_scoped_job())

        response = post_scan(json={})

        assert response.status_code == status.HTTP_202_ACCEPTED
        enqueue.assert_called_once()

    def test_without_a_scan_worker_is_refused(
        self, enqueue, post_scan, task_worker_listening
    ):
        task_worker_listening.return_value = False

        response = post_scan(json={})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "worker" in response.json()["detail"]
        enqueue.assert_not_called()

    @pytest.mark.parametrize(
        "body",
        [
            {"type": "deep"},
            {"apis": ["not-a-source"]},
            {"platforms": ["x"]},
            # The names scan_platforms takes, which would otherwise scan everything.
            {"platform_ids": [1]},
            {"scan_type": "complete"},
        ],
    )
    def test_an_invalid_body_is_rejected(self, enqueue, post_scan, body):
        response = post_scan(json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        enqueue.assert_not_called()

    def test_unauthenticated_is_rejected(self, enqueue, client):
        response = client.post("/api/tasks/scan", json={})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        enqueue.assert_not_called()
