from dataclasses import replace

from handler.snapshots import retention
from tasks.registry import PRUNE_SNAPSHOTS_SPEC
from tasks.scheduled.prune_snapshots import PruneSnapshotsTask


class TestPruneSnapshotsTask:
    def test_default_schedule(self):
        assert PRUNE_SNAPSHOTS_SPEC.enabled is True
        assert PRUNE_SNAPSHOTS_SPEC.cron_string == "41 * * * *"

    async def test_disabled_task_prunes_nothing(self, mocker):
        prune = mocker.patch.object(retention, "prune_branches")
        task = PruneSnapshotsTask()
        task.spec = replace(task.spec, enabled=False)
        await task.run()
        prune.assert_not_called()

    async def test_enabled_task_prunes_expired_branches(self, mocker):
        prune = mocker.patch.object(retention, "prune_branches", return_value=3)
        await PruneSnapshotsTask().run()
        prune.assert_awaited_once()
