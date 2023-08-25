from utils.redis import redis_connectable
from logger.logger import log
from .exceptions import SchedulerException
from . import scheduler


async def run():
    from endpoints.scan import scan_platforms

    log.info("Scheduled library scan started...")
    await scan_platforms("", False)
    log.info("Scheduled library scan done.")


def schedule():
    if not redis_connectable:
        raise SchedulerException("Redis not connectable, library scan not scheduled.")

    existing_jobs = scheduler.get_jobs(func_name="tasks.scan_library.run")
    if existing_jobs:
        raise SchedulerException("Library scan already scheduled.")

    return scheduler.cron(
        "0 3 * * *",  # At 3:00 AM every day
        func="tasks.scan_library.run",
        repeat=None,
    )


def unschedule():
    existing_jobs = scheduler.get_jobs(func_name="tasks.scan_library.run")

    if not existing_jobs:
        raise SchedulerException("No library scan scheduled.")

    scheduler.cancel(*existing_jobs)
