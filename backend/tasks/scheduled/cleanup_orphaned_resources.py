import asyncio
import os
import shutil
from dataclasses import dataclass

from anyio import Path as AnyioPath
from rq.job import Job

from config import (
    ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES,
    RESOURCES_BASE_PATH,
    SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON,
)
from handler.database import db_platform_handler, db_rom_handler
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType, update_job_meta
from utils.context import initialize_context


def _numeric_subdirs(path: str) -> set[int]:
    """Numeric-named subdirectories of `path`, as ints."""
    try:
        with os.scandir(path) as entries:
            return {
                int(entry.name)
                for entry in entries
                if entry.name.isdigit() and entry.is_dir()
            }
    except OSError as exc:
        log.error(f"Unable to list resource directory {path}: {str(exc)}")
        return set()


def _scan_resource_dirs(roms_resources_path: str) -> dict[int, set[int]]:
    """Map each platform id on disk to the ROM ids that have a resource directory.

    `os.scandir` reports the entry type from the directory read itself, so this
    walks tens of thousands of entries without a stat call per entry.
    """
    return {
        platform_id: _numeric_subdirs(
            os.path.join(roms_resources_path, str(platform_id))
        )
        for platform_id in _numeric_subdirs(roms_resources_path)
    }


@dataclass
class CleanupStats:
    """Statistics for cleanup operations."""

    platforms_in_db: int = 0
    roms_in_db: int = 0
    platforms_in_fs: int = 0
    roms_in_fs: int = 0
    removed_fs_platforms: int = 0
    removed_fs_roms: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"cleanup_stats": self.to_dict()})

    def to_dict(self) -> dict[str, int]:
        return {
            "platforms_in_db": self.platforms_in_db,
            "roms_in_db": self.roms_in_db,
            "platforms_in_fs": self.platforms_in_fs,
            "roms_in_fs": self.roms_in_fs,
            "removed_fs_platforms": self.removed_fs_platforms,
            "removed_fs_roms": self.removed_fs_roms,
        }


class CleanupOrphanedResourcesTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Cleanup orphaned resources",
            description="Clean up orphaned resources in the ROMs directory",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=(
                SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON
                if ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES
                else None
            ),
            func="tasks.scheduled.cleanup_orphaned_resources.cleanup_orphaned_resources_task.run",
        )

    def init(self) -> Job | None:
        # `enabled` stays True for manual runs, so the absence of a cron string
        # is what drives unscheduling when the schedule is turned off.
        if not self.cron_string:
            self.unschedule()
            return None

        return super().init()

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, int]:
        """Clean up orphaned resources.

        Args:
            force: Clean up even when the database reports an empty library.
        """
        log.info(f"Starting {self.title} task...")

        cleanup_stats = CleanupStats()

        roms_resources_path = os.path.join(RESOURCES_BASE_PATH, "roms")
        roms_resources_dir = AnyioPath(roms_resources_path)
        if not await roms_resources_dir.exists():
            cleanup_stats.update()
            log.info("Resources path does not exist, skipping cleanup")
            return cleanup_stats.to_dict()

        existing_platforms: set[int] = {
            platform.id for platform in db_platform_handler.get_platforms()
        }
        existing_roms_by_platform: dict[int, set[int]] = {
            platform_id: {
                rom.id
                for rom in db_rom_handler.get_roms_scalar(platform_ids=[platform_id])
            }
            for platform_id in existing_platforms
        }
        log.debug(
            f"Found {len(existing_platforms)} platforms and {len(existing_roms_by_platform)} ROMs in database"
        )
        cleanup_stats.update(
            platforms_in_db=len(existing_platforms),
            roms_in_db=sum(len(roms) for roms in existing_roms_by_platform.values()),
        )

        # Count total platforms and ROMs for progress tracking
        rom_dirs_by_platform: dict[int, set[int]] = await asyncio.to_thread(
            _scan_resource_dirs, roms_resources_path
        )
        platform_dirs = set(rom_dirs_by_platform)

        # An empty library alongside artwork on disk is far more likely to be a
        # database that is unavailable or mid-migration than one that was really
        # emptied, and every platform directory would be removed in one pass.
        if platform_dirs and not existing_platforms and not force:
            cleanup_stats.update(platforms_in_fs=len(platform_dirs))
            log.warning(
                f"Database reports no platforms while {len(platform_dirs)} platform "
                "resource directories exist on disk, skipping cleanup. Run the task "
                "manually with `force` to clean them up anyway."
            )
            return cleanup_stats.to_dict()

        cleanup_stats.update(
            platforms_in_fs=len(platform_dirs),
            roms_in_fs=sum(len(rom_dirs) for rom_dirs in rom_dirs_by_platform.values()),
        )

        # Clean up orphaned platforms and ROMs
        for platform_dir, rom_dirs in rom_dirs_by_platform.items():
            platform_path = os.path.join(roms_resources_path, str(platform_dir))

            # Check if platform exists in database
            if platform_dir not in existing_platforms:
                try:
                    # Remove entire platform directory if platform doesn't exist
                    shutil.rmtree(platform_path)
                    cleanup_stats.update(
                        removed_fs_platforms=cleanup_stats.removed_fs_platforms + 1,
                        removed_fs_roms=cleanup_stats.removed_fs_roms + len(rom_dirs),
                    )

                    log.info(
                        f"Removed orphaned platform resource directory: {platform_dir}"
                    )
                except Exception as e:
                    log.error(
                        f"Failed to remove platform resource directory {platform_dir}: {e}"
                    )
                continue

            for rom_dir in rom_dirs:
                rom_path = os.path.join(platform_path, str(rom_dir))

                # Check if ROM exists in database
                if rom_dir not in existing_roms_by_platform[platform_dir]:
                    try:
                        # Remove ROM directory if ROM doesn't exist
                        shutil.rmtree(rom_path)
                        cleanup_stats.update(
                            removed_fs_roms=cleanup_stats.removed_fs_roms + 1
                        )
                        log.info(
                            f"Removed orphaned ROM resource directory: {platform_dir}/{rom_dir}"
                        )
                    except Exception as e:
                        log.error(
                            f"Failed to remove ROM resource directory {platform_dir}/{rom_dir}: {e}"
                        )

        if (
            cleanup_stats.removed_fs_platforms == 0
            and cleanup_stats.removed_fs_roms == 0
        ):
            log.info("No orphaned resources found, cleanup completed!")
            return cleanup_stats.to_dict()

        log.info(
            f"Removed {cleanup_stats.removed_fs_platforms} orphaned platforms and {cleanup_stats.removed_fs_roms} orphaned ROMs"
        )
        log.info("Cleanup of orphaned resources completed successfully!")

        return cleanup_stats.to_dict()


cleanup_orphaned_resources_task = CleanupOrphanedResourcesTask()
