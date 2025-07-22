import os
import shutil

from config import RESOURCES_BASE_PATH
from handler.database import db_platform_handler, db_rom_handler
from logger.logger import log
from utils.context import initialize_context


class CleanupOrphanedResourcesTask:
    def __init__(self):
        self.manual_run = True
        self.title = "Cleanup orphaned resources"
        self.description = "cleanup orphaned resources"
        self.enabled = True

    @initialize_context()
    async def run(self) -> None:
        """Clean up orphaned resources."""
        log.info(f"Starting {self.title} task...")

        removed_count = 0

        roms_path = os.path.join(RESOURCES_BASE_PATH, "roms")
        if not os.path.exists(RESOURCES_BASE_PATH) or not os.path.exists(roms_path):
            log.info("Resources path does not exist, skipping cleanup")
            return

        existing_platforms = {
            str(platform.id) for platform in db_platform_handler.get_platforms()
        }
        log.debug(f"Found {len(existing_platforms)} platforms in database")

        for platform_dir in os.listdir(roms_path):
            platform_path = os.path.join(roms_path, platform_dir)
            if not os.path.isdir(platform_path):
                continue

            # Check if platform exists in database
            if platform_dir not in existing_platforms:
                try:
                    # Remove entire platform directory if platform doesn't exist
                    shutil.rmtree(platform_path)
                    removed_count += 1
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

            for rom_dir in os.listdir(platform_path):
                rom_path = os.path.join(platform_path, rom_dir)
                if not os.path.isdir(rom_path):
                    continue

                # Check if ROM exists in database
                if rom_dir not in existing_roms:
                    try:
                        # Remove ROM directory if ROM doesn't exist
                        shutil.rmtree(rom_path)
                        removed_count += 1
                        log.info(
                            f"Removed orphaned ROM directory: {platform_dir}/{rom_dir}"
                        )
                    except Exception as e:
                        log.error(
                            f"Failed to remove ROM directory {platform_dir}/{rom_dir}: {e}"
                        )

        log.info(f"Removed {removed_count} orphaned resource directories")
        log.info("Cleanup of orphaned resources completed!")


cleanup_orphaned_resources_task = CleanupOrphanedResourcesTask()
