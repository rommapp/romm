from config import (
    ENABLE_SCHEDULED_RESCAN,
    SCHEDULED_RESCAN_CRON,
)
from endpoints.sockets.scan import ScanStats, scan_platforms
from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.scan_handler import MetadataSource, ScanType
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType


class ScanLibraryTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled rescan",
            description="Rescans the entire library",
            task_type=TaskType.SCAN,
            enabled=ENABLE_SCHEDULED_RESCAN,
            manual_run=False,
            cron_string=SCHEDULED_RESCAN_CRON,
            func="tasks.scheduled.scan_library.scan_library_task.run",
        )

    async def run(self) -> dict[str, str]:
        scan_stats = ScanStats()

        if not ENABLE_SCHEDULED_RESCAN:
            log.info("Scheduled library scan not enabled, unscheduling...")
            self.unschedule()
            return scan_stats.to_dict()

        source_mapping: dict[str, bool] = {
            MetadataSource.IGDB: meta_igdb_handler.is_enabled(),
            MetadataSource.SS: meta_ss_handler.is_enabled(),
            MetadataSource.MOBY: meta_moby_handler.is_enabled(),
            MetadataSource.RA: meta_ra_handler.is_enabled(),
            MetadataSource.LAUNCHBOX: meta_launchbox_handler.is_enabled(),
            MetadataSource.HASHEOUS: meta_hasheous_handler.is_enabled(),
            MetadataSource.SGDB: meta_sgdb_handler.is_enabled(),
            MetadataSource.FLASHPOINT: meta_flashpoint_handler.is_enabled(),
            MetadataSource.HLTB: meta_hltb_handler.is_enabled(),
            MetadataSource.TGDB: meta_tgdb_handler.is_enabled(),
        }

        metadata_sources = [source for source, flag in source_mapping.items() if flag]
        if not metadata_sources:
            log.warning("No metadata sources enabled, unscheduling library scan")
            self.unschedule()
            return scan_stats.to_dict()

        log.info("Scheduled library scan started...")
        scan_stats = await scan_platforms(
            platform_ids=[],
            metadata_sources=metadata_sources,
            scan_type=ScanType.UPDATE,
        )
        log.info("Scheduled library scan done")

        return scan_stats.to_dict()


scan_library_task = ScanLibraryTask()
