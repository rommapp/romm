import importlib

import pytest

from endpoints.responses import TaskType
from handler.redis_handler import SCAN_QUEUE_NAME, QueuePrio
from tasks import cron_config
from tasks.registry import SCHEDULED_TASKS
from tasks.tasks import run_task_by_name


@pytest.fixture
def registered(mocker):
    """Reload the config and report what it registered with the scheduler."""

    def _reload(tasks):
        register = mocker.patch("rq.cron.register")
        mocker.patch.dict(cron_config.SCHEDULED_TASKS, tasks, clear=True)
        importlib.reload(cron_config)
        return register

    return _reload


def _task(mocker, *, enabled=True, cron_string="0 4 * * *"):
    return mocker.MagicMock(
        enabled=enabled,
        cron_string=cron_string,
        timeout=100,
        title="Test Task",
        description="test task",
        task_type=TaskType.CLEANUP,
    )


class TestCronConfig:
    """The cron process registers what this module declares, and nothing else."""

    def test_registers_an_enabled_task_by_name(self, mocker, registered):
        register = registered({"test_task": _task(mocker)})

        register.assert_called_once()
        args, kwargs = register.call_args
        assert args[0] is run_task_by_name
        assert kwargs["kwargs"] == {"name": "test_task"}
        assert kwargs["cron"] == "0 4 * * *"

    def test_a_scan_is_registered_on_the_scan_queue(self, mocker, registered):
        task = _task(mocker)
        task.task_type = TaskType.SCAN
        register = registered({"scan_library": task})

        assert register.call_args.args[1] == SCAN_QUEUE_NAME

    def test_everything_else_stays_on_the_low_queue(self, mocker, registered):
        register = registered({"cleanup": _task(mocker)})

        assert register.call_args.args[1] == QueuePrio.LOW.value

    def test_skips_a_disabled_task(self, mocker, registered):
        assert registered({"off": _task(mocker, enabled=False)}).call_count == 0

    def test_skips_a_task_with_no_cron_string(self, mocker, registered):
        assert registered({"no_cron": _task(mocker, cron_string="")}).call_count == 0

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
