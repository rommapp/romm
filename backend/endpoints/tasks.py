from datetime import datetime, timezone
from typing import Any, Final

from fastapi import Body, HTTPException, Request
from rq import Worker
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus
from rq.registry import FailedJobRegistry, FinishedJobRegistry

from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    TASK_RESULT_TTL,
)
from decorators.auth import protected_route
from endpoints.responses import (
    CleanupTaskStatusResponse,
    ConversionTaskStatusResponse,
    GenericTaskStatusResponse,
    ScanTaskStatusResponse,
    SyncTaskStatusResponse,
    TaskExecutionResponse,
    TaskStatusResponse,
    UpdateTaskStatusResponse,
    WatcherTaskStatusResponse,
)
from endpoints.responses.tasks import GroupedTasksDict, TaskInfo
from handler.auth.constants import Scope
from handler.redis_handler import (
    default_queue,
    get_job_func_name,
    high_prio_queue,
    low_prio_queue,
    redis_client,
    scan_queue,
)
from tasks.registry import MANUAL_TASKS, SCHEDULED_TASKS
from tasks.tasks import SCAN_DISPATCH_META_KEY, Task, TaskType, run_task_by_name
from utils.router import APIRouter

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)


# Every queue a job can be on, so the task list does not miss one.
ALL_QUEUES: Final = (scan_queue, high_prio_queue, default_queue, low_prio_queue)

# Scheduled tasks an admin can see and trigger. The rest of the catalog runs on
# its schedule without being surfaced.
VISIBLE_SCHEDULED_TASKS: Final = (
    "scan_library",
    "update_launchbox_metadata",
    "update_switch_titledb",
    "convert_images_to_webp",
    "cleanup_zip_cache",
    "cleanup_orphaned_resources",
)


def _build_task_info(name: str, task: Task) -> TaskInfo:
    """Builds a TaskInfo object from task details."""
    return TaskInfo(
        name=name,
        type=task.task_type,
        title=task.title,
        description=task.description,
        enabled=task.enabled,
        manual_run=task.can_run_manually,
        cron_string=task.cron_string or "",
    )


def _is_spent_scan_dispatch(job: Job) -> bool:
    """Whether a job is a scan dispatch that has already handed off.

    It carries the scan's own name, so listing it too would show one scheduled
    scan as two runs. A failed dispatch stays, because then no scan ran at all.
    """
    return (
        bool(job.get_meta().get(SCAN_DISPATCH_META_KEY))
        and job.get_status() is not JobStatus.FAILED
    )


def _build_task_status_response(
    job: Job,
) -> TaskStatusResponse:
    job_meta = job.get_meta()
    task_type = job_meta.get("task_type")
    task_name = job_meta.get("task_name") or get_job_func_name(job)

    # Convert datetime objects to ISO format strings
    created_at = job.created_at.isoformat() if job.created_at else None
    started_at = job.started_at.isoformat() if job.started_at else None
    ended_at = job.ended_at.isoformat() if job.ended_at else None
    enqueued_at = job.enqueued_at.isoformat() if job.enqueued_at else None

    common_data = {
        "task_name": task_name,
        "task_id": job.id,
        "status": job.get_status(),
        "created_at": created_at,
        "enqueued_at": enqueued_at,
        "started_at": started_at,
        "ended_at": ended_at,
    }

    if not task_type:
        return GenericTaskStatusResponse(
            task_type=TaskType.GENERIC,
            meta={},
            **common_data,  # trunk-ignore(mypy/typeddict-item)
        )

    match TaskType(task_type):
        case TaskType.SCAN:
            return ScanTaskStatusResponse(
                task_type=TaskType.SCAN,
                meta={"scan_stats": job_meta.get("scan_stats")},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.CONVERSION:
            return ConversionTaskStatusResponse(
                task_type=TaskType.CONVERSION,
                meta={"conversion_stats": job_meta.get("conversion_stats")},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.UPDATE:
            return UpdateTaskStatusResponse(
                task_type=TaskType.UPDATE,
                meta={"update_stats": job_meta.get("update_stats")},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.CLEANUP:
            return CleanupTaskStatusResponse(
                task_type=TaskType.CLEANUP,
                meta={"cleanup_stats": job_meta.get("cleanup_stats")},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.SYNC:
            return SyncTaskStatusResponse(
                task_type=TaskType.SYNC,
                meta={},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.WATCHER:
            return WatcherTaskStatusResponse(
                task_type=TaskType.WATCHER,
                meta={},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case TaskType.GENERIC:
            return GenericTaskStatusResponse(
                task_type=TaskType.GENERIC,
                meta={},
                **common_data,  # trunk-ignore(mypy/typeddict-item)
            )
        case _:
            raise ValueError(f"Invalid task type: {task_type}")


@protected_route(router.get, "", [Scope.TASKS_RUN])
async def list_tasks(request: Request) -> GroupedTasksDict:
    """List all available tasks grouped by task type.

    Args:
        request (Request): FastAPI Request object
    Returns:
        GroupedTasksDict: Dictionary with tasks grouped by their type (scheduled, manual, watcher)
    """
    # Initialize the grouped tasks dictionary
    grouped_tasks: GroupedTasksDict = {
        "scheduled": [],
        "manual": [],
        "watcher": [],
    }

    for name, task in MANUAL_TASKS.items():
        grouped_tasks["manual"].append(_build_task_info(name, task))

    for name in VISIBLE_SCHEDULED_TASKS:
        grouped_tasks["scheduled"].append(_build_task_info(name, SCHEDULED_TASKS[name]))

    # Add the adhoc watcher task
    grouped_tasks["watcher"].append(
        TaskInfo(
            name="filesystem_watcher",
            type=TaskType.WATCHER,
            title="Rescan on filesystem change",
            description=f"Runs a scan when a change is detected in the library path, with a {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minute delay",
            enabled=ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
            manual_run=False,
            cron_string="",
        )
    )

    return grouped_tasks


@protected_route(router.get, "/status", [Scope.TASKS_RUN])
async def get_tasks_status(request: Request) -> list[TaskStatusResponse]:
    """Get all active, queued, completed, and failed tasks.

    Args:
        request (Request): FastAPI Request object
    Returns:
        list[TaskStatusResponse]: List of all tasks with their current status
    """
    all_tasks: list[TaskStatusResponse] = []

    # Get currently running jobs from workers
    workers = Worker.all(connection=redis_client)
    for worker in workers:
        # A worker killed mid-job keeps pointing at it until its own
        # registration expires, and the job can be gone by then.
        try:
            current_job = worker.get_current_job()
        except NoSuchJobError:
            continue

        if current_job and not _is_spent_scan_dispatch(current_job):
            all_tasks.append(_build_task_status_response(current_job))

    # Get all jobs from the queues (including completed ones)
    for queue in ALL_QUEUES:
        for job in queue.get_jobs():
            if _is_spent_scan_dispatch(job):
                continue
            all_tasks.append(_build_task_status_response(job))

    finished_registries = [FinishedJobRegistry(queue=queue) for queue in ALL_QUEUES]
    failed_registries = [FailedJobRegistry(queue=queue) for queue in ALL_QUEUES]

    # Process finished jobs
    for registry in finished_registries:
        for job_id in registry.get_job_ids():
            try:
                job = Job.fetch(job_id, connection=redis_client)
            except NoSuchJobError:
                registry.remove(job_id)
                continue
            if _is_spent_scan_dispatch(job):
                continue
            all_tasks.append(_build_task_status_response(job))

    # Process failed jobs
    for registry in failed_registries:
        for job_id in registry.get_job_ids():
            try:
                job = Job.fetch(job_id, connection=redis_client)
            except NoSuchJobError:
                registry.remove(job_id)
                continue
            all_tasks.append(_build_task_status_response(job))

    all_tasks.sort(
        key=lambda x: x["started_at"] or x["enqueued_at"] or x["created_at"] or "",
        reverse=True,
    )

    return all_tasks


@protected_route(router.get, "/{task_id}", [Scope.TASKS_RUN])
async def get_task_by_id(request: Request, task_id: str) -> TaskStatusResponse:
    """Get the status of a task by its job ID.

    Args:
        request (Request): FastAPI Request object
        task_id (str): Job ID of the task to retrieve status for
    Returns:
        TaskStatusResponse: Task status information
    """
    try:
        job = Job.fetch(task_id, connection=low_prio_queue.connection)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Task with ID '{task_id}' not found",
        ) from e

    return _build_task_status_response(job)


TASK_KWARGS = Body(default=None)


@protected_route(router.post, "/run/{task_name}", [Scope.TASKS_RUN])
async def run_single_task(
    request: Request,
    task_name: str,
    task_kwargs: dict[str, Any] | None = TASK_KWARGS,
) -> TaskExecutionResponse:
    """Run a single task endpoint.

    Args:
        request (Request): FastAPI Request object
        task_name (str): Name of the task to run
        task_kwargs (dict | None): Optional keyword arguments forwarded to the task's run() method
    Returns:
        TaskExecutionResponse: Task execution response with details
    """
    all_tasks: dict[str, Task] = {
        **MANUAL_TASKS,
        **{name: SCHEDULED_TASKS[name] for name in VISIBLE_SCHEDULED_TASKS},
    }

    if task_name not in all_tasks:
        available_tasks = list(all_tasks.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_name}' not found, available tasks are {', '.join(available_tasks)}",
        )

    task_instance = all_tasks[task_name]
    if not task_instance.can_run_manually:
        raise HTTPException(
            status_code=400,
            detail=f"Task '{task_name}' cannot be run",
        )

    # Enqueued by name, like the scheduled runs, so the payload carries no
    # pickled task and the job is readable by whatever version picks it up. The
    # caller's arguments are nested rather than spread, so a body cannot name a
    # different task than the one this route just authorized.
    job = low_prio_queue.enqueue(
        run_task_by_name,
        kwargs={"name": task_name, "task_kwargs": task_kwargs or {}},
        job_timeout=task_instance.timeout,
        result_ttl=TASK_RESULT_TTL,
        meta={
            "task_name": task_instance.title,
            "task_type": task_instance.task_type.value,
        },
    )

    return {
        "task_name": task_instance.title,
        "task_id": job.id,
        "status": job.get_status() or JobStatus.QUEUED,
        "created_at": (
            job.created_at.isoformat()
            if job.created_at
            else datetime.now(timezone.utc).isoformat()
        ),
        "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
    }
