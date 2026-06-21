"""Backfill natural cover dimensions for ROMs scanned before cover_width /
cover_height were recorded.

Background: the frontend renders cover art at its natural aspect ratio
(ratio = cover_width / cover_height). Newly scanned / edited ROMs capture
those dimensions at save time, but ROMs imported before this change have
NULL dimensions and fall back to the default box-art ratio on the client.

This task pages every ROM that has a stored large cover but no recorded
dimensions, reads the image off disk, and writes the dimensions back. Safe
to re-run: rows that resolve drop out of the query; rows whose cover can't
be read stay NULL and are skipped on the next pass.
"""

from dataclasses import dataclass

from handler.database import db_rom_handler
from handler.filesystem import fs_resource_handler
from logger.logger import log
from tasks.tasks import Task, TaskType, update_job_meta
from utils.context import initialize_context

META_FLUSH_EVERY = 100
PAGE_SIZE = 1000


@dataclass
class BackfillCoverDimensionsStats:
    """Counters reported via RQ job meta for the backfill task."""

    roms_scanned: int = 0
    roms_updated: int = 0
    roms_missing_fs: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "roms_scanned": self.roms_scanned,
            "roms_updated": self.roms_updated,
            "roms_missing_fs": self.roms_missing_fs,
            "errors": self.errors,
        }

    def flush(self) -> None:
        """Push the current snapshot into the RQ job meta payload."""
        update_job_meta({"backfill_cover_dimensions_stats": self.to_dict()})


class BackfillCoverDimensionsTask(Task):
    def __init__(self) -> None:
        super().__init__(
            title="Backfill cover dimensions",
            description=(
                "Read each ROM's stored cover off disk and record its natural "
                "width/height so the gallery can render covers at their true "
                "aspect ratio. One-time backfill for libraries scanned before "
                "cover dimensions were tracked."
            ),
            task_type=TaskType.CLEANUP,
            enabled=True,
            manual_run=True,
            cron_string=None,
        )

    @initialize_context()
    async def run(self) -> dict[str, int]:
        log.info(f"Starting {self.title} task...")
        stats = BackfillCoverDimensionsStats()

        # Keyset-paginate by primary key. Advancing last_id past every row we
        # touch (including ones we couldn't read) guarantees forward progress
        # even though resolved rows drop out of the filter.
        last_id = 0
        while True:
            batch = db_rom_handler.get_roms_missing_cover_dimensions_after_id(
                after_id=last_id, limit=PAGE_SIZE
            )
            if not batch:
                break

            for rom in batch:
                stats.roms_scanned += 1
                last_id = rom.id

                try:
                    width, height = fs_resource_handler.get_cover_dimensions(rom)
                except Exception as e:
                    log.warning(
                        f"Failed to read cover dimensions for rom {rom.id} "
                        f"({rom.fs_resources_path}): {e}"
                    )
                    stats.errors += 1
                    self._maybe_flush(stats)
                    continue

                if width is None or height is None:
                    stats.roms_missing_fs += 1
                    self._maybe_flush(stats)
                    continue

                try:
                    db_rom_handler.update_rom(
                        rom.id,
                        {"cover_width": width, "cover_height": height},
                    )
                    stats.roms_updated += 1
                    log.debug(
                        f"Recorded cover dimensions for rom {rom.id} "
                        f"({rom.fs_resources_path}): {width}x{height}"
                    )
                except Exception as e:
                    log.warning(f"Failed to update rom {rom.id}: {e}")
                    stats.errors += 1

                self._maybe_flush(stats)

        stats.flush()
        log.info(
            f"{self.title} complete: scanned={stats.roms_scanned}, "
            f"updated={stats.roms_updated}, missing_fs={stats.roms_missing_fs}, "
            f"errors={stats.errors}"
        )
        return stats.to_dict()

    @staticmethod
    def _maybe_flush(stats: BackfillCoverDimensionsStats) -> None:
        """Push the meta payload at coarse batch boundaries instead of on
        every row, so large libraries don't churn Redis."""
        if stats.roms_scanned % META_FLUSH_EVERY == 0:
            stats.flush()


backfill_cover_dimensions_task = BackfillCoverDimensionsTask()
