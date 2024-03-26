import json
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from tasks.tasks import RemoteFilePullTask
from logger.logger import log
from handler.redis_handler import cache

SWITCH_TITLEDB_INDEX_KEY: Final = "romm:switch_titledb"
SWITCH_PRODUCT_ID_KEY: Final = "romm:switch_product_id"


class UpdateSwitchTitleDBTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_switch_titledb.update_switch_titledb_task.run",
            description="switch titledb update",
            enabled=ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
            cron_string=SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
            url="https://raw.githubusercontent.com/blawar/titledb/master/US.en.json",
        )

    async def run(self, force: bool = False):
        content = await super().run(force)
        if content is None:
            return

        index_json = json.loads(content)
        cache.set(SWITCH_TITLEDB_INDEX_KEY, content)

        product_ids = dict((v["id"], v) for _k, v in index_json.items())
        cache.set(SWITCH_PRODUCT_ID_KEY, json.dumps(product_ids))

        log.info("Scheduled switch titledb update completed!")


update_switch_titledb_task = UpdateSwitchTitleDBTask()
