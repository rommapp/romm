import requests
import os
from pathlib import Path

from logger.logger import log
from typing import Final
from config import (
    ENABLE_EXPERIMENTAL_REDIS,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from .exceptions import SchedulerException
from . import tasks_scheduler

RAW_URL: Final = "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
FIXTURE_FILE_PATH = (
    Path(os.path.dirname(__file__)).parent
    / "handler"
    / "fixtures"
    / "switch_titledb.json"
)


def _get_existing_job():
    existing_jobs = tasks_scheduler.get_jobs()
    for job in existing_jobs:
        if job.func_name == "tasks.update_switch_titledb.run":
            return job

    return None


async def run():
    if not ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        log.info("Scheduled TitleDB update not enabled, unscheduling...")
        unschedule()
        return

    log.info("Scheduled TitleDB update started...")

    try:
        response = requests.get(RAW_URL)
        response.raise_for_status()

        with open(FIXTURE_FILE_PATH, "wb") as fixture:
            fixture.write(response.content)

        log.info("TitleDB update done.")
    except requests.exceptions.RequestException as e:
        log.error("TitleDB update failed.", exc_info=True)
        log.error(e)


def schedule():
    if not ENABLE_EXPERIMENTAL_REDIS:
        raise SchedulerException("Redis not connectable, titleDB update not scheduled.")

    if not ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB:
        raise SchedulerException("Scheduled TitleDB update not enabled.")

    if _get_existing_job():
        log.info("TitleDB update already scheduled.")
        return

    return tasks_scheduler.cron(
        SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
        func="tasks.update_switch_titledb.run",
        repeat=None,
    )


def unschedule():
    job = _get_existing_job()

    if not job:
        log.info("TitleDB update not scheduled.")
        return

    tasks_scheduler.cancel(job)
    log.info("TitleDB update unscheduled.")
