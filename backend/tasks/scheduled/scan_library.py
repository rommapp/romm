from endpoints.sockets.scan import ScanStats, scan_platforms
from handler.scan_handler import ScanType, get_enabled_metadata_sources
from logger.logger import log
from tasks.registry import SCAN_LIBRARY_SPEC
from tasks.tasks import PeriodicTask


class ScanLibraryTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(SCAN_LIBRARY_SPEC)

    async def run(self) -> dict[str, str]:
        scan_stats = ScanStats()

        if not self.spec.enabled:
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
