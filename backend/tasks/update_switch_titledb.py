import os
from pathlib import Path

from typing import Final
from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from .utils import RemoteFilePullTask

FIXTURE_FILE_PATH: Final = (
    Path(os.path.dirname(__file__)).parent
    / "handler"
    / "fixtures"
    / "switch_titledb.json"
)


class UpdateSwitchTitleDBTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_switch_titledb.update_switch_titledb_task.run",
            description="switch titledb update",
            enabled=ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
            cron_string=SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
            url="https://raw.githubusercontent.com/blawar/titledb/master/US.en.json",
            file_path=FIXTURE_FILE_PATH,
        )


update_switch_titledb_task = UpdateSwitchTitleDBTask()
