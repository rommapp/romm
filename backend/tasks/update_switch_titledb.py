import json
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from handler.redis_handler import cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask

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
        for key, value in index_json.items():
            if key and value:
                cache.hset(SWITCH_TITLEDB_INDEX_KEY, key, json.dumps(value))

        product_ids = dict((v["id"], v) for _k, v in index_json.items())
        for key, value in product_ids.items():
            if key and value:
                cache.hset(SWITCH_PRODUCT_ID_KEY, key, json.dumps(value))

        log.info("Scheduled switch titledb update completed!")


update_switch_titledb_task = UpdateSwitchTitleDBTask()
