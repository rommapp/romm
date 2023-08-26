import sys

from config import (
    ENABLE_EXPERIMENTAL_REDIS,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
)
from tasks import tasks_scheduler
import tasks.scan_library as scan_library
import tasks.update_switch_titledb as update_switch_titledb

if __name__ == "__main__":
    if not ENABLE_EXPERIMENTAL_REDIS:
        sys.exit(0)

    # Start the scheduled library scan
    if ENABLE_SCHEDULED_RESCAN:
        scan_library.schedule()

    if ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        update_switch_titledb.schedule()

    # Start the scheduler
    tasks_scheduler.run()
