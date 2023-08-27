import sys

from config import ENABLE_EXPERIMENTAL_REDIS
from tasks.utils import tasks_scheduler
from tasks.scan_library import scan_library_task
from tasks.update_switch_titledb import update_switch_titledb_task

if __name__ == "__main__":
    if not ENABLE_EXPERIMENTAL_REDIS:
        sys.exit(0)

    # Initialize the tasks
    scan_library_task.init()
    update_switch_titledb_task.init()

    # Start the scheduler
    tasks_scheduler.run()
