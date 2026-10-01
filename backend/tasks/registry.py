"""The catalog of tasks, kept free of task code so scheduling or listing them imports none."""

from typing import Any, Final, cast

from rq.job import Callback, Job
from rq.queue import Queue
from rq.utils import import_attribute

from config import (
    AUDIT_LOG_RETENTION_DAYS,
    ENABLE_SCHEDULED_BUILD_RECOMMENDATIONS,
    ENABLE_SCHEDULED_CLEANUP_NETPLAY,
    ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES,
    ENABLE_SCHEDULED_CLEANUP_SYNC_SESSIONS,
    ENABLE_SCHEDULED_CLEANUP_UPLOAD_TMP,
    ENABLE_SCHEDULED_CLEANUP_ZIP_CACHE,
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    ENABLE_SYNC_FOLDER_WATCHER,
    ENABLE_SYNC_PUSH_PULL,
    LAUNCHBOX_API_ENABLED,
    SCAN_TIMEOUT,
    SCHEDULED_BUILD_RECOMMENDATIONS_CRON,
    SCHEDULED_CLEANUP_NETPLAY_CRON,
    SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON,
    SCHEDULED_CLEANUP_SYNC_SESSIONS_CRON,
    SCHEDULED_CLEANUP_UPLOAD_TMP_CRON,
    SCHEDULED_CLEANUP_ZIP_CACHE_CRON,
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
    SYNC_PUSH_PULL_CRON,
    TASK_TIMEOUT,
)
from exceptions.task_exceptions import TaskNotFoundException
from handler.redis_handler import QUEUES_BY_NAME, STREAMING_QUEUE_NAME, scan_queue
from handler.streaming.config import HOLD_CEILING_SECONDS, streaming_enabled
from tasks.tasks import Task, TaskSpec, TaskType, run_task_by_name

SCAN_LIBRARY_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.scan_library.scan_library_task",
    title="Scheduled rescan",
    description="Rescans the entire library",
    task_type=TaskType.SCAN,
    enabled=ENABLE_SCHEDULED_RESCAN,
    cron_string=SCHEDULED_RESCAN_CRON,
    # A library scan is not a five-minute task like the rest.
    timeout=SCAN_TIMEOUT,
)

UPDATE_LAUNCHBOX_METADATA_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.update_launchbox_metadata.update_launchbox_metadata_task",
    title="Scheduled LaunchBox metadata update",
    description="Updates the LaunchBox metadata store",
    task_type=TaskType.UPDATE,
    enabled=ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    cron_string=SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
    manual_run=True,
    # The store lives only in the cache, so with LaunchBox on admins must be
    # able to fill it even while the scheduled update is off.
    manual_run_when_disabled=LAUNCHBOX_API_ENABLED,
    # Downloading ~100MB and parsing it takes far longer than an ordinary task.
    timeout=max(TASK_TIMEOUT, 30 * 60),
)

UPDATE_SWITCH_TITLEDB_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.update_switch_titledb.update_switch_titledb_task",
    title="Scheduled Switch TitleDB update",
    description="Updates the Nintendo Switch TitleDB file",
    task_type=TaskType.UPDATE,
    enabled=ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    cron_string=SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
    manual_run=True,
    # The store lives only in the cache, and a rebuild that fails is not queued
    # again, so admins need a way to fill it with the cron off.
    manual_run_when_disabled=True,
)

BUILD_RECOMMENDATIONS_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.build_recommendations.build_recommendations_task",
    title="Build recommendations index",
    description=(
        "Rebuilds the similar-games index from library metadata, "
        "play history and collections"
    ),
    task_type=TaskType.UPDATE,
    enabled=ENABLE_SCHEDULED_BUILD_RECOMMENDATIONS,
    manual_run=True,
    cron_string=SCHEDULED_BUILD_RECOMMENDATIONS_CRON,
)

CONVERT_IMAGES_TO_WEBP_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.convert_images_to_webp.convert_images_to_webp_task",
    title="Convert images to WebP",
    description="Convert existing image files (PNG, JPG, BMP, TIFF, GIF) to WebP format for better performance",
    task_type=TaskType.CONVERSION,
    enabled=ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    manual_run=True,
    cron_string=SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
)

CLEANUP_ZIP_CACHE_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_zip_cache.cleanup_zip_cache_task",
    title="Scheduled ZIP cache cleanup",
    description="Removes stale cached ZIP files based on tiered TTL",
    task_type=TaskType.CLEANUP,
    enabled=ENABLE_SCHEDULED_CLEANUP_ZIP_CACHE,
    cron_string=SCHEDULED_CLEANUP_ZIP_CACHE_CRON,
)

CLEANUP_CONVERSION_CACHE_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_conversion_cache.cleanup_conversion_cache_task",
    title="Scheduled conversion cache cleanup",
    description="Removes stale converted download files based on TTL",
    task_type=TaskType.CLEANUP,
    enabled=True,
    cron_string="0 4 * * *",
)

CLEANUP_ORPHANED_RESOURCES_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_orphaned_resources.cleanup_orphaned_resources_task",
    title="Cleanup orphaned resources",
    description="Clean up orphaned resources in the ROMs directory",
    task_type=TaskType.CLEANUP,
    enabled=ENABLE_SCHEDULED_CLEANUP_ORPHANED_RESOURCES,
    manual_run=True,
    cron_string=SCHEDULED_CLEANUP_ORPHANED_RESOURCES_CRON,
)

CLEANUP_NETPLAY_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_netplay.cleanup_netplay_task",
    title="Scheduled netplay cleanup",
    description="Cleans up empty netplay rooms",
    task_type=TaskType.CLEANUP,
    enabled=ENABLE_SCHEDULED_CLEANUP_NETPLAY,
    cron_string=SCHEDULED_CLEANUP_NETPLAY_CRON,
)

CLEANUP_UPLOAD_TMP_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_upload_tmp.cleanup_upload_tmp_task",
    title="Scheduled upload tmp cleanup",
    description="Cleans up orphaned chunked-upload temp directories",
    task_type=TaskType.CLEANUP,
    enabled=ENABLE_SCHEDULED_CLEANUP_UPLOAD_TMP,
    cron_string=SCHEDULED_CLEANUP_UPLOAD_TMP_CRON,
)

REAP_STREAMING_SESSIONS_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.reap_streaming_sessions.reap_streaming_sessions_task",
    title="Scheduled streaming session reaper",
    description="Stops streaming sessions whose player stopped sending heartbeats",
    task_type=TaskType.CLEANUP,
    # Read once, as cron registers only enabled tasks when it starts.
    enabled=streaming_enabled(),
    cron_string="* * * * *",  # Every minute
    # RQ kills a job at its timeout, so it has to cover a teardown holding its
    # marker to the ceiling.
    timeout=HOLD_CEILING_SECONDS,
    result_ttl=0,
    queue_name=STREAMING_QUEUE_NAME,
)

CLEANUP_SYNC_SESSIONS_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_sync_sessions.cleanup_sync_sessions_task",
    title="Scheduled sync session cleanup",
    description="Fails sync sessions no client ever completed",
    task_type=TaskType.CLEANUP,
    enabled=ENABLE_SCHEDULED_CLEANUP_SYNC_SESSIONS,
    cron_string=SCHEDULED_CLEANUP_SYNC_SESSIONS_CRON,
)

CLEANUP_AUDIT_LOG_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.cleanup_audit_log.cleanup_audit_log_task",
    title="Scheduled audit log cleanup",
    description=f"Removes audit log events older than {AUDIT_LOG_RETENTION_DAYS} days",
    task_type=TaskType.CLEANUP,
    enabled=AUDIT_LOG_RETENTION_DAYS > 0,
    cron_string="30 4 * * *",
)

SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC: Final = TaskSpec(
    implementation="tasks.scheduled.sync_retroachievements_progress.sync_retroachievements_progress_task",
    title="Scheduled RetroAchievements progress sync",
    description="Updates RetroAchievements progress for all users",
    task_type=TaskType.UPDATE,
    enabled=ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    cron_string=SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
)

SYNC_PUSH_PULL_SPEC: Final = TaskSpec(
    implementation="tasks.sync_push_pull_task.sync_push_pull_task",
    title="Push-Pull Sync",
    description="Sync saves with devices via SSH/SFTP",
    task_type=TaskType.SYNC,
    enabled=ENABLE_SYNC_PUSH_PULL,
    cron_string=SYNC_PUSH_PULL_CRON,
)

CLEANUP_MISSING_ROMS_SPEC: Final = TaskSpec(
    implementation="tasks.manual.cleanup_missing_roms.cleanup_missing_roms_task",
    title="Cleanup missing ROMs",
    description="Delete all ROMs flagged as missing from the filesystem from the database",
    task_type=TaskType.CLEANUP,
    enabled=True,
    manual_run=True,
)

CLEANUP_MISSING_FIRMWARE_SPEC: Final = TaskSpec(
    implementation="tasks.manual.cleanup_missing_firmware.cleanup_missing_firmware_task",
    title="Cleanup missing firmware",
    description="Delete all firmware flagged as missing from the filesystem from the database",
    task_type=TaskType.CLEANUP,
    enabled=True,
    manual_run=True,
)

SYNC_FOLDER_SCAN_SPEC: Final = TaskSpec(
    implementation="tasks.manual.sync_folder_scan.sync_folder_scan_task",
    title="Sync Folder Scan",
    description="Scan device sync folders for new save files",
    task_type=TaskType.SYNC,
    enabled=ENABLE_SYNC_FOLDER_WATCHER,
    manual_run=True,
)

RECOMPUTE_SAVE_CONTENT_HASHES_SPEC: Final = TaskSpec(
    implementation="tasks.manual.recompute_save_content_hashes.recompute_save_content_hashes_task",
    title="Recompute save content hashes",
    description=(
        "Re-scan every save row and rewrite content_hash with the "
        "current compute_content_hash algorithm. One-time recovery "
        "after the zip-hash dispatch fix."
    ),
    task_type=TaskType.CLEANUP,
    enabled=True,
    manual_run=True,
)

CONVERT_LIBRARY_SPEC: Final = TaskSpec(
    implementation="tasks.manual.convert_library.convert_library_task",
    title="Convert library",
    description=(
        "Convert each matched ROM to its platform's library format, "
        "replacing the original files"
    ),
    task_type=TaskType.CONVERSION,
    enabled=True,
    manual_run=True,
    # One conversion after another, each up to ROM_CONVERTO_TIMEOUT.
    timeout=SCAN_TIMEOUT,
)

# The keys are the names the API and the cron schedule address a task by, and
# they end up in the job payload, so they outlive any given release. Every task
# that runs on a schedule belongs here; which of them the API surfaces is the
# endpoint's business.
SCHEDULED_TASKS: Final[dict[str, TaskSpec]] = {
    "scan_library": SCAN_LIBRARY_SPEC,
    "update_launchbox_metadata": UPDATE_LAUNCHBOX_METADATA_SPEC,
    "update_switch_titledb": UPDATE_SWITCH_TITLEDB_SPEC,
    "build_recommendations": BUILD_RECOMMENDATIONS_SPEC,
    "convert_images_to_webp": CONVERT_IMAGES_TO_WEBP_SPEC,
    "cleanup_zip_cache": CLEANUP_ZIP_CACHE_SPEC,
    "cleanup_conversion_cache": CLEANUP_CONVERSION_CACHE_SPEC,
    "cleanup_orphaned_resources": CLEANUP_ORPHANED_RESOURCES_SPEC,
    "cleanup_netplay": CLEANUP_NETPLAY_SPEC,
    "cleanup_upload_tmp": CLEANUP_UPLOAD_TMP_SPEC,
    "reap_streaming_sessions": REAP_STREAMING_SESSIONS_SPEC,
    "cleanup_sync_sessions": CLEANUP_SYNC_SESSIONS_SPEC,
    "cleanup_audit_log": CLEANUP_AUDIT_LOG_SPEC,
    "sync_retroachievements_progress": SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC,
    "sync_push_pull": SYNC_PUSH_PULL_SPEC,
}

MANUAL_TASKS: Final[dict[str, TaskSpec]] = {
    "cleanup_missing_roms": CLEANUP_MISSING_ROMS_SPEC,
    "cleanup_missing_firmware": CLEANUP_MISSING_FIRMWARE_SPEC,
    "sync_folder_scan": SYNC_FOLDER_SCAN_SPEC,
    "recompute_save_content_hashes": RECOMPUTE_SAVE_CONTENT_HASHES_SPEC,
    "convert_library": CONVERT_LIBRARY_SPEC,
}


def get_task_spec(name: str) -> TaskSpec | None:
    """Look up what is known of a task by the name it is addressed by."""
    return SCHEDULED_TASKS.get(name) or MANUAL_TASKS.get(name)


def get_task(name: str) -> Task | None:
    """Import the task registered under ``name``, the first call loading its module."""
    spec = get_task_spec(name)
    if spec is None:
        return None
    return cast(Task, import_attribute(spec.implementation))


def enqueue_task(
    name: str,
    *,
    queue: Queue | None = None,
    task_kwargs: dict[str, Any] | None = None,
    run_by_user_id: int | None = None,
    **job_options: Any,
) -> Job:
    """Enqueue a registered task by name.

    Args:
        name: The key the task is registered under.
        queue: Which queue to enqueue on, the one the spec names by default.
        task_kwargs: Forwarded to the task's ``run``, nested so that they cannot
            collide with the name of the task to run.
        run_by_user_id: Who ran it by hand, notified when it ends.
        job_options: Passed through to RQ, for a fixed job id and the like.

    Returns:
        The enqueued job.
    """
    spec = get_task_spec(name)
    if spec is None:
        raise TaskNotFoundException(name)

    queue = queue or QUEUES_BY_NAME[spec.queue_name]
    return queue.enqueue(
        run_task_by_name,
        kwargs={
            "name": name,
            "task_kwargs": task_kwargs or {},
            "run_by_user_id": run_by_user_id,
        },
        job_timeout=spec.timeout,
        result_ttl=spec.result_ttl,
        meta=spec.job_meta(name),
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
    # By path, so the dispatch job doesn't load the scan stack to reference it.
    on_failure = Callback("endpoints.sockets.scan.report_scan_failure")
    return enqueue_task(name, queue=scan_queue, on_failure=on_failure).id
