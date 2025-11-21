import json
from itertools import batched
from typing import Any, Final

from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask, TaskType
from utils.context import initialize_context

from . import UpdateStats

SWITCH_TITLEDB_INDEX_KEY: Final = "romm:switch_titledb"
SWITCH_PRODUCT_ID_KEY: Final = "romm:switch_product_id"


class UpdateSwitchTitleDBTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            title="Scheduled Switch TitleDB update",
            description="Updates the Nintendo Switch TitleDB file",
            task_type=TaskType.UPDATE,
            enabled=ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
            cron_string=SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
            manual_run=True,
            func="tasks.scheduled.update_switch_titledb.update_switch_titledb_task.run",
            url="https://raw.githubusercontent.com/blawar/titledb/master/US.en.json",
        )

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, Any]:
        update_stats = UpdateStats()

        content = await super().run(force)
        if content is None:
            return update_stats.to_dict()

        index_json = json.loads(content)
        relevant_data = {k: v for k, v in index_json.items() if k and v}
        total_items = len(relevant_data)
        processed_items = 0

        # Update initial progress
        update_stats.update(processed=processed_items, total=total_items)

        async with async_cache.pipeline() as pipe:
            for data_batch in batched(relevant_data.items(), 2000, strict=False):
                titledb_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                await pipe.hset(SWITCH_TITLEDB_INDEX_KEY, mapping=titledb_map)
                processed_items += len(data_batch)
                update_stats.update(processed=processed_items)

            for data_batch in batched(relevant_data.items(), 2000, strict=False):
                product_map = {
                    v["id"]: json.dumps(v)
                    for v in dict(data_batch).values()
                    if v.get("id")
                }
                if product_map:
                    await pipe.hset(SWITCH_PRODUCT_ID_KEY, mapping=product_map)
            await pipe.execute()

        # Final progress update
        update_stats.update(processed=processed_items)
        log.info("Scheduled switch titledb update completed!")

        return update_stats.to_dict()


update_switch_titledb_task = UpdateSwitchTitleDBTask()

TITLEDB_REGION_LANG_MAP: Final = {
    "BG": ["en"],
    "BR": ["en", "pt"],
    "CH": ["fr", "de", "it"],
    "CY": ["en"],
    "EE": ["en"],
    "HR": ["en"],
    "IE": ["en"],
    "LT": ["en"],
    "LU": ["fr", "de"],
    "LV": ["en"],
    "MT": ["en"],
    "RO": ["en"],
    "SI": ["en"],
    "SK": ["en"],
    "CO": ["en", "es"],
    "AR": ["en", "es"],
    "CL": ["en", "es"],
    "PE": ["en", "es"],
    "KR": ["ko"],
    "HK": ["zh"],
    "CN": ["zh"],
    "NZ": ["en"],
    "AT": ["de"],
    "BE": ["fr", "nl"],
    "CZ": ["en"],
    "DK": ["en"],
    "ES": ["es"],
    "FI": ["en"],
    "GR": ["en"],
    "HU": ["en"],
    "NL": ["nl"],
    "NO": ["en"],
    "PL": ["en"],
    "PT": ["pt"],
    "RU": ["ru"],
    "ZA": ["en"],
    "SE": ["en"],
    "MX": ["en", "es"],
    "IT": ["it"],
    "CA": ["en", "fr"],
    "FR": ["fr"],
    "DE": ["de"],
    "JP": ["ja"],
    "AU": ["en"],
    "GB": ["en"],
    "US": ["en", "es"],
}

TITLEDB_REGION_LIST: Final = list(TITLEDB_REGION_LANG_MAP.keys())
TITLEDB_LANGUAGE_LIST: Final = list(
    set(lang for sublist in TITLEDB_REGION_LANG_MAP.values() for lang in sublist)
)
