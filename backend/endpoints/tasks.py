from endpoints.responses import MessageResponse
from fastapi import APIRouter, Request
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task
from utils.oauth import protected_route

router = APIRouter()


@protected_route(router.post, "/tasks/run", ["tasks.run"])
async def run_tasks(request: Request) -> MessageResponse:
    """Run all tasks endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        RunTasksResponse: Standard message response
    """

    await update_mame_xml_task.run()
    await update_switch_titledb_task.run()

    return {"message": "All tasks run successfully!"}
