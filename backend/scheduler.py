import sys

from config import ENABLE_EXPERIMENTAL_REDIS
from logger.logger import log
from tasks.scan_library import scan_library_task
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task
from tasks.tasks import tasks_scheduler

if __name__ == "__main__":
    if not ENABLE_EXPERIMENTAL_REDIS:
        sys.exit(0)

    # Initialize the tasks
    scan_library_task.init()
    update_switch_titledb_task.init()
    update_mame_xml_task.init()

    log.info("Starting scheduler")

    # Start the scheduler
    tasks_scheduler.run()
