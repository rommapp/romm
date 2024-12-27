import os
from datetime import timedelta

import sentry_sdk
from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    LIBRARY_BASE_PATH,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    SENTRY_DSN,
)
from config.config_manager import config_manager as cm
from endpoints.sockets.scan import scan_platforms
from handler.database import db_platform_handler
from handler.scan_handler import ScanType
from logger.logger import log
from tasks.tasks import tasks_scheduler
from utils import get_version
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release="romm@" + get_version(),
)

path = (
    cm.get_config().HIGH_PRIO_STRUCTURE_PATH
    if os.path.exists(cm.get_config().HIGH_PRIO_STRUCTURE_PATH)
    else LIBRARY_BASE_PATH
)


class EventHandler(FileSystemEventHandler):
    """Filesystem event handler"""

    def on_any_event(self, event):
        """Catch-all event handler.

        Args:
            event: The event object representing the file system event.
        """
        if not ENABLE_RESCAN_ON_FILESYSTEM_CHANGE:
            return

        # Ignore .DS_Store files
        if event.src_path.endswith(".DS_Store"):
            return

        # Ignore some event types
        if event.event_type in ["modified", "opened", "closed"]:
            return

        event_src = event.src_path.split(path)[-1]
        fs_slug = event_src.split("/")[1]
        db_platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)

        log.info(f"Filesystem event: {event.event_type} {event_src}")

        # Skip if a scan is already scheduled
        for job in tasks_scheduler.get_jobs():
            if job.func_name == "endpoints.sockets.scan.scan_platforms":
                if job.args[0] == []:
                    log.info("Full rescan already scheduled")
                    return

                if db_platform and db_platform.id in job.args[0]:
                    log.info(f"Scan already scheduled for {fs_slug}")
                    return

        time_delta = timedelta(minutes=RESCAN_ON_FILESYSTEM_CHANGE_DELAY)
        rescan_in_msg = f"rescanning in {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minutes."

        # Any change to a platform directory should trigger a full rescan
        if event.is_directory and event_src.count("/") == 1:
            log.info(f"Platform directory changed, {rescan_in_msg}")
            tasks_scheduler.enqueue_in(time_delta, scan_platforms, [])
        elif db_platform:
            # Otherwise trigger a rescan for the specific platform
            log.info(f"Change detected in {fs_slug} folder, {rescan_in_msg}")
            return tasks_scheduler.enqueue_in(
                time_delta,
                scan_platforms,
                [db_platform.id],
                scan_type=ScanType.QUICK,
            )


if __name__ == "__main__":
    observer = Observer()
    observer.schedule(EventHandler(), path, recursive=True)
    observer.start()

    log.info(f"Watching {path} for changes")

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()
