from dataclasses import asdict, dataclass
from typing import Any, cast

from endpoints.responses import MissingRomsCleanupStats
from handler.database import db_collection_handler, db_rom_handler
from handler.filesystem import fs_resource_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context


@dataclass
class CleanupMissingRomsStats:
    """Statistics for missing ROMs cleanup operations."""

    platform_ids: list[int] | None = None
    roms_found: int = 0
    roms_deleted: int = 0
    errors: int = 0

    def update(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"cleanup_stats": self.to_dict()})

    def to_dict(self) -> MissingRomsCleanupStats:
        return cast(MissingRomsCleanupStats, asdict(self))


def _refresh_after_delete(rom_ids: list[int]) -> None:
    """Drop what the library caches about the deleted ROMs, as the delete endpoint does."""
    if not rom_ids:
        return
    # The rows are already gone, so a cache failure must not mask how the run ended.
    try:
        db_rom_handler.invalidate_filter_values_cache()
        db_collection_handler.refresh_smart_collections_for_roms(rom_ids)
    except Exception as e:
        log.error(f"Couldn't refresh caches after deleting ROMs {rom_ids}: {e}")


class CleanupMissingRomsTask(Task):
    def __init__(self) -> None:
        super().__init__(
            title="Cleanup missing ROMs",
            description="Delete all ROMs flagged as missing from the filesystem from the database",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(
        self, platform_ids: list[int] | None = None
    ) -> MissingRomsCleanupStats:
        """Clean up ROMs that are flagged as missing from the filesystem."""
        log.info(f"Starting {self.title} task...")

        stats = CleanupMissingRomsStats(platform_ids=platform_ids)

        filter_kwargs: dict[str, Any] = {"missing": True}
        if platform_ids:
            filter_kwargs["platform_ids"] = platform_ids

        missing_roms = db_rom_handler.get_roms_scalar(**filter_kwargs)

        stats.update(roms_found=len(missing_roms))
        log.info(
            f"Found {len(missing_roms)} missing ROM(s) to clean up"
            + (
                f" for platform ID(s) {', '.join(map(str, platform_ids))}"
                if platform_ids
                else ""
            )
        )

        deleted_ids: list[int] = []
        try:
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
                deleted_ids.append(rom.id)

                try:
                    await fs_resource_handler.remove_directory(rom.fs_resources_path)
                except FileNotFoundError:
                    log.warning(
                        f"Couldn't find resources to delete for '{rom.name or rom.fs_name}'"
                    )

                stats.update(roms_deleted=stats.roms_deleted + 1)
        finally:
            _refresh_after_delete(deleted_ids)

        log.info(
            f"Cleanup of missing ROMs completed: {stats.roms_deleted} deleted, {stats.errors} error(s)"
        )
        return stats.to_dict()


cleanup_missing_roms_task = CleanupMissingRomsTask()
