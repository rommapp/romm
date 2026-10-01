"""Rebuilds the item-item similarity graph that backs recommendations."""

from handler.recommendation import (
    BuildStats,
    SimilarityBuilder,
    invalidate_all_cached_feeds,
)
from logger.logger import log
from tasks.registry import BUILD_RECOMMENDATIONS_SPEC
from tasks.tasks import PeriodicTask
from utils.context import initialize_context

from . import UpdateStats


class BuildRecommendationsTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(BUILD_RECOMMENDATIONS_SPEC)

    @initialize_context()
    async def run(self, force: bool = False) -> dict[str, int]:
        if not self.spec.enabled and not force:
            log.info(f"Scheduled {self.spec.description} not enabled, skipping...")
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

        # Every cached ranking was computed against the previous graph.
        invalidate_all_cached_feeds()

        log.info(
            f"Recommendations index rebuilt: {build_stats.edges_written} edges "
            f"across {build_stats.roms_indexed} ROMs"
        )
        return update_stats.to_dict()


build_recommendations_task = BuildRecommendationsTask()
