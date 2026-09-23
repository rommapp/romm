import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx
from rq import get_current_job
from rq.exceptions import AbandonedJobError
from rq.job import Job
from rq.timeouts import JobTimeoutException

from config import TASK_TIMEOUT
from exceptions.task_exceptions import TaskNotFoundException
from logger.logger import log
from utils.context import ctx_httpx_client


async def run_task_by_name(
    name: str,
    task_kwargs: dict[str, Any] | None = None,
    run_by_user_id: int | None = None,
) -> Any:
    """Run the task registered under ``name``.

    Every scheduled and manually triggered task is enqueued through here, so a
    job payload holds a name rather than a pickled task, and nothing in Redis
    depends on where the code that runs it lives.

    Args:
        name: The key the task is registered under.
        task_kwargs: Forwarded to the task's ``run``, nested so that they cannot
            collide with the name of the task to run.
        run_by_user_id: Who ran it by hand, notified when it succeeds. A failure
            is reported by `report_task_failure`.

    Returns:
        Whatever the task returns.
    """
    # Imported here because the registry imports every task module, and those
    # modules import this one.
    from tasks.registry import get_task

    task = get_task(name)
    if task is None:
        raise TaskNotFoundException(name)

    result = await task.run(**(task_kwargs or {}))
    await _notify_task_end(name, task, run_by_user_id)
    return result


def report_task_failure(
    job: Job, exc_type: type[BaseException], exc_value: BaseException, tb: Any
) -> None:
    """RQ exception handler telling whoever ran a task, or the admins, that it failed.

    The worker calls it for a timeout parked in the event loop and for a job a
    dead worker orphaned too, neither of which unwinds through the task.
    """
    try:
        if job.func_name != f"{__name__}.{run_task_by_name.__name__}":
            return
        name = job.kwargs["name"]
        run_by_user_id = job.kwargs.get("run_by_user_id")
    except Exception:  # noqa: BLE001 - a job that won't deserialize is RQ's to log
        return

    from tasks.registry import get_task

    task = get_task(name)
    if task is None:
        return

    if issubclass(exc_type, AbandonedJobError):
        reason = "The worker running it stopped unexpectedly"
    elif issubclass(exc_type, JobTimeoutException):
        reason = f"It ran past its {task.timeout}s timeout"
    else:
        reason = str(exc_value) or repr(exc_value)

    try:
        asyncio.run(_notify_task_end(name, task, run_by_user_id, error=reason))
    except Exception:  # noqa: BLE001
        # Raising would stop the worker's sweep of the other orphaned jobs.
        log.error(f"Could not report failed task {job.id}", exc_info=True)


async def _notify_task_end(
    name: str, task: "Task", run_by_user_id: int | None, error: str | None = None
) -> None:
    # A scan notifies of its own end, with the counts a task result lacks.
    if task.task_type is TaskType.SCAN:
        return

    # Imported here because the notification schemas import this module.
    from handler.notification_handler import notify_user_or_admins
    from models.notification import NotificationKind, NotificationLevel

    data: dict[str, Any] = {"task": name, "title": task.title}
    if error is None:
        await notify_user_or_admins(
            run_by_user_id,
            NotificationKind.TASK_COMPLETED,
            NotificationLevel.SUCCESS,
            data,
            admins_too=False,
        )
    else:
        await notify_user_or_admins(
            run_by_user_id,
            NotificationKind.TASK_FAILED,
            NotificationLevel.ERROR,
            {**data, "error": error},
            admins_too=True,
        )


def update_job_meta(metadata: dict[str, Any]) -> None:
    """Update the current RQ job's meta data with update stats information"""
    try:
        current_job = get_current_job()
        if current_job:
            current_job.meta.update(metadata)
            current_job.save_meta()
    except Exception as e:
        # Silently fail if we can't update meta (e.g., not running in RQ context)
        log.debug(f"Could not update job meta: {e}")


class TaskType(str, Enum):
    """Enumeration of task types for categorization and UI display."""

    SCAN = "scan"
    CONVERSION = "conversion"
    CLEANUP = "cleanup"
    UPDATE = "update"
    SYNC = "sync"
    WATCHER = "watcher"
    GENERIC = "generic"


class Task(ABC):
    """Base class for all RQ tasks."""

    title: str
    description: str
    enabled: bool
    manual_run: bool
    cron_string: str | None = None
    task_type: TaskType
    timeout: int

    def __init__(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        enabled: bool = False,
        manual_run: bool = False,
        cron_string: str | None = None,
        timeout: int = TASK_TIMEOUT,
    ):
        self.title = title
        self.description = description or title
        self.task_type = task_type
        self.enabled = enabled
        self.manual_run = manual_run
        self.cron_string = cron_string
        self.timeout = timeout

    @property
    def can_run_manually(self) -> bool:
        """Whether an admin can trigger this task on demand."""
        return self.manual_run and self.enabled

    def job_meta(self, key: str) -> dict[str, Any]:
        """What a job of this task carries so the API can describe it.

        Args:
            key: The name the task is registered under, which outlives its title.
        """
        return {
            "task_key": key,
            "task_name": self.title,
            "task_type": self.task_type.value,
        }

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any: ...


class PeriodicTask(Task, ABC):
    """Base class for tasks the cron scheduler runs on a schedule."""


class RemoteFilePullTask(PeriodicTask, ABC):
    """Base class for tasks that pull files from a remote URL."""

    def __init__(self, *args: Any, url: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.url = url

    async def run(self) -> Any:
        log.info(f"Scheduled {self.description} started...")

        httpx_client = ctx_httpx_client.get()
        try:
            response = await httpx_client.get(self.url, timeout=120)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            log.error(f"Scheduled {self.description} failed", exc_info=True)
            log.error(e)
            return None
