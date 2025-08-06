from datetime import datetime, timezone

from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
)
from decorators.auth import protected_route
from endpoints.responses import TaskExecutionResponse, TaskStatusResponse
from endpoints.responses.tasks import GroupedTasksDict, TaskInfo
from fastapi import HTTPException, Request
from handler.auth.constants import Scope
from handler.redis_handler import low_prio_queue
from rq.job import Job
from tasks.manual.cleanup_orphaned_resources import cleanup_orphaned_resources_task
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from tasks.tasks import Task
from utils.router import APIRouter

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)

scheduled_tasks: dict[str, Task] = {
    "scan_library": scan_library_task,
    "update_launchbox_metadata": update_launchbox_metadata_task,
    "update_switch_titledb": update_switch_titledb_task,
}

manual_tasks: dict[str, Task] = {
    "cleanup_orphaned_resources": cleanup_orphaned_resources_task,
}


def _build_task_info(name: str, task: Task) -> TaskInfo:
    """Builds a TaskInfo object from task details."""
    return TaskInfo(
        name=name,
        title=task.title,
        description=task.description,
        enabled=task.enabled,
        manual_run=task.manual_run,
        cron_string=task.cron_string or "",
    )


@protected_route(router.get, "", [Scope.TASKS_RUN])
async def list_tasks(request: Request) -> GroupedTasksDict:
    """List all available tasks grouped by task type.

    Args:
        request (Request): FastAPI Request object
    Returns:
        Dictionary with tasks grouped by their type (scheduled, manual, watcher)
    """
    # Initialize the grouped tasks dictionary
    grouped_tasks: GroupedTasksDict = {
        "scheduled": [],
        "manual": [],
        "watcher": [],
    }

    for name, task in manual_tasks.items():
        grouped_tasks["manual"].append(_build_task_info(name, task))

    for name, task in scheduled_tasks.items():
        grouped_tasks["scheduled"].append(_build_task_info(name, task))

    # Add the adhoc watcher task
    grouped_tasks["watcher"].append(
        TaskInfo(
            name="filesystem_watcher",
            title="Rescan on filesystem change",
            description=f"Runs a scan when a change is detected in the library path, with a {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minute delay",
            enabled=ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
            manual_run=False,
            cron_string="",
        )
    )

    return grouped_tasks


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

    # Convert datetime objects to ISO format strings
    queued_at = job.created_at.isoformat() if job.created_at else None
    started_at = job.started_at.isoformat() if job.started_at else None
    ended_at = job.ended_at.isoformat() if job.ended_at else None

    # Get task name from job metadata or function name
    task_name = (
        job.meta.get("task_name") or job.func_name if job.meta else job.func_name
    )

    return TaskStatusResponse(
        task_name=str(task_name),
        task_id=task_id,
        status=job.get_status(),
        queued_at=queued_at or "",
        started_at=started_at,
        ended_at=ended_at,
    )


@protected_route(router.post, "/run", [Scope.TASKS_RUN])
async def run_all_tasks(request: Request) -> list[TaskExecutionResponse]:
    """Run all runnable tasks endpoint

    Args:
        request (Request): FastAPI Request object
    Returns:
        TaskExecutionResponse: Task execution response with details
    """
    # Filter only runnable tasks
    runnable_tasks = {
        name: task
        for name, task in {**manual_tasks, **scheduled_tasks}.items()
        if task.enabled and task.manual_run
    }

    if not runnable_tasks:
        raise HTTPException(
            status_code=400,
            detail="No runnable tasks available to run",
        )

    jobs = [
        (task_name, low_prio_queue.enqueue(task_instance.run))
        for task_name, task_instance in runnable_tasks.items()
    ]

    return [
        {
            "task_name": task_name,
            "task_id": job.get_id(),
            "status": job.get_status(),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        for (task_name, job) in jobs
    ]


@protected_route(router.post, "/run/{task_name}", [Scope.TASKS_RUN])
async def run_single_task(request: Request, task_name: str) -> TaskExecutionResponse:
    """Run a single task endpoint.

    Args:
        request (Request): FastAPI Request object
        task_name (str): Name of the task to run
    Returns:
        TaskExecutionResponse: Task execution response with details
    """
    all_tasks = {**manual_tasks, **scheduled_tasks}

    if task_name not in all_tasks:
        available_tasks = list(all_tasks.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_name}' not found, available tasks are {', '.join(available_tasks)}",
        )

    task_instance = all_tasks[task_name]
    if not task_instance.enabled or not task_instance.manual_run:
        raise HTTPException(
            status_code=400,
            detail=f"Task '{task_name}' cannot be run",
        )

    job = low_prio_queue.enqueue(task_instance.run)

    return {
        "task_name": task_name,
        "task_id": job.get_id(),
        "status": job.get_status(),
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
