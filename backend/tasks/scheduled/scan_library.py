from config import (
    ENABLE_SCHEDULED_RESCAN,
    SCHEDULED_RESCAN_CRON,
)
from endpoints.sockets.scan import scan_platforms
from handler.metadata import (
    meta_hasheous_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
)
from handler.scan_handler import MetadataSource, ScanType
from logger.logger import log
from tasks.tasks import PeriodicTask


class ScanLibraryTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled rescan",
            description="Rescans the entire library",
            enabled=ENABLE_SCHEDULED_RESCAN,
            manual_run=False,
            cron_string=SCHEDULED_RESCAN_CRON,
            func="tasks.scheduled.scan_library.scan_library_task.run",
        )

    async def run(self):
        if not ENABLE_SCHEDULED_RESCAN:
            log.info("Scheduled library scan not enabled, unscheduling...")
            self.unschedule()
            return None

        source_mapping: dict[str, bool] = {
            MetadataSource.IGDB: meta_igdb_handler.is_enabled(),
            MetadataSource.SS: meta_ss_handler.is_enabled(),
            MetadataSource.MOBY: meta_moby_handler.is_enabled(),
            MetadataSource.RA: meta_ra_handler.is_enabled(),
            MetadataSource.LB: meta_launchbox_handler.is_enabled(),
            MetadataSource.HASHEOUS: meta_hasheous_handler.is_enabled(),
            MetadataSource.SGDB: meta_sgdb_handler.is_enabled(),
        }

        metadata_sources = [source for source, flag in source_mapping.items() if flag]
        if not metadata_sources:
            log.warning("No metadata sources enabled, unscheduling library scan")
            self.unschedule()
            return None

        log.info("Scheduled library scan started...")
        await scan_platforms(
            [], scan_type=ScanType.UNIDENTIFIED, metadata_sources=metadata_sources
        )
        log.info("Scheduled library scan done")


scan_library_task = ScanLibraryTask()
