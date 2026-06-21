"""Tests for BackfillCoverDimensionsTask.

The task reads each ROM's stored large cover off disk and records its
natural width/height so the gallery can render covers at their true aspect
ratio. These tests pin the updated / missing-fs / skip accounting and the
end-to-end persistence of dimensions.
"""

from pathlib import Path

import pytest
from PIL import Image

from handler.database import db_rom_handler
from handler.filesystem import fs_resource_handler
from models.platform import Platform
from models.rom import Rom
from tasks.manual.backfill_cover_dimensions import (
    BackfillCoverDimensionsTask,
    backfill_cover_dimensions_task,
)


@pytest.fixture
def isolated_resources_dir(tmp_path, monkeypatch):
    """Redirect fs_resource_handler to tmp_path so cover reads/writes stay
    scoped to the test."""
    new_base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_resource_handler, "base_path", new_base)
    return new_base


def _write_big_cover(base: Path, rom: Rom, width: int, height: int) -> None:
    cover_dir = base / rom.fs_resources_path / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), (10, 20, 30)).save(cover_dir / "big.png")


class TestBackfillCoverDimensionsTask:
    @pytest.fixture
    def task(self) -> BackfillCoverDimensionsTask:
        return BackfillCoverDimensionsTask()

    def test_module_singleton_exists(self):
        assert backfill_cover_dimensions_task is not None
        assert isinstance(backfill_cover_dimensions_task, BackfillCoverDimensionsTask)

    def test_init(self, task: BackfillCoverDimensionsTask):
        assert task.title == "Backfill cover dimensions"
        assert task.manual_run is True
        assert task.cron_string is None

    async def test_records_dimensions_from_disk(
        self,
        task: BackfillCoverDimensionsTask,
        isolated_resources_dir: Path,
        rom: Rom,
        platform: Platform,
    ):
        """A ROM with a stored cover but no recorded dimensions gets them
        read off disk and persisted."""
        db_rom_handler.update_rom(
            rom.id,
            {
                "path_cover_l": f"{rom.fs_resources_path}/cover/big.png",
                "cover_width": None,
                "cover_height": None,
            },
        )
        _write_big_cover(isolated_resources_dir, rom, 320, 448)

        stats = await task.run()

        assert stats["roms_scanned"] == 1
        assert stats["roms_updated"] == 1
        assert stats["roms_missing_fs"] == 0
        assert stats["errors"] == 0

        refreshed = db_rom_handler.get_rom(rom.id)
        assert refreshed is not None
        assert refreshed.cover_width == 320
        assert refreshed.cover_height == 448

    async def test_missing_file_is_counted_not_fatal(
        self,
        task: BackfillCoverDimensionsTask,
        isolated_resources_dir: Path,
        rom: Rom,
        platform: Platform,
    ):
        """A ROM whose cover path is set but absent on disk is counted as
        missing_fs and left NULL, not errored."""
        db_rom_handler.update_rom(
            rom.id,
            {
                "path_cover_l": f"{rom.fs_resources_path}/cover/big.png",
                "cover_width": None,
                "cover_height": None,
            },
        )
        # No file written.

        stats = await task.run()

        assert stats["roms_scanned"] == 1
        assert stats["roms_updated"] == 0
        assert stats["roms_missing_fs"] == 1
        assert stats["errors"] == 0

        refreshed = db_rom_handler.get_rom(rom.id)
        assert refreshed is not None
        assert refreshed.cover_width is None

    async def test_rom_with_recorded_dimensions_is_skipped(
        self,
        task: BackfillCoverDimensionsTask,
        isolated_resources_dir: Path,
        rom: Rom,
        platform: Platform,
    ):
        """A ROM that already has dimensions is not re-scanned (it falls out
        of the missing-dimensions query)."""
        db_rom_handler.update_rom(
            rom.id,
            {
                "path_cover_l": f"{rom.fs_resources_path}/cover/big.png",
                "cover_width": 100,
                "cover_height": 150,
            },
        )

        stats = await task.run()

        assert stats["roms_scanned"] == 0
        assert stats["roms_updated"] == 0
