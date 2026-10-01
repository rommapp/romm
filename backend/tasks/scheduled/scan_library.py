from config import (
    ENABLE_SCHEDULED_RESCAN,
    SCAN_TIMEOUT,
    SCHEDULED_RESCAN_CRON,
)
from endpoints.sockets.scan import ScanStats, scan_platforms
from handler.scan_handler import ScanType, get_enabled_metadata_sources
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class ScanLibraryTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(
            title="Scheduled rescan",
            description="Rescans the entire library",
            task_type=TaskType.SCAN,
            enabled=ENABLE_SCHEDULED_RESCAN,
            manual_run=False,
            cron_string=SCHEDULED_RESCAN_CRON,
            # A library scan is not a five-minute task like the rest.
            timeout=SCAN_TIMEOUT,
        )

    async def run(self) -> dict[str, str]:
        scan_stats = ScanStats()

        if not ENABLE_SCHEDULED_RESCAN:
            log.info("Scheduled library scan not enabled, skipping...")
            return scan_stats.to_dict()

        metadata_sources = get_enabled_metadata_sources()
        if not metadata_sources:
            log.warning("No metadata sources enabled, unscheduling library scan")
            return scan_stats.to_dict()

        log.info("Scheduled library scan started...")
        scan_stats = await scan_platforms(
            platform_ids=[],
            metadata_sources=metadata_sources,
            scan_type=ScanType.QUICK,
        )
        log.info("Scheduled library scan done")

        return scan_stats.to_dict()


scan_library_task = ScanLibraryTask()
