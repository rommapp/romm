import json
from itertools import batched
from typing import Final

from rq import get_current_job

from config import (
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from handler.redis_handler import async_cache
from logger.logger import log
from tasks.tasks import RemoteFilePullTask, TaskType
from utils.context import initialize_context

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

    def _update_job_meta(self, processed: int, total: int) -> None:
        """Update the current RQ job's meta data with update stats information"""
        try:
            current_job = get_current_job()
            if current_job:
                current_job.meta.update(
                    {
                        "update_stats": {
                            "processed": processed,
                            "total": total,
                        }
                    }
                )
                current_job.save_meta()
        except Exception as e:
            # Silently fail if we can't update meta (e.g., not running in RQ context)
            log.debug(f"Could not update job meta: {e}")

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, str]:
        content = await super().run(force)
        if content is None:
            return {"status": "failed", "reason": "No content received"}

        index_json = json.loads(content)
        relevant_data = {k: v for k, v in index_json.items() if k and v}

        total_items = len(relevant_data)
        processed_items = 0

        # Update initial progress
        self._update_job_meta(processed_items, total_items)

        async with async_cache.pipeline() as pipe:
            for data_batch in batched(relevant_data.items(), 2000, strict=False):
                titledb_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                await pipe.hset(SWITCH_TITLEDB_INDEX_KEY, mapping=titledb_map)
                processed_items += len(data_batch)
                self._update_job_meta(processed_items, total_items)

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
        self._update_job_meta(total_items, total_items)
        log.info("Scheduled switch titledb update completed!")

        return {
            "status": "completed",
            "message": "Switch TitleDB update completed successfully",
        }


update_switch_titledb_task = UpdateSwitchTitleDBTask()
