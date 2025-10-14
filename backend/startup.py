"""Startup script to run tasks before the main application is started."""

import asyncio
import os

import sentry_sdk
from opentelemetry import trace

from config import (
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    LIBRARY_BASE_PATH,
    SENTRY_DSN,
)
from config.config_manager import config_manager as cm
from handler.metadata.base_handler import (
    MAME_XML_KEY,
    METADATA_FIXTURES_DIR,
    PS1_SERIAL_INDEX_KEY,
    PS2_OPL_KEY,
    PS2_SERIAL_INDEX_KEY,
    PSP_SERIAL_INDEX_KEY,
)
from handler.redis_handler import async_cache
from logger.logger import log
from models.firmware import FIRMWARE_FIXTURES_DIR, KNOWN_BIOS_KEY
from tasks.scheduled.convert_images_to_webp import convert_images_to_webp_task
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.sync_retroachievements_progress import (
    sync_retroachievements_progress_task,
)
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from utils import get_version
from utils.cache import conditionally_set_cache
from utils.context import initialize_context

tracer = trace.get_tracer(__name__)


# TODO: Remove this in v4.5 release
def validate_library_structure() -> None:
    """Validate library structure and warn about migration needs."""
    # Check if old low-priority structure exists
    old_structure_path = f"{LIBRARY_BASE_PATH}/roms"
    if not os.path.exists(old_structure_path):
        # Check if any platform directories exist at library root (old low-priority structure)
        try:
            library_contents = os.listdir(LIBRARY_BASE_PATH)
            platform_dirs = [
                d
                for d in library_contents
                if os.path.isdir(os.path.join(LIBRARY_BASE_PATH, d))
            ]

            # Check if any of these directories contain a roms subdirectory
            old_structure_detected = False
            for platform_dir in platform_dirs:
                platform_path = os.path.join(LIBRARY_BASE_PATH, platform_dir)
                roms_path = os.path.join(platform_path, "roms")
                if os.path.exists(roms_path):
                    old_structure_detected = True
                    break

            if old_structure_detected:
                log.critical(
                    "⚠️  OLD LIBRARY STRUCTURE DETECTED ⚠️\n"
                    "RomM has detected the old low-priority library structure pattern.\n"
                    "This structure is no longer supported and must be migrated.\n\n"
                    "CURRENT STRUCTURE: {platform}/{roms}/\n"
                    "REQUIRED STRUCTURE: {roms}/{platform}/\n\n"
                    "To migrate:\n"
                    "1. Update your config.yml to specify the custom structure:\n"
                    "   filesystem:\n"
                    '     structure: "{roms}/{platform}/{game}"\n'
                    "2. Reorganize your library files to match the new structure\n"
                    "3. Restart RomM\n\n"
                    "For more information, see the migration guide in the documentation."
                )
        except (OSError, PermissionError):
            pass  # Can't read directory, skip validation


@tracer.start_as_current_span("main")
async def main() -> None:
    """Run startup tasks."""

    async with initialize_context():
        log.info("Running startup tasks")

        # Temporary check for old library structure
        validate_library_structure()

        # Validate structure patterns
        cm.validate_structures()

        # Initialize scheduled tasks
        if ENABLE_SCHEDULED_RESCAN:
            log.info("Starting scheduled rescan")
            scan_library_task.init()
        if ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
            log.info("Starting scheduled update switch titledb")
            update_switch_titledb_task.init()
        if ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA:
            log.info("Starting scheduled update launchbox metadata")
            update_launchbox_metadata_task.init()
        if ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP:
            log.info("Starting scheduled convert images to webp")
            convert_images_to_webp_task.init()
        if ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC:
            log.info("Starting scheduled RetroAchievements progress sync")
            sync_retroachievements_progress_task.init()

        log.info("Initializing cache with fixtures data")
        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )
        await conditionally_set_cache(
            async_cache, PS2_OPL_KEY, METADATA_FIXTURES_DIR / "ps2_opl_index.json"
        )
        await conditionally_set_cache(
            async_cache,
            PS1_SERIAL_INDEX_KEY,
            METADATA_FIXTURES_DIR / "ps1_serial_index.json",
        )
        await conditionally_set_cache(
            async_cache,
            PS2_SERIAL_INDEX_KEY,
            METADATA_FIXTURES_DIR / "ps2_serial_index.json",
        )
        await conditionally_set_cache(
            async_cache,
            PSP_SERIAL_INDEX_KEY,
            METADATA_FIXTURES_DIR / "psp_serial_index.json",
        )
        await conditionally_set_cache(
            async_cache, KNOWN_BIOS_KEY, FIRMWARE_FIXTURES_DIR / "known_bios_files.json"
        )

        log.info("Startup tasks completed")


if __name__ == "__main__":
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=f"romm@{get_version()}",
    )

    asyncio.run(main())
