"""The catalog of tasks an admin can see, run, or have run on a schedule."""

from typing import Any, Final

from rq.job import Job
from rq.queue import Queue

from config import TASK_RESULT_TTL
from exceptions.task_exceptions import TaskNotFoundException
from handler.redis_handler import low_prio_queue, scan_queue
from tasks.manual.cleanup_missing_firmware import cleanup_missing_firmware_task
from tasks.manual.cleanup_missing_roms import cleanup_missing_roms_task
from tasks.manual.recompute_save_content_hashes import (
    recompute_save_content_hashes_task,
)
from tasks.manual.sync_folder_scan import sync_folder_scan_task
from tasks.scheduled.build_recommendations import build_recommendations_task
from tasks.scheduled.cleanup_netplay import cleanup_netplay_task
from tasks.scheduled.cleanup_orphaned_resources import cleanup_orphaned_resources_task
from tasks.scheduled.cleanup_upload_tmp import cleanup_upload_tmp_task
from tasks.scheduled.cleanup_zip_cache import cleanup_zip_cache_task
from tasks.scheduled.convert_images_to_webp import convert_images_to_webp_task
from tasks.scheduled.scan_library import scan_library_task
from tasks.scheduled.sync_retroachievements_progress import (
    sync_retroachievements_progress_task,
)
from tasks.scheduled.update_launchbox_metadata import update_launchbox_metadata_task
from tasks.scheduled.update_switch_titledb import update_switch_titledb_task
from tasks.sync_push_pull_task import sync_push_pull_task
from tasks.tasks import PeriodicTask, Task, run_task_by_name

# The keys are the names the API and the cron schedule address a task by, and
# they end up in the job payload, so they outlive any given release. Every task
# that runs on a schedule belongs here; which of them the API surfaces is the
# endpoint's business.
SCHEDULED_TASKS: Final[dict[str, PeriodicTask]] = {
    "scan_library": scan_library_task,
    "update_launchbox_metadata": update_launchbox_metadata_task,
    "update_switch_titledb": update_switch_titledb_task,
    "build_recommendations": build_recommendations_task,
    "convert_images_to_webp": convert_images_to_webp_task,
    "cleanup_zip_cache": cleanup_zip_cache_task,
    "cleanup_orphaned_resources": cleanup_orphaned_resources_task,
    "cleanup_netplay": cleanup_netplay_task,
    "cleanup_upload_tmp": cleanup_upload_tmp_task,
    "sync_retroachievements_progress": sync_retroachievements_progress_task,
    "sync_push_pull": sync_push_pull_task,
}

MANUAL_TASKS: Final[dict[str, Task]] = {
    "cleanup_missing_roms": cleanup_missing_roms_task,
    "cleanup_missing_firmware": cleanup_missing_firmware_task,
    "sync_folder_scan": sync_folder_scan_task,
    "recompute_save_content_hashes": recompute_save_content_hashes_task,
}


def get_task(name: str) -> Task | None:
    """Look up a task by the name it is addressed by."""
    return SCHEDULED_TASKS.get(name) or MANUAL_TASKS.get(name)


def enqueue_task(
    name: str,
    *,
    queue: Queue = low_prio_queue,
    task_kwargs: dict[str, Any] | None = None,
    **job_options: Any,
) -> Job:
    """Enqueue a registered task by name.

    Args:
        name: The key the task is registered under.
        queue: Which queue to enqueue on.
        task_kwargs: Forwarded to the task's ``run``, nested so that they cannot
            collide with the name of the task to run.
        job_options: Passed through to RQ, for a fixed job id and the like.

    Returns:
        The enqueued job.
    """
    task = get_task(name)
    if task is None:
        raise TaskNotFoundException(name)

    return queue.enqueue(
        run_task_by_name,
        kwargs={"name": name, "task_kwargs": task_kwargs or {}},
        job_timeout=task.timeout,
        result_ttl=TASK_RESULT_TTL,
        meta=task.job_meta,
        **job_options,
    )


def enqueue_scheduled_scan(name: str) -> str:
    """Put a scheduled scan on the scan queue with the abandoned-job callback.

    Cron can attach no `on_failure`, so a scan it enqueues itself is the one
    scan whose worker can die without anything telling the clients.

    Args:
        name: The key the scan task is registered under.

    Returns:
        The id of the enqueued scan job.
    """
    # Imported here because the scan module imports the task modules this one
    # pulls in.
    from endpoints.sockets.scan import report_scan_failure

    return enqueue_task(name, queue=scan_queue, on_failure=report_scan_failure).id
