"""Startup script to run tasks before the main application is started."""

import asyncio

import sentry_sdk
from opentelemetry import trace

from config import (
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    ENABLE_SYNC_PUSH_PULL,
    SENTRY_DSN,
    TASK_TIMEOUT,
)
from handler.database import db_save_handler
from handler.metadata.base_handler import (
    MAME_XML_KEY,
    METADATA_FIXTURES_DIR,
    PS1_SERIAL_INDEX_KEY,
    PS2_OPL_KEY,
    PS2_SERIAL_INDEX_KEY,
    PSP_SERIAL_INDEX_KEY,
    SCUMMVM_INDEX_KEY,
)
from handler.redis_handler import async_cache, low_prio_queue
from logger.logger import log
from models.firmware import FIRMWARE_FIXTURES_DIR, KNOWN_BIOS_KEY
from tasks.manual.recompute_save_content_hashes import (
    recompute_save_content_hashes_task,
)
from tasks.scheduled.cleanup_netplay import cleanup_netplay_task
from tasks.scheduled.cleanup_upload_tmp import cleanup_upload_tmp_task
from tasks.scheduled.convert_images_to_webp import convert_images_to_webp_task
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.sync_retroachievements_progress import (
    sync_retroachievements_progress_task,
)
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from tasks.sync_push_pull_task import sync_push_pull_task
from utils import get_version
from utils.cache import conditionally_set_cache
from utils.context import initialize_context

tracer = trace.get_tracer(__name__)


def _enqueue_recompute_save_hashes_if_needed() -> None:
    """Backfill content_hash for saves uploaded before the path-resolution
    fix. Non-blocking: a single COUNT query, then -- only if any Save rows
    still have NULL content_hash -- enqueue the manual recompute task on
    the low-priority RQ queue. The worker process picks it up; this
    process moves on. Once the run completes, future restarts see 0 NULL
    hashes and skip. Admins can still trigger the manual task explicitly."""
    try:
        missing = db_save_handler.count_saves_missing_content_hash()
    except Exception:
        log.exception(
            "Failed to count saves with NULL content_hash; "
            "skipping auto-enqueue of recompute_save_content_hashes (admins can run it manually)"
        )
        return

    if missing == 0:
        log.debug("All saves have content_hash; skipping recompute auto-enqueue")
        return

    try:
        low_prio_queue.enqueue(
            recompute_save_content_hashes_task.run,
            job_timeout=TASK_TIMEOUT,
            meta={
                "task_name": recompute_save_content_hashes_task.title,
                "task_type": recompute_save_content_hashes_task.task_type.value,
            },
        )
        log.info(
            f"Enqueued recompute_save_content_hashes ({missing} saves with NULL content_hash); "
            "running on low-priority worker"
        )
    except Exception:
        log.exception(
            "Failed to enqueue recompute_save_content_hashes; admins can run it manually"
        )


@tracer.start_as_current_span("main")
async def main() -> None:
    """Run startup tasks."""

    async with initialize_context():
        log.info("Running startup tasks")

        # Initialize scheduled tasks
        cleanup_netplay_task.init()
        cleanup_upload_tmp_task.init()

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
        if ENABLE_SYNC_PUSH_PULL:
            log.info("Starting scheduled push-pull sync")
            sync_push_pull_task.init()

        _enqueue_recompute_save_hashes_if_needed()

        log.info("Initializing cache with fixtures data")
        await conditionally_set_cache(
            async_cache, MAME_XML_KEY, METADATA_FIXTURES_DIR / "mame_index.json"
        )
        await conditionally_set_cache(
            async_cache,
            SCUMMVM_INDEX_KEY,
            METADATA_FIXTURES_DIR / "scummvm_index.json",
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
