from fastapi import APIRouter, Request

from utils.oauth import protected_route
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task

router = APIRouter()

@protected_route(router.post, "/tasks/run", ["tasks.run"])
async def run_tasks(request: Request):
    """Run all async tasks"""
    await update_mame_xml_task.run()
    await update_switch_titledb_task.run()

    return {"message": "All tasks run successfully!"}
