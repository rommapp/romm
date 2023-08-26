from logger.logger import log
from config import (
    ENABLE_EXPERIMENTAL_REDIS,
    ENABLE_SCHEDULED_RESCAN,
    SCHEDULED_RESCAN_CRON,
)
from .exceptions import SchedulerException
from . import tasks_scheduler


def _get_existing_job():
    existing_jobs = tasks_scheduler.get_jobs()
    for job in existing_jobs:
        if job.func_name == "tasks.scan_library.run":
            return job

    return None


async def run():
    if not ENABLE_SCHEDULED_RESCAN:
        log.info("Scheduled library scan not enabled, unscheduling...")
        unschedule()
        return

    from endpoints.scan import scan_platforms

    log.info("Scheduled library scan started...")
    await scan_platforms("", False)
    log.info("Scheduled library scan done.")


def schedule():
    if not ENABLE_EXPERIMENTAL_REDIS:
        raise SchedulerException("Redis not connectable, library scan not scheduled.")

    if not ENABLE_SCHEDULED_RESCAN:
        raise SchedulerException("Scheduled library scan not enabled.")

    if _get_existing_job():
        log.info("Library scan already scheduled.")
        return
    
    log.info("Scheduling library scan.")

    tasks_scheduler.cron(
        SCHEDULED_RESCAN_CRON,
        func="tasks.scan_library.run",
        repeat=None,
    )


def unschedule():
    job = _get_existing_job()

    if not job:
        log.info("Library scan not scheduled.")
        return

    tasks_scheduler.cancel(job)
    log.info("Library scan unscheduled.")
