from handler.netplay_handler import netplay_handler
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class CleanupNetplayTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled netplay cleanup",
            description="Cleans up empty netplay rooms",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=False,
            cron_string="*/5 * * * *",  # Every 5 minutes
            func="tasks.scheduled.cleanup_netplay.cleanup_netplay_task.run",
        )

    async def run(self) -> None:
        if not self.enabled:
            self.unschedule()
            return

        netplay_rooms = await netplay_handler.get_all()
        rooms_to_delete = [
            sid for sid, r in netplay_rooms.items() if len(r.get("players", {})) == 0
        ]
        if rooms_to_delete:
            log.info(f"Cleaning up {len(rooms_to_delete)} empty netplay rooms")
            await netplay_handler.delete(rooms_to_delete)


cleanup_netplay_task = CleanupNetplayTask()
