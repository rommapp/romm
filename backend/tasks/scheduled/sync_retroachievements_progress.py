from typing import Any, cast

from config import (
    ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
)
from handler.database import db_user_handler
from handler.metadata import meta_ra_handler
from handler.metadata.ra_handler import RAUserProgression
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.context import initialize_context

from . import UpdateStats


class SyncRetroAchievementsProgressTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled RetroAchievements progress sync",
            task_type=TaskType.UPDATE,
            description="Updates RetroAchievements progress for all users",
            enabled=ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
            cron_string=SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
            manual_run=False,
            func="tasks.scheduled.sync_retroachievements_progress.sync_retroachievements_progress_task.run",
        )

    @initialize_context()
    async def run(self) -> dict[str, Any]:
        update_stats = UpdateStats()

        if not meta_ra_handler.is_enabled():
            log.warning("RetroAchievements API is not enabled, skipping progress sync")
            return update_stats.to_dict()

        log.info("Scheduled RetroAchievements progress sync started...")

        users = db_user_handler.get_users(has_ra_username=True)
        total_users = len(users)
        processed_users = 0

        # Update initial progress
        update_stats.update(processed=processed_users, total=total_users)

        for user in users:
            try:
                user_progression = await meta_ra_handler.get_user_progression(
                    user.ra_username,  # type: ignore[union-attr]
                    current_progression=cast(
                        RAUserProgression | None, user.ra_progression
                    ),
                )
                db_user_handler.update_user(
                    user.id,
                    {"ra_progression": user_progression},
                )
            except Exception as e:
                log.error(
                    f"Failed to update RetroAchievements progress for user: {user.username}, error: {e}"
                )
            else:
                log.debug(
                    f"Updated RetroAchievements progress for user: {user.username}"
                )

            processed_users += 1
            update_stats.update(processed=processed_users)

        log.info(
            f"Scheduled RetroAchievements progress sync done. Updated users: {len(users)}"
        )

        return update_stats.to_dict()


sync_retroachievements_progress_task = SyncRetroAchievementsProgressTask()
