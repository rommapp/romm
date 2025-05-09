import sentry_sdk
from config import (
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SENTRY_DSN,
)
from logger.logger import log
from tasks.scan_library import scan_library_task
from tasks.tasks import tasks_scheduler
from tasks.update_switch_titledb import update_switch_titledb_task
from utils import get_version

sentry_sdk.init(dsn=SENTRY_DSN, release=f"romm@{get_version()}")

if __name__ == "__main__":
    # Initialize the tasks
    if ENABLE_SCHEDULED_RESCAN:
        log.info("Starting scheduled rescan")
        scan_library_task.init()
    if ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        log.info("Starting scheduled update switch titledb")
        update_switch_titledb_task.init()
    # Start the scheduler
    tasks_scheduler.run()
