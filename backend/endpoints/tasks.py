import importlib
from pathlib import Path
from typing import Any, Dict

from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
)
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.tasks import GroupedTasksDict, TaskInfoDict
from fastapi import HTTPException, Request
from handler.auth.constants import Scope
from handler.redis_handler import low_prio_queue
from logger.logger import log
from utils.router import APIRouter

TASK_TYPES = ["scheduled", "manual"]

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)


def _get_available_tasks() -> Dict[str, Any]:
    """Automatically discover all available tasks by scanning the tasks directory."""
    tasks = {}

    for task_type in TASK_TYPES:
        tasks_dir = Path(__file__).parent.parent / "tasks" / task_type

        for task_file in tasks_dir.glob("*.py"):
            module_name = f"tasks.{task_type}.{task_file.stem}"
            try:
                module = importlib.import_module(module_name)

                # Look for task instances (variables ending with _task)
                for attr_name in dir(module):
                    if attr_name.endswith("_task") and not attr_name.startswith("_"):
                        task_instance = getattr(module, attr_name)
                        # Verify it has a run method
                        if hasattr(task_instance, "run") and callable(
                            task_instance.run
                        ):
                            # Use the task name without the _task suffix as the key
                            task_key = attr_name.replace("_task", "")
                            tasks[task_key] = task_instance

            except ImportError as e:
                log.error(f"Warning: Could not import task module {module_name}: {e}")

    return tasks


@protected_route(router.get, "", [Scope.TASKS_RUN])
async def list_tasks(request: Request) -> GroupedTasksDict:
    """List all available tasks grouped by task type.

    Args:
        request (Request): FastAPI Request object
    Returns:
        Dictionary with tasks grouped by their type (scheduled, manual, watcher)
    """
    tasks = _get_available_tasks()

    # Initialize the grouped tasks dictionary
    grouped_tasks: GroupedTasksDict = {}

    # Group tasks by type
    for task_type in TASK_TYPES:
        task_list: list[TaskInfoDict] = []
        tasks_dir = Path(__file__).parent.parent / "tasks" / task_type

        for name, instance in tasks.items():
            # Check if this task belongs to the current type by checking if it exists in the type directory
            task_file_path = tasks_dir / f"{name}.py"
            if task_file_path.exists():
                manual_run = getattr(instance, "manual_run", False)
                title = getattr(instance, "title", name.replace("_", " ").title())
                description = getattr(
                    instance, "description", "No description available"
                )
                enabled = getattr(instance, "enabled", False)
                task_info: TaskInfoDict = {
                    "name": name,
                    "manual_run": manual_run,
                    "title": title,
                    "description": description,
                    "enabled": enabled,
                    "cron_string": getattr(instance, "cron_string", ""),
                }
                task_list.append(task_info)

        if task_list:
            grouped_tasks[task_type] = task_list

    # Add the adhoc watcher task
    watcher_task: TaskInfoDict = {
        "name": "filesystem_watcher",
        "manual_run": False,
        "title": "Rescan on filesystem change",
        "description": f"Runs a scan when a change is detected in the library path, with a {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minute delay",
        "enabled": ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
        "cron_string": "",
    }
    grouped_tasks["watcher"] = [watcher_task]

    return grouped_tasks


@protected_route(router.post, "/run", [Scope.TASKS_RUN])
async def run_all_tasks(request: Request) -> MessageResponse:
    """Run all runnable tasks endpoint

    Args:
        request (Request): FastAPI Request object
    Returns:
        MessageResponse: Standard message response
    """
    tasks = _get_available_tasks()

    if not tasks:
        return {"msg": "No tasks available to run"}

    # Filter only runnable tasks
    runnable_tasks = {
        name: instance
        for name, instance in tasks.items()
        if getattr(instance, "manual_run", False)
    }

    if not runnable_tasks:
        return {"msg": "No runnable tasks available to run"}

    for task_name, task_instance in runnable_tasks.items():
        low_prio_queue.enqueue(task_instance.run)

    return {"msg": "All tasks launched. Check the worker logs for details."}


@protected_route(router.post, "/run/{task_name}", [Scope.TASKS_RUN])
async def run_single_task(request: Request, task_name: str) -> MessageResponse:
    """Run a single task endpoint.

    Args:
        request (Request): FastAPI Request object
        task_name (str): Name of the task to run
    Returns:
        MessageResponse: Standard message response
    """
    tasks = _get_available_tasks()

    if task_name not in tasks:
        available_tasks = list(tasks.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_name}' not found. Available tasks: {', '.join(available_tasks)}",
        )

    task_instance = tasks[task_name]

    # Check if task is triggerable (manual_run = True)
    if not getattr(task_instance, "manual_run", False):
        raise HTTPException(
            status_code=400,
            detail=f"Task '{task_name}' is not triggerable manually.",
        )
    low_prio_queue.enqueue(task_instance.run)
    return {"msg": f"Task '{task_name}' launched. Check the worker logs for details."}
