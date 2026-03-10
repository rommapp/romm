from dataclasses import dataclass
from typing import Any

from handler.database import db_rom_handler
from handler.filesystem import fs_resource_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context


@dataclass
class CleanupMissingRomsStats:
    """Statistics for missing ROMs cleanup operations."""

    platform_id: int | None = None
    roms_found: int = 0
    roms_deleted: int = 0
    errors: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"cleanup_stats": self.to_dict()})

    def to_dict(self) -> dict:
        return {
            "platform_id": self.platform_id,
            "roms_found": self.roms_found,
            "roms_deleted": self.roms_deleted,
            "errors": self.errors,
        }


class CleanupMissingRomsTask(Task):
    def __init__(self):
        super().__init__(
            title="Cleanup missing ROMs",
            description="Delete all ROMs flagged as missing from the filesystem from the database",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self, platform_id: int | None = None) -> dict:
        """Clean up ROMs that are flagged as missing from the filesystem."""
        log.info(f"Starting {self.title} task...")

        stats = CleanupMissingRomsStats(platform_id=platform_id)

        filter_kwargs: dict[str, Any] = {"missing": True}
        if platform_id is not None:
            filter_kwargs["platform_ids"] = [platform_id]

        missing_roms = db_rom_handler.get_roms_scalar(**filter_kwargs)

        stats.update(roms_found=len(missing_roms))
        log.info(
            f"Found {len(missing_roms)} missing ROM(s) to clean up"
            + (f" for platform ID {platform_id}" if platform_id else "")
        )

        for rom in missing_roms:
            try:
                log.info(
                    f"Deleting missing ROM '{rom.name or rom.fs_name}' [ID: {rom.id}] from database"
                )
                db_rom_handler.delete_rom(rom.id)
            except Exception as e:
                log.error(f"Failed to delete missing ROM {rom.id}: {e}")
                stats.update(errors=stats.errors + 1)
                continue

            try:
                await fs_resource_handler.remove_directory(rom.fs_resources_path)
            except FileNotFoundError:
                log.warning(
                    f"Couldn't find resources to delete for '{rom.name or rom.fs_name}'"
                )

            stats.update(roms_deleted=stats.roms_deleted + 1)

        log.info(
            f"Cleanup of missing ROMs completed: {stats.roms_deleted} deleted, {stats.errors} error(s)"
        )
        return stats.to_dict()


cleanup_missing_roms_task = CleanupMissingRomsTask()
