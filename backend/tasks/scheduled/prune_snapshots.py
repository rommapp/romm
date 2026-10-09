from handler.snapshots import retention
from logger.logger import log
from tasks.registry import PRUNE_SNAPSHOTS_SPEC
from tasks.tasks import PeriodicTask


class PruneSnapshotsTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(PRUNE_SNAPSHOTS_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        removed = await retention.prune_branches()
        if removed:
            log.info(f"Pruned expired sync branches and {removed} content row(s)")
        orphaned = await retention.prune_unreachable()
        if orphaned:
            log.info(f"Pruned unreachable archival saves and {orphaned} content row(s)")


prune_snapshots_task = PruneSnapshotsTask()
