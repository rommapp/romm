import importlib

import pytest

from config import TASK_RESULT_TTL
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
        task_type=mocker.MagicMock(value="cleanup"),
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

    def test_each_entry_gets_its_own_cron_identity(self, mocker, registered):
        # Every entry runs the same function, so an unnamed one would inherit
        # that func name and share one job history with all the others.
        register = registered(
            {"first": _task(mocker), "second": _task(mocker)},
        )

        names = [call.kwargs["name"] for call in register.call_args_list]
        assert names == ["first", "second"]

    def test_a_finished_run_is_kept_as_long_as_a_manual_one(self, mocker, registered):
        # rq.cron always passes a result_ttl, so leaving it out means its 500s
        # default rather than the worker's setting.
        register = registered({"test_task": _task(mocker)})

        assert register.call_args.kwargs["result_ttl"] == TASK_RESULT_TTL

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
