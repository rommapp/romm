from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from rq import get_current_job
from rq.exceptions import AbandonedJobError
from rq.job import Job
from rq.timeouts import JobTimeoutException

from config import TASK_RESULT_TTL, TASK_TIMEOUT
from exceptions.task_exceptions import TaskNotFoundException
from handler.redis_handler import QueuePrio, default_queue
from logger.logger import log
from utils.background_tasks import wait_for_background_tasks


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
    # Imported here because the task modules the registry resolves import this one.
    from tasks.registry import get_task

    task = get_task(name)
    if task is None:
        raise TaskNotFoundException(name)

    try:
        result = await task.run(**(task_kwargs or {}))
    finally:
        # RQ runs the job on a loop that never runs again once it returns.
        await wait_for_background_tasks()
    await _notify_task_end(name, task.spec, run_by_user_id)
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

    from tasks.registry import get_task_spec

    spec = get_task_spec(name)
    if spec is None:
        return

    if issubclass(exc_type, AbandonedJobError):
        reason = "The worker running it stopped unexpectedly"
    elif issubclass(exc_type, JobTimeoutException):
        reason = f"It ran past its {spec.timeout}s timeout"
    else:
        reason = str(exc_value) or repr(exc_value)

    try:
        # A job of its own, as this may run in the worker parent, which must not
        # load the notification stack.
        default_queue.enqueue(
            notify_task_failure, name, run_by_user_id, reason, result_ttl=0
        )
    except Exception:  # noqa: BLE001
        # Raising would stop the worker's sweep of the other orphaned jobs.
        log.error(f"Could not report failed task {job.id}", exc_info=True)


async def notify_task_failure(
    name: str, run_by_user_id: int | None, reason: str
) -> None:
    """Tell whoever ran a task, or the admins, why it failed."""
    from tasks.registry import get_task_spec

    spec = get_task_spec(name)
    if spec is not None:
        await _notify_task_end(name, spec, run_by_user_id, error=reason)


async def _notify_task_end(
    name: str, spec: "TaskSpec", run_by_user_id: int | None, error: str | None = None
) -> None:
    # A scan notifies of its own end, with the counts a task result lacks.
    if spec.task_type is TaskType.SCAN:
        return

    # Imported here because the notification schemas import this module.
    from handler.notification_handler import notify_user_or_admins
    from models.notification import NotificationKind, NotificationLevel

    data: dict[str, Any] = {"task": name, "title": spec.title}
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


class JobMetaStats(ABC):
    """Task counters mirrored into the RQ job meta under `meta_key`."""

    meta_key: ClassVar[str]

    def update(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({self.meta_key: self.to_dict()})

    @abstractmethod
    def to_dict(self) -> Mapping[str, object]: ...


class TaskType(str, Enum):
    """Enumeration of task types for categorization and UI display."""

    SCAN = "scan"
    CONVERSION = "conversion"
    CLEANUP = "cleanup"
    UPDATE = "update"
    SYNC = "sync"
    WATCHER = "watcher"
    GENERIC = "generic"


@dataclass(frozen=True)
class TaskSpec:
    """What the scheduler, the API and the worker know of a task without importing it.

    Args:
        implementation: Dotted path to the `Task` instance that runs it.
        manual_run_when_disabled: Lets an admin run it with the schedule off,
            for a task that fills a store nothing else fills.
        destructive: It deletes or rewrites library files, so running it by
            hand needs a typed confirmation.
        single_instance: A run is refused while another job of it is queued
            or running.
    """

    implementation: str
    title: str
    description: str
    task_type: TaskType
    enabled: bool = False
    manual_run: bool = False
    manual_run_when_disabled: bool = False
    destructive: bool = False
    single_instance: bool = False
    cron_string: str | None = None
    timeout: int = TASK_TIMEOUT
    result_ttl: int = TASK_RESULT_TTL
    queue_name: str = QueuePrio.LOW.value

    @property
    def can_run_manually(self) -> bool:
        """Whether an admin can trigger this task on demand."""
        return self.manual_run and (self.enabled or self.manual_run_when_disabled)

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


class Task(ABC):
    """Base class for all RQ tasks."""

    def __init__(self, spec: TaskSpec):
        self.spec = spec

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
        """Download the file, raising a failure worded for the user notified of it."""
        log.info(f"Scheduled {self.spec.description} started...")

        # Imported here because the HTTP client stack would otherwise load in
        # every process that reads the task catalog, the cron scheduler included.
        import httpx2

        from utils.context import ctx_httpx_client

        httpx_client = ctx_httpx_client.get()
        try:
            response = await httpx_client.get(self.url, timeout=120)
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise RuntimeError(
                f"{self.url} answered {exc.response.status_code}"
            ) from exc
        except httpx2.HTTPError as exc:
            reason = str(exc) or type(exc).__name__
            raise RuntimeError(f"Could not reach {self.url}: {reason}") from exc
        return response.content
