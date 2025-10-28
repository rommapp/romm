import enum
import json
import os
from collections.abc import Sequence
from datetime import timedelta
from typing import cast

import sentry_sdk
from opentelemetry import trace
from rq import Worker
from rq.job import Job, JobStatus

from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    LIBRARY_BASE_PATH,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    SCAN_TIMEOUT,
    SENTRY_DSN,
    TASK_RESULT_TTL,
)
from config.config_manager import config_manager as cm
from endpoints.sockets.scan import scan_platforms
from handler.database import db_platform_handler
from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.redis_handler import low_prio_queue, redis_client
from handler.scan_handler import MetadataSource, ScanType
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from tasks.tasks import TaskType, tasks_scheduler
from utils import get_version

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)
tracer = trace.get_tracer(__name__)

structure_level = 2 if os.path.exists(cm.get_config().HIGH_PRIO_STRUCTURE_PATH) else 1


@enum.unique
class EventType(enum.StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


VALID_EVENTS = frozenset(
    (
        EventType.ADDED,
        EventType.DELETED,
    )
)

# A change is a tuple representing a file change, first element is the event type, second is the
# path of the file or directory that changed.
Change = tuple[EventType, str]


def get_pending_scan_jobs() -> list[Job]:
    """Get all pending scan jobs (scheduled, queued, or running) for scan_platforms function.

    Returns:
        list[Job]: List of pending scan jobs that are not completed or failed
    """
    pending_jobs = []

    # Get jobs from the scheduler (delayed/scheduled jobs)
    scheduled_jobs = tasks_scheduler.get_jobs()
    for job in scheduled_jobs:
        if (
            isinstance(job, Job)
            and job.func_name == "endpoints.sockets.scan.scan_platforms"
            and job.get_status()
            in [JobStatus.SCHEDULED, JobStatus.QUEUED, JobStatus.STARTED]
        ):
            pending_jobs.append(job)

    # Get jobs from the queue (immediate jobs)
    queue_jobs = low_prio_queue.get_jobs()
    for job in queue_jobs:
        if (
            isinstance(job, Job)
            and job.func_name == "endpoints.sockets.scan.scan_platforms"
            and job.get_status() in [JobStatus.QUEUED, JobStatus.STARTED]
        ):
            pending_jobs.append(job)

    # Get currently running jobs from workers
    workers = Worker.all(connection=redis_client)
    for worker in workers:
        current_job = worker.get_current_job()
        if (
            current_job
            and current_job.func_name == "endpoints.sockets.scan.scan_platforms"
            and current_job.get_status() == JobStatus.STARTED
        ):
            pending_jobs.append(current_job)

    return pending_jobs


def process_changes(changes: Sequence[Change]) -> None:
    if not ENABLE_RESCAN_ON_FILESYSTEM_CHANGE:
        return

    # Filter for valid events
    changes = [change for change in changes if change[0] in VALID_EVENTS]
    if not changes:
        return

    with tracer.start_as_current_span("process_changes"):
        # Find affected platform slugs
        fs_slugs: set[str] = set()
        changes_platform_directory = False
        for change in changes:
            event_type, change_path = change
            src_path = os.fsdecode(change_path)
            event_src = src_path.split(LIBRARY_BASE_PATH)[-1]
            event_src_parts = event_src.split("/")
            if len(event_src_parts) <= structure_level:
                log.warning(
                    f"Filesystem event path '{event_src}' does not have enough segments for structure_level {structure_level}. Skipping event."
                )
                continue

            if len(event_src_parts) == structure_level + 1:
                changes_platform_directory = True

            log.info(f"Filesystem event: {event_type} {event_src}")
            fs_slugs.add(event_src_parts[structure_level])

        if not fs_slugs:
            log.info("No valid filesystem slugs found in changes, exiting...")
            return

        # Check whether any metadata source is enabled
        source_mapping: dict[str, bool] = {
            MetadataSource.IGDB: meta_igdb_handler.is_enabled(),
            MetadataSource.SS: meta_ss_handler.is_enabled(),
            MetadataSource.MOBY: meta_moby_handler.is_enabled(),
            MetadataSource.RA: meta_ra_handler.is_enabled(),
            MetadataSource.LAUNCHBOX: meta_launchbox_handler.is_enabled(),
            MetadataSource.HASHEOUS: meta_hasheous_handler.is_enabled(),
            MetadataSource.SGDB: meta_sgdb_handler.is_enabled(),
            MetadataSource.FLASHPOINT: meta_flashpoint_handler.is_enabled(),
            MetadataSource.HLTB: meta_hltb_handler.is_enabled(),
            MetadataSource.TGDB: meta_tgdb_handler.is_enabled(),
        }
        metadata_sources = [source for source, flag in source_mapping.items() if flag]
        if not metadata_sources:
            log.warning("No metadata sources enabled, skipping rescan")
            return

        # Get currently pending scan jobs (scheduled, queued, or running)
        pending_jobs = get_pending_scan_jobs()

        # If a full rescan is already scheduled, skip further processing
        full_rescan_jobs = [
            job for job in pending_jobs if job.args and job.args[0] == []
        ]
        if full_rescan_jobs:
            log.info(f"Full rescan already scheduled ({len(full_rescan_jobs)} job(s))")
            return

        time_delta = timedelta(minutes=RESCAN_ON_FILESYSTEM_CHANGE_DELAY)
        rescan_in_msg = f"rescanning in {hl(str(RESCAN_ON_FILESYSTEM_CHANGE_DELAY), color=CYAN)} minutes."

        # Any change to a platform directory should trigger a full rescan
        if changes_platform_directory:
            log.info(f"Platform directory changed, {rescan_in_msg}")
            tasks_scheduler.enqueue_in(
                time_delta,
                scan_platforms,
                platform_ids=[],
                metadata_sources=metadata_sources,
                scan_type=ScanType.UPDATE,
                timeout=SCAN_TIMEOUT,
                job_result_ttl=TASK_RESULT_TTL,
                meta={
                    "task_name": "Unidentified Scan",
                    "task_type": TaskType.SCAN,
                },
            )
            return

        # Otherwise, process each platform slug
        for fs_slug in fs_slugs:
            # TODO: Query platforms from the database in bulk
            db_platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if not db_platform:
                continue

            # Skip if a scan is already scheduled for this platform
            platform_scan_jobs = [
                job
                for job in pending_jobs
                if job.args and db_platform.id in job.args[0]
            ]
            if platform_scan_jobs:
                log.info(
                    f"Scan already scheduled for {hl(fs_slug)} ({len(platform_scan_jobs)} job(s))"
                )
                continue

            log.info(f"Change detected in {hl(fs_slug)} folder, {rescan_in_msg}")
            tasks_scheduler.enqueue_in(
                time_delta,
                scan_platforms,
                platform_ids=[db_platform.id],
                metadata_sources=metadata_sources,
                scan_type=ScanType.QUICK,
                timeout=SCAN_TIMEOUT,
                job_result_ttl=TASK_RESULT_TTL,
                meta={
                    "task_name": "Quick Scan",
                    "task_type": TaskType.SCAN,
                },
            )


if __name__ == "__main__":
    changes = cast(list[Change], json.loads(os.getenv("WATCHFILES_CHANGES", "[]")))
    if changes:
        process_changes(changes)
