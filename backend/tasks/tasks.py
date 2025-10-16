from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx
from rq import get_current_job
from rq.job import Job
from rq_scheduler import Scheduler

from config import TASK_TIMEOUT
from exceptions.task_exceptions import SchedulerException
from handler.redis_handler import low_prio_queue
from logger.logger import log
from utils.context import ctx_httpx_client

tasks_scheduler = Scheduler(queue=low_prio_queue, connection=low_prio_queue.connection)


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

    def __init__(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        enabled: bool = False,
        manual_run: bool = False,
        cron_string: str | None = None,
    ):
        self.title = title
        self.description = description or title
        self.task_type = task_type
        self.enabled = enabled
        self.manual_run = manual_run
        self.cron_string = cron_string

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any: ...


class PeriodicTask(Task, ABC):
    """Base class for periodic tasks that can be scheduled."""

    def __init__(self, *args: Any, func: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.func = func

    def _get_existing_job(self) -> Job | None:
        existing_jobs = tasks_scheduler.get_jobs()
        for job in existing_jobs:
            if isinstance(job, Job) and job.func_name == self.func:
                return job

        return None

    def init(self) -> Job | None:
        """Initialize the task by scheduling or unscheduling it based on its state.

        Returns the scheduled job if it was successfully scheduled, or None if it was already
        scheduled or unscheduled.
        """
        job = self._get_existing_job()

        if self.enabled and not job:
            return self.schedule()
        elif job and not self.enabled:
            self.unschedule()
            return None
        return None

    def schedule(self) -> Job | None:
        """Schedule the task if it is enabled and not already scheduled.

        Returns the scheduled job if successful, or None otherwise.
        """
        if not self.enabled:
            raise SchedulerException(f"Scheduled {self.description} is not enabled.")

        if self._get_existing_job():
            log.info(f"{self.description.capitalize()} is already scheduled.")
            return None

        if self.cron_string:
            return tasks_scheduler.cron(
                self.cron_string,
                func=self.func,
                repeat=None,
                timeout=TASK_TIMEOUT,
                meta={
                    "task_name": self.title,
                    "task_type": self.task_type.value,
                },
            )

        return None

    def unschedule(self) -> bool:
        """Unschedule the task if it is currently scheduled.

        Returns whether the unscheduling was successful.
        """
        job = self._get_existing_job()
        if not job:
            log.info(f"{self.description.capitalize()} is not scheduled.")
            return False

        tasks_scheduler.cancel(job)
        log.info(f"{self.description.capitalize()} unscheduled.")
        return True


class RemoteFilePullTask(PeriodicTask, ABC):
    """Base class for tasks that pull files from a remote URL."""

    def __init__(self, *args: Any, url: str, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.url = url

    async def run(self, force: bool = False) -> Any:
        if not self.enabled and not force:
            log.info(f"Scheduled {self.description} not enabled, unscheduling...")
            self.unschedule()
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
