import logging

import sentry_sdk
from config import (
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SENTRY_DSN,
)
from logger.formatter import BLUE, CYAN, GREEN, LIGHTMAGENTA, RESET, RESET_ALL
from tasks.scan_library import scan_library_task
from tasks.tasks import tasks_scheduler
from tasks.update_switch_titledb import update_switch_titledb_task
from utils import get_version

sentry_sdk.init(dsn=SENTRY_DSN, release=f"romm@{get_version()}")

# Set up custom logging
log_format = f"{GREEN}INFO{RESET}:\t  {BLUE}[RomM]{LIGHTMAGENTA}[%(module)s]{CYAN}[%(asctime)s] {RESET_ALL}%(message)s"
logging.basicConfig(format=log_format, datefmt="%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    # Initialize the tasks
    if ENABLE_SCHEDULED_RESCAN:
        scan_library_task.init()
    if ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        update_switch_titledb_task.init()
    # Start the scheduler
    tasks_scheduler.run()
