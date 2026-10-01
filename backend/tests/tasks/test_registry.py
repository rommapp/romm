import os
import subprocess
import sys
from pathlib import Path

import pytest
from rq.utils import import_attribute

from config import TASK_RESULT_TTL
from endpoints.sockets.scan import report_scan_failure
from exceptions.task_exceptions import TaskNotFoundException
from tasks.registry import (
    MANUAL_TASKS,
    SCHEDULED_TASKS,
    enqueue_scheduled_scan,
    enqueue_task,
    get_task,
    get_task_spec,
)
from tasks.tasks import PeriodicTask, Task, run_task_by_name


class TestRegistry:
    """A job payload carries only a name, so the catalog has to resolve it."""

    @pytest.mark.parametrize("name", sorted(SCHEDULED_TASKS | MANUAL_TASKS))
    def test_every_name_resolves_to_a_task_built_from_its_spec(self, name: str):
        task = get_task(name)

        assert isinstance(task, Task)
        assert task.spec is get_task_spec(name)

    def test_a_name_is_never_registered_twice(self):
        assert not SCHEDULED_TASKS.keys() & MANUAL_TASKS.keys()

    def test_scheduled_tasks_can_be_scheduled(self):
        for name in SCHEDULED_TASKS:
            assert isinstance(get_task(name), PeriodicTask), name

    def test_an_unknown_name_resolves_to_nothing(self):
        assert get_task("no_such_task") is None
        assert get_task_spec("no_such_task") is None


class TestEnqueueTask:
    """Every enqueue goes through here, so the payload is built in one place."""

    @pytest.fixture
    def queue(self, mocker):
        return mocker.MagicMock()

    def test_the_payload_carries_the_name_and_the_task_metadata(self, queue):
        enqueue_task("cleanup_zip_cache", queue=queue)

        args, kwargs = queue.enqueue.call_args
        task = SCHEDULED_TASKS["cleanup_zip_cache"]
        assert args[0] is run_task_by_name
        assert kwargs["kwargs"] == {
            "name": "cleanup_zip_cache",
            "task_kwargs": {},
            "run_by_user_id": None,
        }
        assert kwargs["job_timeout"] == task.timeout
        assert kwargs["result_ttl"] == TASK_RESULT_TTL
        assert kwargs["meta"] == task.job_meta("cleanup_zip_cache")
        assert kwargs["meta"]["task_key"] == "cleanup_zip_cache"

    def test_caller_arguments_are_nested_under_the_name(self, queue):
        enqueue_task("cleanup_missing_roms", queue=queue, task_kwargs={"dry_run": True})

        kwargs = queue.enqueue.call_args.kwargs["kwargs"]
        assert kwargs == {
            "name": "cleanup_missing_roms",
            "task_kwargs": {"dry_run": True},
            "run_by_user_id": None,
        }

    def test_job_options_reach_rq(self, queue):
        enqueue_task("cleanup_zip_cache", queue=queue, job_id="fixed", unique=True)

        kwargs = queue.enqueue.call_args.kwargs
        assert kwargs["job_id"] == "fixed"
        assert kwargs["unique"] is True

    @pytest.mark.parametrize(
        "name,queue_name",
        [("cleanup_zip_cache", "low"), ("reap_streaming_sessions", "streaming")],
    )
    def test_defaults_to_the_queue_the_spec_names(self, mocker, name, queue_name):
        queue = mocker.MagicMock()
        mocker.patch.dict("tasks.registry.QUEUES_BY_NAME", {queue_name: queue})

        enqueue_task(name)

        queue.enqueue.assert_called_once()

    def test_an_unknown_name_is_refused_before_it_reaches_redis(self, queue):
        with pytest.raises(TaskNotFoundException):
            enqueue_task("no_such_task", queue=queue)

        queue.enqueue.assert_not_called()


class TestEnqueueScheduledScan:
    """Cron cannot attach a failure callback, so a dispatch job does it."""

    @pytest.fixture
    def scan_queue(self, mocker):
        queue = mocker.patch("tasks.registry.scan_queue")
        queue.enqueue.return_value = mocker.MagicMock(id="job-1")
        return queue

    def test_enqueues_the_scan_with_the_abandoned_job_callback(self, scan_queue):
        assert enqueue_scheduled_scan("scan_library") == "job-1"

        args, kwargs = scan_queue.enqueue.call_args
        assert args[0] is run_task_by_name
        assert kwargs["kwargs"]["name"] == "scan_library"
        assert import_attribute(kwargs["on_failure"].func) is report_scan_failure

    def test_the_scan_carries_its_own_timeout(self, scan_queue):
        # The dispatch itself runs on the ordinary task timeout, so the scan
        # timeout has to reach the scan it creates.
        enqueue_scheduled_scan("scan_library")

        job_timeout = scan_queue.enqueue.call_args.kwargs["job_timeout"]
        assert job_timeout == SCHEDULED_TASKS["scan_library"].timeout


BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "env,name,field,expected",
    [
        ({"AUDIT_LOG_RETENTION_DAYS": "0"}, "cleanup_audit_log", "enabled", False),
        ({"AUDIT_LOG_RETENTION_DAYS": "30"}, "cleanup_audit_log", "enabled", True),
        (
            {"SCHEDULED_RESCAN_CRON": "5 4 * * 1"},
            "scan_library",
            "cron_string",
            "5 4 * * 1",
        ),
        (
            {
                "LAUNCHBOX_API_ENABLED": "true",
                "ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA": "false",
            },
            "update_launchbox_metadata",
            "can_run_manually",
            True,
        ),
        (
            {
                "LAUNCHBOX_API_ENABLED": "false",
                "ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA": "false",
            },
            "update_launchbox_metadata",
            "can_run_manually",
            False,
        ),
    ],
)
def test_specs_follow_the_config_they_start_with(env, name, field, expected):
    """Specs read config once at import, so each case needs a fresh interpreter."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from tasks.registry import get_task_spec\n"
            "print(repr(getattr(get_task_spec(sys.argv[1]), sys.argv[2])))\n",
            name,
            field,
        ],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT), **env},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == repr(expected)
