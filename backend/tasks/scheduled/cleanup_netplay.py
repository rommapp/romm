from handler.netplay_handler import netplay_handler
from logger.logger import log
from tasks.registry import CLEANUP_NETPLAY_SPEC
from tasks.tasks import PeriodicTask


class CleanupNetplayTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(CLEANUP_NETPLAY_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        netplay_rooms = await netplay_handler.get_all()
        rooms_to_delete = [
            sid for sid, r in netplay_rooms.items() if len(r.get("players", {})) == 0
        ]
        if rooms_to_delete:
            log.info(f"Cleaning up {len(rooms_to_delete)} empty netplay rooms")
            await netplay_handler.delete(rooms_to_delete)


cleanup_netplay_task = CleanupNetplayTask()
