"""Recompute content_hash for existing save rows after the
compute_content_hash path-resolution fix.

Background: previously, compute_content_hash dispatched on
zipfile.is_zipfile(relative_path), which silently returned False whenever the
server process's CWD did not equal ASSETS_BASE_PATH. Every zip save fell
through to the raw-MD5 path, so DB content_hash values for zip saves never
reflected the intended per-entry zip-hash. Once the path fix lands, existing
zip saves still have the old (raw-MD5) value stored; sync negotiations from
clients computing the correct zip-hash will disagree with the server forever
unless we re-scan.

This task iterates every Save row, recomputes content_hash via the now-fixed
algorithm, and updates the row if the value changed. Safe to re-run.
"""

from dataclasses import dataclass

from handler.database import db_save_handler
from handler.filesystem import fs_asset_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context

META_FLUSH_EVERY = 100


@dataclass
class RecomputeSaveHashesStats:
    """Counters reported via RQ job meta for the recompute task."""

    saves_scanned: int = 0
    saves_updated: int = 0
    saves_unchanged: int = 0
    saves_missing_fs: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "saves_scanned": self.saves_scanned,
            "saves_updated": self.saves_updated,
            "saves_unchanged": self.saves_unchanged,
            "saves_missing_fs": self.saves_missing_fs,
            "errors": self.errors,
        }

    def flush(self) -> None:
        """Push the current snapshot into the RQ job meta payload."""
        update_job_meta({"recompute_save_hashes_stats": self.to_dict()})


class RecomputeSaveContentHashesTask(Task):
    def __init__(self) -> None:
        super().__init__(
            title="Recompute save content hashes",
            description=(
                "Re-scan every save row and rewrite content_hash with the "
                "current compute_content_hash algorithm. One-time recovery "
                "after the zip-hash dispatch fix."
            ),
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self) -> dict[str, int]:
        log.info(f"Starting {self.title} task...")
        stats = RecomputeSaveHashesStats()

        saves = db_save_handler.get_all_saves()
        for save in saves:
            stats.saves_scanned += 1

            relative_path = f"{save.file_path}/{save.file_name}"
            try:
                new_hash = await fs_asset_handler.compute_content_hash(relative_path)
            except Exception as e:
                log.warning(
                    f"Failed to compute content_hash for save {save.id} "
                    f"({relative_path}): {e}"
                )
                stats.errors += 1
                self._maybe_flush(stats)
                continue

            if new_hash is None:
                stats.saves_missing_fs += 1
                self._maybe_flush(stats)
                continue

            if new_hash == save.content_hash:
                stats.saves_unchanged += 1
                self._maybe_flush(stats)
                continue

            try:
                db_save_handler.update_save(save.id, {"content_hash": new_hash})
                stats.saves_updated += 1
                log.debug(
                    f"Rewrote content_hash for save {save.id} "
                    f"({relative_path}): {save.content_hash} -> {new_hash}"
                )
            except Exception as e:
                log.warning(f"Failed to update save {save.id}: {e}")
                stats.errors += 1

            self._maybe_flush(stats)

        stats.flush()
        log.info(
            f"{self.title} complete: scanned={stats.saves_scanned}, "
            f"updated={stats.saves_updated}, unchanged={stats.saves_unchanged}, "
            f"missing_fs={stats.saves_missing_fs}, errors={stats.errors}"
        )
        return stats.to_dict()

    @staticmethod
    def _maybe_flush(stats: RecomputeSaveHashesStats) -> None:
        """Push the meta payload at coarse batch boundaries instead of on
        every row, so large libraries don't churn Redis."""
        if stats.saves_scanned % META_FLUSH_EVERY == 0:
            stats.flush()


recompute_save_content_hashes_task = RecomputeSaveContentHashesTask()
