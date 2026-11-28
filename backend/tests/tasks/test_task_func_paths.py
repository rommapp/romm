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
    "tasks.tasks.notify_task_failure",
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


def _loaded_after(setup: str, watched: tuple[str, ...], then: str = "") -> str:
    """Run `setup` in a fresh interpreter and list the `watched` modules it loaded.

    `then` runs after the snapshot, so it can import what the setup deferred.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            f"{setup}\n"
            "watched = sys.argv[1:]\n"
            "loaded = ','.join(m for m in sys.modules\n"
            "    if any(m == w or m.startswith(w + '.') for w in watched))\n"
            f"{then}\n"
            "print('LOADED:' + loaded)\n",
            *watched,
        ],
        cwd=BACKEND_ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    return result.stdout.rpartition("LOADED:")[2].strip()


# Loaded only by the jobs that need them, so the long-lived scheduler and
# worker parents stay small. Each name covers its submodules too.
HEAVY_MODULES = (
    "tasks.manual",
    "tasks.sync_push_pull_task",
    "handler.database",
    "handler.auth.base_handler",
    "fastapi",
    "httpx2",
)
JOB_ONLY_MODULES = ("tasks.scheduled", *HEAVY_MODULES)


@pytest.mark.parametrize("module", ["tasks.cron_config", "handler.rq_worker"])
def test_the_scheduler_and_worker_load_no_task_code(module):
    loaded = _loaded_after(f"import {module}", JOB_ONLY_MODULES)

    assert loaded == "", f"{module} loads {loaded}"


# Left to the streaming work horse that tears a session down or pushes a notice.
PRELOAD_DEFERRED_MODULES = (
    *HEAVY_MODULES,
    "handler.scan",
    "handler.metadata",
    "handler.streaming.lifecycle",
    "handler.socket_handler",
    "endpoints",
)


def test_the_streaming_worker_preloads_its_tasks_without_their_teardown():
    """The parent keeps what it preloads, and a work horse can still import the rest."""
    # Every streaming task, enabled or not, as PreloadingWorker would load them.
    loaded = _loaded_after(
        "import handler.rq_worker\n"
        "from handler.redis_handler import STREAMING_QUEUE_NAME\n"
        "from tasks.registry import SCHEDULED_TASKS, get_task\n"
        "for name, spec in SCHEDULED_TASKS.items():\n"
        "    if spec.queue_name == STREAMING_QUEUE_NAME:\n"
        "        get_task(name)",
        PRELOAD_DEFERRED_MODULES,
        then="import handler.streaming.lifecycle, handler.notification_handler",
    )

    assert loaded == "", f"the streaming preload loads {loaded}"
