import requests
import os
from pathlib import Path

from utils.redis import redis_connectable
from logger.logger import log
from typing import Final
from .exceptions import SchedulerException
from . import scheduler

RAW_URL: Final = "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
FIXTURE_FILE_PATH = (
    Path(os.path.dirname(__file__)).parent
    / "handler"
    / "fixtures"
    / "switch_titledb.json"
)


async def run():
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
    if not redis_connectable:
        raise SchedulerException("Redis not connectable, titleDB update not scheduled.")

    existing_jobs = scheduler.get_jobs(func_name="tasks.update_switch_titledb.run")
    if existing_jobs:
        raise SchedulerException("TitleDB update already scheduled.")

    return scheduler.cron(
        "0 3 * * *",  # At 3:00 AM every day
        func="tasks.update_switch_titledb.run",
        repeat=None,
    )


def unschedule():
    existing_jobs = scheduler.get_jobs(func_name="tasks.update_switch_titledb.run")

    if not existing_jobs:
        raise SchedulerException("No TitleDB update scheduled.")

    scheduler.cancel(*existing_jobs)
