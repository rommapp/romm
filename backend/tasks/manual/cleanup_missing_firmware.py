from dataclasses import dataclass

from handler.database import db_firmware_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context


@dataclass
class CleanupMissingFirmwareStats:
    """Statistics for missing firmware cleanup operations."""

    platform_ids: list[int] | None = None
    firmware_found: int = 0
    firmware_deleted: int = 0
    errors: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"cleanup_stats": self.to_dict()})

    def to_dict(self) -> dict:
        return {
            "platform_ids": self.platform_ids,
            "firmware_found": self.firmware_found,
            "firmware_deleted": self.firmware_deleted,
            "errors": self.errors,
        }


class CleanupMissingFirmwareTask(Task):
    def __init__(self):
        super().__init__(
            title="Cleanup missing firmware",
            description="Delete all firmware flagged as missing from the filesystem from the database",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self, platform_ids: list[int] | None = None) -> dict:
        """Clean up firmware that is flagged as missing from the filesystem."""
        log.info(f"Starting {self.title} task...")

        stats = CleanupMissingFirmwareStats(platform_ids=platform_ids)

        missing_firmware = db_firmware_handler.list_firmware(
            platform_ids=platform_ids, missing=True
        )

        stats.update(firmware_found=len(missing_firmware))
        log.info(
            f"Found {len(missing_firmware)} missing firmware file(s) to clean up"
            + (
                f" for platform ID(s) {', '.join(map(str, platform_ids))}"
                if platform_ids
                else ""
            )
        )

        # The row is stale because the file is already gone, so there is
        # nothing to remove from disk here.
        for firmware in missing_firmware:
            try:
                log.info(
                    f"Deleting missing firmware '{firmware.file_name}' [ID: {firmware.id}] from database"
                )
                db_firmware_handler.delete_firmware(firmware.id)
            except Exception as e:
                log.error(f"Failed to delete missing firmware {firmware.id}: {e}")
                stats.update(errors=stats.errors + 1)
                continue

            stats.update(firmware_deleted=stats.firmware_deleted + 1)

        log.info(
            f"Cleanup of missing firmware completed: {stats.firmware_deleted} deleted, {stats.errors} error(s)"
        )
        return stats.to_dict()


cleanup_missing_firmware_task = CleanupMissingFirmwareTask()
