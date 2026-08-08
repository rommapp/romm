"""Rebuilds the item-item similarity graph that backs recommendations."""

from config import (
    ENABLE_SCHEDULED_BUILD_RECOMMENDATIONS,
    SCHEDULED_BUILD_RECOMMENDATIONS_CRON,
)
from handler.recommendation import BuildStats, SimilarityBuilder
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType
from utils.context import initialize_context

from . import UpdateStats


class BuildRecommendationsTask(PeriodicTask):
    def __init__(self):
        super().__init__(
            title="Build recommendations index",
            description=(
                "Rebuilds the similar-games index from library metadata, "
                "play history and collections"
            ),
            task_type=TaskType.UPDATE,
            enabled=ENABLE_SCHEDULED_BUILD_RECOMMENDATIONS,
            manual_run=True,
            cron_string=SCHEDULED_BUILD_RECOMMENDATIONS_CRON,
            func="tasks.scheduled.build_recommendations.build_recommendations_task.run",
        )

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, int]:
        if not self.enabled and not force:
            log.info(f"Scheduled {self.description} not enabled, unscheduling...")
            self.unschedule()
            return UpdateStats().to_dict()

        log.info("Building recommendations index...")

        update_stats = UpdateStats()

        def report(stats: BuildStats) -> None:
            update_stats.update(processed=stats.roms_indexed, total=stats.total)

        try:
            build_stats = SimilarityBuilder(progress=report).build()
        except Exception:
            log.error("Failed to build recommendations index", exc_info=True)
            raise

        log.info(
            f"Recommendations index rebuilt: {build_stats.edges_written} edges "
            f"across {build_stats.roms_indexed} ROMs"
        )
        return update_stats.to_dict()


build_recommendations_task = BuildRecommendationsTask()
