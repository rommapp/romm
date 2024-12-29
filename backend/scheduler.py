import sentry_sdk
from config import SENTRY_DSN
from logger.logger import log
from tasks.scan_library import scan_library_task
from tasks.tasks import tasks_scheduler
from tasks.update_switch_titledb import update_switch_titledb_task
from utils import get_version

sentry_sdk.init(
    dsn=SENTRY_DSN,
    release="romm@" + get_version(),
)

if __name__ == "__main__":
    # Initialize the tasks
    scan_library_task.init()
    update_switch_titledb_task.init()

    log.info("Starting scheduler")

    # Start the scheduler
    tasks_scheduler.run()
