import json
from itertools import batched
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask
from utils.context import initialize_context

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

    @initialize_context()
    async def run(self, force: bool = False) -> None:
        content = await super().run(force)
        if content is None:
            return

        index_json = json.loads(content)
        relevant_data = {k: v for k, v in index_json.items() if k and v}

        async with async_cache.pipeline() as pipe:
            for data_batch in batched(relevant_data.items(), 2000):
                titledb_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                await pipe.hset(SWITCH_TITLEDB_INDEX_KEY, mapping=titledb_map)
            for data_batch in batched(relevant_data.items(), 2000):
                product_map = {
                    v["id"]: json.dumps(v)
                    for v in dict(data_batch).values()
                    if v.get("id")
                }
                if product_map:
                    await pipe.hset(SWITCH_PRODUCT_ID_KEY, mapping=product_map)
            await pipe.execute()

        log.info("Scheduled switch titledb update completed!")


update_switch_titledb_task = UpdateSwitchTitleDBTask()
