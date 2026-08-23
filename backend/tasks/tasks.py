from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx
from rq import get_current_job

from config import TASK_TIMEOUT
from exceptions.task_exceptions import TaskNotFoundException
from logger.logger import log
from utils.context import ctx_httpx_client


async def run_task_by_name(name: str, **kwargs: Any) -> Any:
    """Run the task registered under ``name``.

    Every scheduled and manually triggered task is enqueued through here, so a
    job payload holds a name rather than a pickled task, and nothing in Redis
    depends on where the code that runs it lives.

    Args:
        name: The key the task is registered under.
        kwargs: Forwarded to the task's ``run``.

    Returns:
        Whatever the task returns.
    """
    # Imported here because the registry imports every task module, and those
    # modules import this one.
    from tasks.registry import get_task

    task = get_task(name)
    if task is None:
        raise TaskNotFoundException(name)

    return await task.run(**kwargs)


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

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any: ...


class PeriodicTask(Task, ABC):
    """Base class for tasks the cron scheduler runs on a schedule."""

    def __init__(self, *args: Any, func: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.func = func


class RemoteFilePullTask(PeriodicTask, ABC):
    """Base class for tasks that pull files from a remote URL."""

    def __init__(self, *args: Any, url: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.url = url

    async def run(self, force: bool = False) -> Any:
        if not self.enabled and not force:
            log.info(f"Scheduled {self.description} not enabled, skipping...")
            return None

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
