from typing import cast

from config import (
    ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
    SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
)
from handler.database import db_user_handler
from handler.metadata import meta_ra_handler
from handler.metadata.ra_handler import RA_API_ENABLED, RAUserProgression
from logger.logger import log
from tasks.tasks import PeriodicTask
from utils.context import initialize_context


class SyncRetroAchievementsProgressTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Scheduled RetroAchievements progress sync",
            description="Updates RetroAchievements progress for all users",
            enabled=ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC,
            cron_string=SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON,
            manual_run=False,
            func="tasks.scheduled.sync_retroachievements_progress.sync_retroachievements_progress_task.run",
        )

    @initialize_context()
    async def run(self) -> None:
        if not RA_API_ENABLED:
            log.warning("RetroAchievements API is not enabled, skipping progress sync")
            return None

        log.info("Scheduled RetroAchievements progress sync started...")

        users = db_user_handler.get_users(has_ra_username=True)
        for user in users:
            try:
                user_progression = await meta_ra_handler.get_user_progression(
                    user.ra_username,
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

        log.info(
            f"Scheduled RetroAchievements progress sync done. Updated users: {len(users)}"
        )


sync_retroachievements_progress_task = SyncRetroAchievementsProgressTask()
