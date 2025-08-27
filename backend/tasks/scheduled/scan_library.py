from config import (
    ENABLE_SCHEDULED_RESCAN,
    FLASHPOINT_API_ENABLED,
    HASHEOUS_API_ENABLED,
    LAUNCHBOX_API_ENABLED,
    SCHEDULED_RESCAN_CRON,
)
from endpoints.sockets.scan import scan_platforms
from handler.metadata.igdb_handler import IGDB_API_ENABLED
from handler.metadata.moby_handler import MOBY_API_ENABLED
from handler.metadata.ra_handler import RA_API_ENABLED
from handler.metadata.sgdb_handler import STEAMGRIDDB_API_ENABLED
from handler.metadata.ss_handler import SS_API_ENABLED
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
            MetadataSource.IGDB: IGDB_API_ENABLED,
            MetadataSource.SS: SS_API_ENABLED,
            MetadataSource.MOBY: MOBY_API_ENABLED,
            MetadataSource.RA: RA_API_ENABLED,
            MetadataSource.LB: LAUNCHBOX_API_ENABLED,
            MetadataSource.HASHEOUS: HASHEOUS_API_ENABLED,
            MetadataSource.SGDB: STEAMGRIDDB_API_ENABLED,
            MetadataSource.FLASHPOINT: FLASHPOINT_API_ENABLED,
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
