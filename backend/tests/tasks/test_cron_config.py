import importlib

import pytest

from config import TASK_RESULT_TTL, TASK_TIMEOUT
from handler.redis_handler import QueuePrio
from tasks import cron_config
from tasks.registry import SCHEDULED_TASKS, enqueue_scheduled_scan
from tasks.tasks import TaskSpec, TaskType, run_task_by_name


@pytest.fixture
def registered(mocker):
    """Reload the config and report what it registered with the scheduler."""

    def _reload(tasks):
        register = mocker.patch("rq.cron.register")
        mocker.patch.dict(SCHEDULED_TASKS, tasks, clear=True)
        importlib.reload(cron_config)
        return register

    return _reload


def _task(*, enabled=True, cron_string="0 4 * * *", **fields) -> TaskSpec:
    return TaskSpec(
        **{
            "implementation": "tests.tasks.test_cron_config.task",
            "title": "Test Task",
            "description": "test task",
            "task_type": TaskType.CLEANUP,
            "enabled": enabled,
            "cron_string": cron_string,
            "timeout": 100,
            **fields,
        }
    )


def _scan_task(**kwargs) -> TaskSpec:
    return _task(task_type=TaskType.SCAN, **kwargs)


class TestCronConfig:
    """The cron process registers what this module declares, and nothing else."""

    def test_registers_an_enabled_task_by_name(self, registered):
        register = registered({"test_task": _task()})

        register.assert_called_once()
        args, kwargs = register.call_args
        assert args[0] is run_task_by_name
        assert kwargs["kwargs"] == {"name": "test_task"}
        assert kwargs["cron"] == "0 4 * * *"
        assert kwargs["job_timeout"] == 100

    def test_a_scan_is_registered_through_the_dispatch_job(self, registered):
        # Cron takes no failure callback, so the scan is enqueued by a job that
        # can attach one rather than being registered with cron directly.
        register = registered({"scan_library": _scan_task()})

        kwargs = register.call_args.kwargs
        assert register.call_args.args[0] is enqueue_scheduled_scan
        assert kwargs["job_timeout"] == TASK_TIMEOUT
        # RQ drops a job whose result_ttl is 0 as soon as it succeeds, so the
        # dispatch is not listed next to the scan it enqueued.
        assert kwargs["result_ttl"] == 0

    def test_everything_runs_on_the_low_queue(self, registered):
        for tasks in ({"cleanup": _task()}, {"scan": _scan_task()}):
            register = registered(tasks)
            assert register.call_args.args[1] == QueuePrio.LOW.value

    def test_a_task_can_name_its_own_queue(self, registered):
        register = registered({"reaper": _task(queue_name="streaming")})

        assert register.call_args.args[1] == "streaming"

    def test_history_outlives_rq_s_own_result_ttl(self, registered):
        # `register()` defaults this, and a default is written onto the job, so
        # leaving it out would pin every cron job to RQ's 500 seconds.
        register = registered({"cleanup": _task()})

        assert register.call_args.kwargs["result_ttl"] == TASK_RESULT_TTL

    def test_a_task_can_keep_no_history(self, registered):
        register = registered({"frequent": _task(result_ttl=0)})

        assert register.call_args.kwargs["result_ttl"] == 0

    def test_each_entry_gets_its_own_cron_identity(self, registered):
        # Every entry runs the same function, so an unnamed one would inherit
        # that func name and share one job history with all the others.
        register = registered(
            {"first": _task(), "second": _task()},
        )

        names = [call.kwargs["name"] for call in register.call_args_list]
        assert names == ["first", "second"]

    def test_the_registered_meta_carries_the_key(self, registered):
        register = registered({"test_task": _task()})

        assert register.call_args.kwargs["meta"]["task_key"] == "test_task"

    def test_skips_a_disabled_task(self, registered):
        assert registered({"off": _task(enabled=False)}).call_count == 0

    def test_skips_a_task_with_no_cron_string(self, registered):
        assert registered({"no_cron": _task(cron_string="")}).call_count == 0

    def test_skips_a_task_with_an_invalid_cron_string(self, registered):
        register = registered({"bad": _task(cron_string="hourly"), "good": _task()})

        assert [call.kwargs["name"] for call in register.call_args_list] == ["good"]

    def test_registers_the_real_schedule(self, mocker):
        # Guards the actual catalog: every enabled task with a cron string is
        # registered, because nothing else schedules them any more.
        register = mocker.patch("rq.cron.register")
        importlib.reload(cron_config)

        expected = [
            name
            for name, task in SCHEDULED_TASKS.items()
            if task.enabled and task.cron_string
        ]
        registered_names = [
            call.kwargs["kwargs"]["name"] for call in register.call_args_list
        ]
        assert registered_names == expected
