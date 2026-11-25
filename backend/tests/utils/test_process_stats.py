from pathlib import Path
from unittest.mock import MagicMock

import pytest

from utils.process_stats import (
    _ROLES,
    process_kind,
    process_kinds,
    process_role,
    romm_processes,
)


@pytest.mark.parametrize(
    "cmdline,role",
    [
        (["/src/.venv/bin/python", "/src/.venv/bin/gunicorn", "main:app"], "api"),
        (["/app/.venv/bin/python", "main.py"], "api"),
        (["/src/.venv/bin/rq", "cron", "tasks.cron_config"], "rq_cron"),
        (
            ["python", "-m", "rq.cli", "worker", "--with-scheduler", "scans"],
            "rq_scan_worker",
        ),
        (
            [
                "/src/.venv/bin/rq",
                "worker",
                "--worker-class",
                "handler.rq_worker.PreloadingWorker",
                "streaming",
            ],
            "rq_streaming_worker",
        ),
        (["/src/.venv/bin/rq", "worker", "high", "default", "low"], "rq_worker"),
        (
            [
                "watchfiles",
                "--target-type",
                "command",
                "python3 watcher.py",
                "/romm/library",
            ],
            "watcher",
        ),
        (
            [
                "watchfiles",
                "--target-type",
                "command",
                "python3 sync_watcher.py",
                "/romm/sync",
            ],
            "sync_watcher",
        ),
        (["nginx: worker process"], "nginx"),
        (["valkey-server *:6379"], "valkey"),
        (["/usr/lib/firefox/firefox", "-contentproc"], None),
    ],
)
def test_process_role_names_each_romm_process(cmdline, role) -> None:
    assert process_role(cmdline) == role


def test_romm_processes_skips_every_other_process(mocker) -> None:
    romm = MagicMock(info={"cmdline": ["/src/.venv/bin/rq", "cron"], "ppid": 1})
    other = MagicMock(info={"cmdline": ["/usr/lib/firefox/firefox"], "ppid": 1})
    gone = MagicMock(info={"cmdline": None, "ppid": 1})
    mocker.patch(
        "utils.process_stats.psutil.process_iter", return_value=[romm, other, gone]
    )

    assert list(romm_processes()) == [(romm, "rq_cron")]


def test_a_python_child_of_a_romm_process_takes_its_role(mocker) -> None:
    # What `uvicorn --reload` runs the app in: a spawned child that names nothing.
    server = MagicMock(
        pid=10, info={"cmdline": ["python", "main.py"], "ppid": 1, "name": "python"}
    )
    spawned = MagicMock(
        pid=11,
        info={
            "cmdline": ["python", "-c", "spawn_main()"],
            "ppid": 10,
            "name": "python",
        },
    )
    helper = MagicMock(pid=12, info={"cmdline": ["gzip"], "ppid": 10, "name": "gzip"})
    stranger = MagicMock(
        pid=13, info={"cmdline": ["python", "x.py"], "ppid": 1, "name": "python"}
    )
    mocker.patch(
        "utils.process_stats.psutil.process_iter",
        return_value=[server, spawned, helper, stranger],
    )

    assert list(romm_processes()) == [(server, "api"), (spawned, "api")]


@pytest.mark.parametrize(
    "role,pid,parent_role,pgid,kind",
    [
        ("rq_scan_worker", 80, None, 7, "parent"),
        ("rq_scan_worker", 163, "rq_scan_worker", 7, "scheduler"),
        ("rq_scan_worker", 412, "rq_scan_worker", 412, "work_horse"),
        ("rq_streaming_worker", 90, None, 7, "parent"),
        ("api", 71, None, 7, "master"),
        ("api", 139, "api", 7, "worker"),
        ("nginx", 20, None, 20, "master"),
        ("nginx", 21, "nginx", 20, "worker"),
        ("rq_cron", 60, None, 7, "main"),
        ("valkey", 30, None, 7, "main"),
        ("watcher", 50, "watcher", 7, "worker"),
    ],
)
def test_process_kind_names_each_process_within_its_role(
    role, pid, parent_role, pgid, kind
) -> None:
    assert process_kind(role, pid, parent_role, pgid) == kind


def test_process_kinds_tells_a_work_horse_from_the_scheduler(mocker) -> None:
    parent = MagicMock(pid=80, info={"ppid": 1})
    scheduler = MagicMock(pid=163, info={"ppid": 80})
    horse = MagicMock(pid=412, info={"ppid": 80})
    # A work horse leads its own process group; the scheduler is in its parent's.
    groups = {80: 7, 163: 7, 412: 412}
    mocker.patch("utils.process_stats.os.getpgid", side_effect=groups.__getitem__)

    kinds = process_kinds(
        [
            (parent, "rq_scan_worker"),
            (scheduler, "rq_scan_worker"),
            (horse, "rq_scan_worker"),
        ]
    )

    assert kinds == {80: "parent", 163: "scheduler", 412: "work_horse"}


def test_a_process_that_exits_before_its_group_is_read_still_gets_a_kind(
    mocker,
) -> None:
    child = MagicMock(pid=163, info={"ppid": 80})
    parent = MagicMock(pid=80, info={"ppid": 1})
    mocker.patch("utils.process_stats.os.getpgid", side_effect=ProcessLookupError(163))

    kinds = process_kinds([(parent, "rq_worker"), (child, "rq_worker")])

    assert kinds == {80: "parent", 163: "scheduler"}


S6_SERVICES = Path(__file__).parents[3] / "docker" / "s6-overlay" / "s6-rc.d"

# Each long-lived s6 service, with a command line it starts. Services that only
# run to completion or probe readiness are listed separately.
SERVICE_COMMANDS = {
    "romm-gunicorn": (["python", "/usr/bin/gunicorn", "main:app"], "api"),
    "romm-rq-cron": (["rq", "cron", "tasks.cron_config"], "rq_cron"),
    "romm-rq-worker": (
        ["rq", "worker", "--worker-class", "handler.rq_worker.RomMWorker", "high"],
        "rq_worker",
    ),
    "romm-rq-scan-worker": (
        ["rq", "worker", "--worker-class", "handler.rq_worker.RomMWorker", "scans"],
        "rq_scan_worker",
    ),
    "romm-rq-streaming-worker": (
        ["rq", "worker", "--worker-class", "handler.rq_worker.PreloadingWorker"],
        "rq_streaming_worker",
    ),
    "romm-watcher": (["watchfiles", "python3 watcher.py"], "watcher"),
    "romm-sync-watcher": (["watchfiles", "python3 sync_watcher.py"], "sync_watcher"),
    "romm-nginx": (["nginx", "-g", "daemon off;"], "nginx"),
    "romm-valkey": (["valkey-server", "*:6379"], "valkey"),
}
NOT_LONG_LIVED = {
    "romm-init",
    "romm-migrations",
    "romm-startup",
    "romm-gunicorn-ready",
    "romm-valkey-ready",
}


@pytest.mark.skipif(not S6_SERVICES.is_dir(), reason="the s6 services are not here")
def test_every_long_lived_service_has_a_role() -> None:
    # A service added without a role would be missing from every memory chart.
    services = {path.name for path in S6_SERVICES.glob("romm-*") if path.is_dir()}

    assert services - NOT_LONG_LIVED == set(SERVICE_COMMANDS)


@pytest.mark.parametrize(
    "command,role", SERVICE_COMMANDS.values(), ids=SERVICE_COMMANDS.keys()
)
def test_each_service_command_gets_its_role(command: list[str], role: str) -> None:
    assert process_role(command) == role


def test_every_role_belongs_to_a_service() -> None:
    service_roles = {role for _, role in SERVICE_COMMANDS.values()}

    assert {role for _, role in _ROLES} == service_roles
