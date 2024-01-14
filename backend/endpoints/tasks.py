from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from fastapi import APIRouter, Request
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task

router = APIRouter()


@protected_route(router.post, "/tasks", ["tasks.run"])
async def run_tasks(request: Request, action: str) -> MessageResponse:
    """Run all tasks endpoint

    Args:
        request (Request): Fastapi Request object
        action: Action to perform on tasks
    Returns:
        RunTasksResponse: Standard message response
    """

    if action == "run":
        await update_mame_xml_task.run()
        await update_switch_titledb_task.run()
        return {"msg": f"All tasks {action} successfully!"}
    
    return {"msg": "No action performed on tasks"}


@protected_route(router.post, "/tasks/{task}", ["tasks.run"])
async def run_task(request: Request, task: str, action: str) -> MessageResponse:
    """Run all tasks endpoint

    Args:
        request (Request): Fastapi Request object
        action: Action to perform on tasks
    Returns:
        RunTasksResponse: Standard message response
    """

    tasks = {
        "mame": update_mame_xml_task,
        "switch_titledb": update_switch_titledb_task 
    }
 
    if action == "run":
        await tasks[task].run()
        return {"msg": f"Task {task} {action} successfully!"}
    
    return {"msg": "No action performed on task {task}"}