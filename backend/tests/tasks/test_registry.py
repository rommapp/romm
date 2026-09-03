import pytest

from config import TASK_RESULT_TTL
from endpoints.sockets.scan import report_scan_failure
from exceptions.task_exceptions import TaskNotFoundException
from tasks.registry import (
    MANUAL_TASKS,
    SCHEDULED_TASKS,
    enqueue_scheduled_scan,
    enqueue_task,
    get_task,
)
from tasks.tasks import PeriodicTask, run_task_by_name


class TestRegistry:
    """A job payload carries only a name, so the catalog has to resolve it."""

    @pytest.mark.parametrize("name", sorted(SCHEDULED_TASKS | MANUAL_TASKS))
    def test_every_name_resolves(self, name: str):
        assert get_task(name) is not None

    def test_a_name_is_never_registered_twice(self):
        assert not SCHEDULED_TASKS.keys() & MANUAL_TASKS.keys()

    def test_scheduled_tasks_can_be_scheduled(self):
        for name, task in SCHEDULED_TASKS.items():
            assert isinstance(task, PeriodicTask), name

    def test_an_unknown_name_resolves_to_nothing(self):
        assert get_task("no_such_task") is None


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
        assert kwargs["kwargs"] == {"name": "cleanup_zip_cache", "task_kwargs": {}}
        assert kwargs["job_timeout"] == task.timeout
        assert kwargs["result_ttl"] == TASK_RESULT_TTL
        assert kwargs["meta"] == task.job_meta

    def test_caller_arguments_are_nested_under_the_name(self, queue):
        enqueue_task("cleanup_missing_roms", queue=queue, task_kwargs={"dry_run": True})

        kwargs = queue.enqueue.call_args.kwargs["kwargs"]
        assert kwargs == {
            "name": "cleanup_missing_roms",
            "task_kwargs": {"dry_run": True},
        }

    def test_job_options_reach_rq(self, queue):
        enqueue_task("cleanup_zip_cache", queue=queue, job_id="fixed", unique=True)

        kwargs = queue.enqueue.call_args.kwargs
        assert kwargs["job_id"] == "fixed"
        assert kwargs["unique"] is True

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
        assert kwargs["on_failure"] is report_scan_failure

    def test_the_scan_carries_its_own_timeout(self, scan_queue):
        # The dispatch itself runs on the ordinary task timeout, so the scan
        # timeout has to reach the scan it creates.
        enqueue_scheduled_scan("scan_library")

        job_timeout = scan_queue.enqueue.call_args.kwargs["job_timeout"]
        assert job_timeout == SCHEDULED_TASKS["scan_library"].timeout
