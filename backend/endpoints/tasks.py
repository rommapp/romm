from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from fastapi import Request
from tasks.update_switch_titledb import update_switch_titledb_task
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.post, "/tasks/run", ["tasks.run"])
async def run_tasks(request: Request) -> MessageResponse:
    """Run all tasks endpoint

    Args:
        request (Request): Fastapi Request object
    Returns:
        RunTasksResponse: Standard message response
    """

    await update_switch_titledb_task.run()
    return {"msg": "All tasks ran successfully!"}


@protected_route(router.post, "/tasks/{task}/run", ["tasks.run"])
async def run_task(request: Request, task: str) -> MessageResponse:
    """Run all tasks endpoint

    Args:
        request (Request): Fastapi Request object
    Returns:
        RunTasksResponse: Standard message response
    """

    tasks = {"switch_titledb": update_switch_titledb_task}

    await tasks[task].run()
    return {"msg": f"Task {task} run successfully!"}
