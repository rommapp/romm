from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx
from rq import get_current_job

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
        run_by_user_id: Who ran it by hand, notified of how it ended. A run
            nobody asked for (cron, startup) notifies the admins of a failure.

    Returns:
        Whatever the task returns.
    """
    # Imported here because the registry imports every task module, and those
    # modules import this one.
    from tasks.registry import get_task

    task = get_task(name)
    if task is None:
        raise TaskNotFoundException(name)

    try:
        result = await task.run(**(task_kwargs or {}))
    except Exception as exc:
        await _notify_task_end(name, task, run_by_user_id, error=str(exc) or repr(exc))
        raise

    await _notify_task_end(name, task, run_by_user_id)
    return result


async def _notify_task_end(
    name: str, task: "Task", run_by_user_id: int | None, error: str | None = None
) -> None:
    # A scan notifies of its own end, with the counts a task result lacks.
    if task.task_type is TaskType.SCAN:
        return

    # Imported here because the notification schemas import this module.
    from handler.notification_handler import notify, notify_admins
    from models.notification import NotificationKind, NotificationLevel

    data: dict[str, Any] = {"task": name, "title": task.title}
    if error is None:
        if run_by_user_id is not None:
            await notify(
                run_by_user_id,
                NotificationKind.TASK_COMPLETED,
                NotificationLevel.SUCCESS,
                data,
            )
        return

    data["error"] = error
    if run_by_user_id is not None:
        await notify(
            run_by_user_id, NotificationKind.TASK_FAILED, NotificationLevel.ERROR, data
        )
    else:
        await notify_admins(NotificationKind.TASK_FAILED, NotificationLevel.ERROR, data)


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
