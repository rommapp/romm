"""Startup script to run tasks before the main application is started."""

import asyncio

import sentry_sdk
from opentelemetry import trace
from rq.exceptions import DuplicateJobError

from config import (
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    SENTRY_DSN,
    TASK_TIMEOUT,
)
from endpoints.sockets.scan import drop_stale_scheduled_scans
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
from logger.logger import log
from models.firmware import FIRMWARE_FIXTURES_DIR, KNOWN_BIOS_KEY
from tasks.manual.recompute_save_content_hashes import (
    recompute_save_content_hashes_task,
)
from tasks.scheduled.convert_images_to_webp import convert_images_to_webp_task
from tasks.tasks import run_task_by_name
from utils import get_version
from utils.cache import conditionally_set_cache
from utils.context import initialize_context

tracer = trace.get_tracer(__name__)

RECOMPUTE_SAVE_HASHES_JOB_ID = "recompute_save_content_hashes_bootstrap"
CONVERT_IMAGES_TO_WEBP_JOB_ID = "convert_images_to_webp_bootstrap"

# The names these backfills are registered under, which is what the payload
# carries rather than the task itself.
RECOMPUTE_SAVE_HASHES_TASK = "recompute_save_content_hashes"
CONVERT_IMAGES_TO_WEBP_TASK = "convert_images_to_webp"


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
        # A fixed id with unique=True settles it in one round trip, so two
        # instances starting together cannot both get past the check.
        low_prio_queue.enqueue(
            run_task_by_name,
            kwargs={"name": RECOMPUTE_SAVE_HASHES_TASK},
            job_id=RECOMPUTE_SAVE_HASHES_JOB_ID,
            unique=True,
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
    except DuplicateJobError:
        log.info(
            "recompute_save_content_hashes already queued or running from a "
            "previous restart; skipping enqueue"
        )
    except Exception:
        log.exception(
            "Failed to enqueue recompute_save_content_hashes; admins can run it manually"
        )


def _enqueue_convert_images_to_webp() -> None:
    """Backfill .webp covers when WebP conversion is enabled.

    The frontend rewrites cover URLs to .webp as soon as the feature flag is
    on, but the scheduled task only runs at its next cron time and the inline
    conversion in the resources handler only fires for covers fetched after
    enabling. Without a backfill, existing covers have no .webp sibling and
    every request 404s until the cron eventually runs."""
    try:
        low_prio_queue.enqueue(
            run_task_by_name,
            kwargs={"name": CONVERT_IMAGES_TO_WEBP_TASK},
            job_id=CONVERT_IMAGES_TO_WEBP_JOB_ID,
            unique=True,
            job_timeout=TASK_TIMEOUT,
            meta={
                "task_name": convert_images_to_webp_task.title,
                "task_type": convert_images_to_webp_task.task_type.value,
            },
        )
        log.info("Enqueued convert_images_to_webp backfill on low-priority worker")
    except DuplicateJobError:
        log.info(
            "convert_images_to_webp already queued or running from a previous "
            "restart; skipping enqueue"
        )
    except Exception:
        log.exception(
            "Failed to enqueue convert_images_to_webp; admins can run it manually"
        )


# Keys the rq-scheduler process used before scheduling moved onto RQ itself.
# Everything it held is either obsolete or now owned by the cron config, so it
# only has to be cleared once, and this can go a release or two from now.
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
            job_id.decode()
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
                redis_client.delete(*(f"rq:job:{job_id}" for job_id in orphans))

            log.info(
                f"Cleared {len(legacy_job_ids)} job(s) left behind by the old scheduler"
            )

        # The registry, the lock and the scheduler's own keys go regardless: an
        # old scheduler that never held a job still registered itself.
        redis_client.delete(*LEGACY_SCHEDULER_KEYS)
        for key in redis_client.scan_iter("rq:scheduler_instance:*"):
            redis_client.delete(key)
    except Exception:
        log.exception("Failed to clear the old scheduler's leftovers")


@tracer.start_as_current_span("main")
async def main() -> None:
    """Run startup tasks."""

    async with initialize_context():
        log.info("Running startup tasks")

        # An instance that was down for a while comes back with every rescan
        # its watcher queued still waiting, and releasing them all would run the
        # same library scan over and over.
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
