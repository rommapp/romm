import os
from pathlib import Path
from typing import Final

from config import ENABLE_SCHEDULED_UPDATE_MAME_XML, SCHEDULED_UPDATE_MAME_XML_CRON
from tasks.tasks import RemoteFilePullTask

FIXTURE_FILE_PATH: Final = (
    Path(os.path.dirname(__file__)).parent / "handler" / "fixtures" / "mame.xml"
)


class UpdateMAMEXMLTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_mame_xml.update_mame_xml_task.run",
            description="mame xml update",
            enabled=ENABLE_SCHEDULED_UPDATE_MAME_XML,
            cron_string=SCHEDULED_UPDATE_MAME_XML_CRON,
            url="https://gist.githubusercontent.com/gantoine/0e2b9e25962bfd661ad2fe0ba0e72766/raw/gistfile1.txt",
            file_path=FIXTURE_FILE_PATH,
        )


update_mame_xml_task = UpdateMAMEXMLTask()
