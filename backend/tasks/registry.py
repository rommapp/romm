"""The catalog of tasks an admin can see, run, or have run on a schedule."""

from typing import Final

from tasks.manual.cleanup_missing_firmware import cleanup_missing_firmware_task
from tasks.manual.cleanup_missing_roms import cleanup_missing_roms_task
from tasks.manual.recompute_save_content_hashes import (
    recompute_save_content_hashes_task,
)
from tasks.manual.sync_folder_scan import sync_folder_scan_task
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
from tasks.tasks import PeriodicTask, Task

# The keys are the names the API and the cron schedule address a task by, and
# they end up in the job payload, so they outlive any given release. Every task
# that runs on a schedule belongs here; which of them the API surfaces is the
# endpoint's business.
SCHEDULED_TASKS: Final[dict[str, PeriodicTask]] = {
    "scan_library": scan_library_task,
    "update_launchbox_metadata": update_launchbox_metadata_task,
    "update_switch_titledb": update_switch_titledb_task,
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
