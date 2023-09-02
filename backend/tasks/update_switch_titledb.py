import requests
import os
from pathlib import Path

from logger.logger import log
from typing import Final
from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from .utils import PeriodicTask

RAW_URL: Final = "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json"
FIXTURE_FILE_PATH = (
    Path(os.path.dirname(__file__)).parent
    / "handler"
    / "fixtures"
    / "switch_titledb.json"
)


class UpdateSwitchTitleDBTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_switch_titledb.update_switch_titledb_task.run",
            description="switch titledb update",
            enabled=ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
            cron_string=SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
        )

    async def run(self, force: bool = False):
        if not ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB and not force:
            log.info("Scheduled switch titledb update not enabled, unscheduling...")
            self.unschedule()
            return

        log.info("Scheduled switch titledb update started...")

        try:
            response = requests.get(RAW_URL)
            response.raise_for_status()

            with open(FIXTURE_FILE_PATH, "wb") as fixture:
                fixture.write(response.content)

            log.info("Scheduled switch titledb update done")
        except requests.exceptions.RequestException as e:
            log.error("Scheduled switch titledb update failed", exc_info=True)
            log.error(e)


update_switch_titledb_task = UpdateSwitchTitleDBTask()
