import os
import shutil
from dataclasses import dataclass

from config import RESOURCES_BASE_PATH
from handler.database import db_platform_handler, db_rom_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context


@dataclass
class CleanupStats:
    """Statistics for cleanup operations."""

    total_platforms: int = 0
    total_roms: int = 0
    removed_platforms: int = 0
    removed_roms: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"cleanup_stats": self.to_dict()})

    def to_dict(self) -> dict[str, int]:
        return {
            "total_platforms": self.total_platforms,
            "total_roms": self.total_roms,
            "removed_platforms": self.removed_platforms,
            "removed_roms": self.removed_roms,
        }


class CleanupOrphanedResourcesTask(Task):
    def __init__(self):
        super().__init__(
            title="Cleanup orphaned resources",
            description="Clean up orphaned resources in the ROMs directory",
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self) -> dict[str, int]:
        """Clean up orphaned resources."""
        log.info(f"Starting {self.title} task...")

        cleanup_stats = CleanupStats()
        cleanup_stats.update(cleanup_stats=cleanup_stats.to_dict())

        roms_resources_path = os.path.join(RESOURCES_BASE_PATH, "roms")
        if not os.path.exists(roms_resources_path):
            cleanup_stats.update(
                total_platforms=0, total_roms=0, removed_platforms=0, removed_roms=0
            )
            log.info("Resources path does not exist, skipping cleanup")
            return cleanup_stats.to_dict()

        existing_platforms = {
            str(platform.id) for platform in db_platform_handler.get_platforms()
        }
        log.debug(f"Found {len(existing_platforms)} platforms in database")

        # Count total platforms and ROMs for progress tracking
        platform_dirs = [
            d
            for d in os.listdir(roms_resources_path)
            if os.path.isdir(os.path.join(roms_resources_path, d))
        ]
        cleanup_stats.update(total_platforms=len(platform_dirs))

        for platform_dir in platform_dirs:
            platform_path = os.path.join(roms_resources_path, platform_dir)
            rom_dirs = [
                d
                for d in os.listdir(platform_path)
                if os.path.isdir(os.path.join(platform_path, d))
            ]
            cleanup_stats.update(total_roms=cleanup_stats.total_roms + len(rom_dirs))

        # Clean up orphaned platforms and ROMs
        for platform_dir in platform_dirs:
            platform_path = os.path.join(roms_resources_path, platform_dir)

            rom_dirs = [
                d
                for d in os.listdir(platform_path)
                if os.path.isdir(os.path.join(platform_path, d))
            ]

            # Check if platform exists in database
            if platform_dir not in existing_platforms:
                try:
                    # Remove entire platform directory if platform doesn't exist
                    shutil.rmtree(platform_path)
                    cleanup_stats.update(
                        removed_platforms=cleanup_stats.removed_platforms + 1,
                        removed_roms=cleanup_stats.removed_roms + len(rom_dirs),
                    )

                    log.info(f"Removed orphaned platform directory: {platform_dir}")
                except Exception as e:
                    log.error(
                        f"Failed to remove platform directory {platform_dir}: {e}"
                    )
                continue

            platform_id = int(platform_dir)
            existing_roms = {
                str(rom.id)
                for rom in db_rom_handler.get_roms_scalar(platform_id=platform_id)
            }
            log.debug(f"Found {len(existing_roms)} ROMs for platform {platform_id}")

            for rom_dir in rom_dirs:
                rom_path = os.path.join(platform_path, rom_dir)

                # Check if ROM exists in database
                if rom_dir not in existing_roms:
                    try:
                        # Remove ROM directory if ROM doesn't exist
                        shutil.rmtree(rom_path)
                        cleanup_stats.update(
                            removed_roms=cleanup_stats.removed_roms + 1
                        )
                        log.info(
                            f"Removed orphaned ROM directory: {platform_dir}/{rom_dir}"
                        )
                    except Exception as e:
                        log.error(
                            f"Failed to remove ROM directory {platform_dir}/{rom_dir}: {e}"
                        )

        if cleanup_stats.removed_platforms == 0 and cleanup_stats.removed_roms == 0:
            cleanup_stats.update(
                total_platforms=0, total_roms=0, removed_platforms=0, removed_roms=0
            )
            log.info("No orphaned resources found, cleanup completed!")
            return cleanup_stats.to_dict()

        log.info(
            f"Removed {cleanup_stats.removed_platforms} orphaned platforms and {cleanup_stats.removed_roms} orphaned ROMs"
        )
        log.info("Cleanup of orphaned resources completed successfully!")

        return cleanup_stats.to_dict()


cleanup_orphaned_resources_task = CleanupOrphanedResourcesTask()
