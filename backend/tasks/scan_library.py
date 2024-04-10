from config import ENABLE_SCHEDULED_RESCAN, SCHEDULED_RESCAN_CRON
from endpoints.sockets.scan import scan_platforms
from logger.logger import log
from tasks.tasks import PeriodicTask
from handler.scan_handler import ScanType


class ScanLibraryTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            func="tasks.scan_library.scan_library_task.run",
            description="library scan",
            enabled=ENABLE_SCHEDULED_RESCAN,
            cron_string=SCHEDULED_RESCAN_CRON,
        )

    async def run(self):
        if not ENABLE_SCHEDULED_RESCAN:
            log.info("Scheduled library scan not enabled, unscheduling...")
            self.unschedule()
            return

        log.info("Scheduled library scan started...")
        await scan_platforms([], scan_type=ScanType.UNIDENTIFIED)
        log.info("Scheduled library scan done")


scan_library_task = ScanLibraryTask()
