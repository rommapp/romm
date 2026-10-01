import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# The only callables a job payload names. Everything else runs through
# run_task_by_name, which resolves it from the registry.
JOB_FUNC_PATHS = (
    "tasks.tasks.run_task_by_name",
    "endpoints.sockets.scan.scan_platforms",
    "tasks.registry.enqueue_scheduled_scan",
)


@pytest.mark.parametrize("func", JOB_FUNC_PATHS)
def test_task_func_resolves_in_a_fresh_interpreter(func):
    """The RQ worker resolves a job by importing its func path into a process
    where that module is the first application module imported. An import cycle
    that stays hidden in the web process breaks the job there."""
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


# Loaded only by the jobs that need them, so the long-lived scheduler and
# worker parents stay small.
APP_STACK_MODULES = ("handler.database", "handler.auth.base_handler", "fastapi")


@pytest.mark.parametrize("module", ["tasks.cron_config", "handler.rq_worker"])
def test_the_scheduler_and_worker_load_no_task_code(module):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys\n"
            "importlib.import_module(sys.argv[1])\n"
            "print('LOADED:' + ','.join(m for m in sys.argv[2:] if m in sys.modules))\n",
            module,
            *APP_STACK_MODULES,
        ],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    loaded = result.stdout.rpartition("LOADED:")[2].strip()
    assert loaded == "", f"{module} loads {loaded}"
