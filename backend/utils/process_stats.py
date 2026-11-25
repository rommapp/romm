"""Find RomM's processes by their command lines, for telemetry and tools."""

import os
import re
from collections.abc import Iterator, Sequence
from typing import Final

import psutil

RQ_WORKER_ROLES: Final = frozenset(
    {"rq_worker", "rq_scan_worker", "rq_streaming_worker"}
)

# What a role's first process is called; any other role's first process is "main".
_FIRST_PROCESS_KIND: Final[dict[str, str]] = {
    **dict.fromkeys(RQ_WORKER_ROLES, "parent"),
    "api": "master",
    "nginx": "master",
}

# Matched in order against each process's command line; the first match wins.
_ROLES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\brq(?:\.cli)? cron\b"), "rq_cron"),
    (re.compile(r"\bPreloadingWorker\b"), "rq_streaming_worker"),
    (re.compile(r"\brq(?:\.cli)? worker\b.*\bscans\b"), "rq_scan_worker"),
    (re.compile(r"\brq(?:\.cli)? worker\b"), "rq_worker"),
    (re.compile(r"\bgunicorn\b|\bmain\.py\b"), "api"),
    (re.compile(r"\bsync_watcher\.py\b"), "sync_watcher"),
    (re.compile(r"\bwatcher\.py\b|\bwatchfiles\b"), "watcher"),
    (re.compile(r"\bnginx\b"), "nginx"),
    (re.compile(r"\b(?:valkey|redis)-server\b"), "valkey"),
)


def process_role(cmdline: list[str]) -> str | None:
    """The part of RomM a command line runs, or None for any other process."""
    # s6 supervisors carry their service's name, such as romm-gunicorn.
    if cmdline and os.path.basename(cmdline[0]).startswith("s6-"):
        return None
    command = " ".join(cmdline)
    return next((role for pattern, role in _ROLES if pattern.search(command)), None)


def romm_processes() -> Iterator[tuple[psutil.Process, str]]:
    """Each running RomM process with its role, skipping every other process.

    A Python child of a RomM process takes its parent's role. A reloading dev
    server runs its app in such a child, whose command line names nothing.
    """
    processes = list(psutil.process_iter(["cmdline", "ppid", "name"]))
    roles = {
        proc.pid: role
        for proc in processes
        if (role := process_role(proc.info["cmdline"] or [])) is not None
    }
    for proc in processes:
        role = roles.get(proc.pid)
        if role is None and (proc.info.get("name") or "").startswith("python"):
            role = roles.get(proc.info["ppid"])
        if role is not None:
            yield proc, role


def process_kind(role: str, pid: int, parent_role: str | None, pgid: int) -> str:
    """What a process is within its role, such as "parent" or "work_horse".

    Args:
        parent_role: The role of the process that started this one, if any.
        pgid: The process's process group ID.
    """
    if parent_role != role:
        return _FIRST_PROCESS_KIND.get(role, "main")
    if role in RQ_WORKER_ROLES:
        # RQ makes each work horse lead its own process group right after the
        # fork; the scheduler stays in its worker's group.
        return "work_horse" if pgid == pid else "scheduler"
    return "worker"


def process_kinds(processes: Sequence[tuple[psutil.Process, str]]) -> dict[int, str]:
    """The kind of each process in romm_processes(), by pid."""
    roles = {proc.pid: role for proc, role in processes}
    kinds = {}
    for proc, role in processes:
        try:
            pgid = os.getpgid(proc.pid)
        except OSError:
            pgid = -1
        kinds[proc.pid] = process_kind(
            role, proc.pid, roles.get(proc.info["ppid"]), pgid
        )
    return kinds
