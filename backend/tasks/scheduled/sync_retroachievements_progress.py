from typing import cast

from rq import get_current_job

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
    async def run(self) -> dict[str, str | int]:
        if not meta_ra_handler.is_enabled():
            log.warning("RetroAchievements API is not enabled, skipping progress sync")
            return {
                "status": "skipped",
                "reason": "RetroAchievements API not enabled",
                "updated_users": 0,
            }

        log.info("Scheduled RetroAchievements progress sync started...")

        users = db_user_handler.get_users(has_ra_username=True)
        total_users = len(users)
        processed_users = 0

        # Update initial progress
        self._update_job_meta(processed_users, total_users)

        for user in users:
            try:
                user_progression = await meta_ra_handler.get_user_progression(
                    user.ra_username or "",
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
            self._update_job_meta(processed_users, total_users)

        log.info(
            f"Scheduled RetroAchievements progress sync done. Updated users: {len(users)}"
        )

        return {"status": "completed", "updated_users": len(users)}


sync_retroachievements_progress_task = SyncRetroAchievementsProgressTask()
