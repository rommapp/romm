import os
import sys
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
from logger.formatter import CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from rq.job import Job
from tasks.tasks import tasks_scheduler
from utils import get_version
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileSystemMovedEvent,
)

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release=f"romm@{get_version()}",
)

structure_level = 2 if os.path.exists(cm.get_config().HIGH_PRIO_STRUCTURE_PATH) else 1

valid_events = [
    DirCreatedEvent.event_type,
    DirDeletedEvent.event_type,
    FileCreatedEvent.event_type,
    FileDeletedEvent.event_type,
    FileSystemMovedEvent.event_type,
]


def on_any_event(src_path: str, _dest_path: str, event_type: str, object: str):
    if event_type not in valid_events:
        return

    if not ENABLE_RESCAN_ON_FILESYSTEM_CHANGE:
        return

    src_path = os.fsdecode(src_path)

    event_src = src_path.split(LIBRARY_BASE_PATH)[-1]
    fs_slug = event_src.split("/")[structure_level]
    db_platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)

    log.info(f"Filesystem event: {event_type} {event_src} {fs_slug} {db_platform}")

    # Skip if a scan is already scheduled
    for job in tasks_scheduler.get_jobs():
        if isinstance(job, Job):
            if job.func_name == "endpoints.sockets.scan.scan_platforms":
                if job.args[0] == []:
                    log.info("Full rescan already scheduled")
                    return

                if db_platform and db_platform.id in job.args[0]:
                    log.info(f"Scan already scheduled for {hl(fs_slug)}")
                    return

    time_delta = timedelta(minutes=RESCAN_ON_FILESYSTEM_CHANGE_DELAY)
    rescan_in_msg = f"rescanning in {hl(str(RESCAN_ON_FILESYSTEM_CHANGE_DELAY), color=CYAN)} minutes."

    # Any change to a platform directory should trigger a full rescan
    if object == "directory" and event_src.count("/") == 1:
        log.info(f"Platform directory changed, {rescan_in_msg}")
        tasks_scheduler.enqueue_in(time_delta, scan_platforms, [])
    elif db_platform:
        # Otherwise trigger a rescan for the specific platform
        log.info(f"Change detected in {hl(fs_slug)} folder, {rescan_in_msg}")
        tasks_scheduler.enqueue_in(
            time_delta,
            scan_platforms,
            [db_platform.id],
            scan_type=ScanType.QUICK,
        )


if __name__ == "__main__":
    watch_src_path = sys.argv[1]
    watch_dest_path = sys.argv[2]
    watch_event_type = sys.argv[3]
    watch_object = sys.argv[4]

    on_any_event(watch_src_path, watch_dest_path, watch_event_type, watch_object)
