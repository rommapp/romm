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
