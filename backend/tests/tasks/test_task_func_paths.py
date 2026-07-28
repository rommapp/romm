import os
import pkgutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

import tasks
from tasks.tasks import PeriodicTask

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _periodic_task_funcs() -> list[str]:
    funcs = set()
    for module_info in pkgutil.walk_packages(tasks.__path__, prefix="tasks."):
        module = import_module(module_info.name)
        for value in vars(module).values():
            if isinstance(value, PeriodicTask):
                funcs.add(value.func)
    return sorted(funcs)


@pytest.mark.parametrize("func", _periodic_task_funcs())
def test_task_func_resolves_in_a_fresh_interpreter(func):
    """The RQ worker resolves a job by importing its func path into a process
    where the task module is the first application module imported. An import
    cycle that stays hidden in the web process breaks the job there, so resolve
    each func the way the worker does, in a clean interpreter."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from rq.utils import import_attribute\n"
            "assert callable(import_attribute(sys.argv[1]))\n",
            func,
        ],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"{func} is not importable by RQ:\n{result.stderr}"
