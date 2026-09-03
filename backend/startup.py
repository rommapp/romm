"""Startup script to run tasks before the main application is started."""

import asyncio

import sentry_sdk
from opentelemetry import trace
from rq.exceptions import DuplicateJobError
from rq.job import Job
from rq.utils import as_text

from config import ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP, SENTRY_DSN
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
from handler.redis_handler import (
    async_cache,
    default_queue,
    high_prio_queue,
    low_prio_queue,
    redis_client,
)
from handler.scan_jobs import drop_stale_scheduled_scans
from logger.logger import log
from models.firmware import FIRMWARE_FIXTURES_DIR, KNOWN_BIOS_KEY
from tasks.registry import enqueue_task
from utils import get_version
from utils.cache import conditionally_set_cache
from utils.context import initialize_context

tracer = trace.get_tracer(__name__)

RECOMPUTE_SAVE_HASHES_JOB_ID = "recompute_save_content_hashes_bootstrap"
CONVERT_IMAGES_TO_WEBP_JOB_ID = "convert_images_to_webp_bootstrap"


def _enqueue_backfill(task_name: str, job_id: str) -> None:
    """Hand a backfill to the low-priority worker and move on.

    A fixed id with unique=True settles it in one round trip, so two instances
    starting together cannot both get past the check.
    """
    try:
        enqueue_task(task_name, job_id=job_id, unique=True)
        log.info(f"Enqueued {task_name} on the low-priority worker")
    except DuplicateJobError:
        log.info(
            f"{task_name} already queued or running from a previous restart; "
            "skipping enqueue"
        )
    except Exception:
        log.exception(f"Failed to enqueue {task_name}; admins can run it manually")


def _enqueue_recompute_save_hashes_if_needed() -> None:
    """Backfill content_hash for saves uploaded before the path-resolution fix."""
    try:
        missing = db_save_handler.count_saves_missing_content_hash()
    except Exception:
        log.exception(
            "Failed to count saves with NULL content_hash; skipping auto-enqueue "
            "of recompute_save_content_hashes (admins can run it manually)"
        )
        return

    if missing == 0:
        log.debug("All saves have content_hash; skipping recompute auto-enqueue")
        return

    log.info(f"{missing} save(s) still have a NULL content_hash")
    _enqueue_backfill("recompute_save_content_hashes", RECOMPUTE_SAVE_HASHES_JOB_ID)


def _enqueue_convert_images_to_webp() -> None:
    """Backfill .webp covers when WebP conversion is enabled.

    The frontend rewrites cover URLs to .webp as soon as the flag is on, so
    without this every cover fetched before it 404s until the next cron run.
    """
    _enqueue_backfill("convert_images_to_webp", CONVERT_IMAGES_TO_WEBP_JOB_ID)


# Keys the rq-scheduler process left behind, now owned by the cron config.
LEGACY_SCHEDULED_JOBS_KEY = "rq:scheduler:scheduled_jobs"
LEGACY_SCHEDULER_KEYS = (
    LEGACY_SCHEDULED_JOBS_KEY,
    "rq:scheduler_lock",
    "rq:scheduler",
)


def _drop_legacy_scheduler_state() -> None:
    """Clear what the old scheduler left in Redis, jobs included."""
    try:
        legacy_job_ids = {
            as_text(job_id)
            for job_id in redis_client.zrange(LEGACY_SCHEDULED_JOBS_KEY, 0, -1)
        }

        if legacy_job_ids:
            # A cron job the old scheduler had already queued lives in both
            # places, and it still has to run, so only the orphans are deleted.
            queued: set[str] = set()
            for queue in (high_prio_queue, default_queue, low_prio_queue):
                queued.update(queue.get_job_ids())

            orphans = legacy_job_ids - queued
            if orphans:
                redis_client.delete(*(Job.key_for(job_id) for job_id in orphans))

            log.info(f"Cleared {len(orphans)} job(s) left behind by the old scheduler")

        # The registry, the lock and the scheduler's own keys go regardless: an
        # old scheduler that never held a job still registered itself.
        instance_keys = list(
            redis_client.scan_iter("rq:scheduler_instance:*", count=1000)
        )
        redis_client.delete(*LEGACY_SCHEDULER_KEYS, *instance_keys)
    except Exception:
        log.exception("Failed to clear the old scheduler's leftovers")


@tracer.start_as_current_span("main")
async def main() -> None:
    """Run startup tasks."""

    async with initialize_context():
        log.info("Running startup tasks")

        try:
            drop_stale_scheduled_scans()
        except Exception:
            log.exception("Failed to check for stale scheduled scans")

        _drop_legacy_scheduler_state()

        if ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP:
            _enqueue_convert_images_to_webp()

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
