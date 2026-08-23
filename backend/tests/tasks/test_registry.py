import pytest

from tasks.registry import MANUAL_TASKS, SCHEDULED_TASKS, get_task
from tasks.tasks import PeriodicTask


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
