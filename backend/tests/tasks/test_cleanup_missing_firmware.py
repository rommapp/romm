"""Tests for CleanupMissingFirmwareTask.

The ROM side has had a bulk cleanup for missing rows since forever; firmware
flagged by `mark_missing_firmware` had no counterpart, so stale BIOS entries
could only be removed one platform tab at a time (issue #4075).
"""

import pytest

from handler.database import db_firmware_handler, db_platform_handler
from models.firmware import Firmware
from models.platform import Platform
from tasks.manual.cleanup_missing_firmware import (
    CleanupMissingFirmwareTask,
    cleanup_missing_firmware_task,
)


def _add(platform: Platform, file_name: str, missing: bool) -> Firmware:
    return db_firmware_handler.add_firmware(
        Firmware(
            platform_id=platform.id,
            file_name=file_name,
            file_path=f"{platform.fs_slug}/bios",
            file_size_bytes=1,
            crc_hash="crc",
            md5_hash="md5",
            sha1_hash="sha1",
            missing_from_fs=missing,
        )
    )


@pytest.fixture
def other_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(name="other", slug="other_slug", fs_slug="other_slug")
    )


class TestCleanupMissingFirmwareTask:
    @pytest.fixture
    def task(self) -> CleanupMissingFirmwareTask:
        return CleanupMissingFirmwareTask()

    def test_module_singleton_exists(self):
        assert isinstance(cleanup_missing_firmware_task, CleanupMissingFirmwareTask)

    def test_configuration(self, task):
        assert task.enabled is True
        assert task.manual_run is True
        assert task.can_run_manually is True
        assert task.cron_string is None

    async def test_deletes_only_missing_firmware(self, task, platform):
        present = _add(platform, "present.bin", missing=False)
        gone = _add(platform, "gone.bin", missing=True)

        stats = await task.run()

        assert stats["firmware_found"] == 1
        assert stats["firmware_deleted"] == 1
        assert stats["errors"] == 0
        assert db_firmware_handler.get_firmware(gone.id) is None
        assert db_firmware_handler.get_firmware(present.id) is not None

    async def test_scopes_to_a_single_platform(self, task, platform, other_platform):
        mine = _add(platform, "gone.bin", missing=True)
        theirs = _add(other_platform, "other-gone.bin", missing=True)

        stats = await task.run(platform_id=platform.id)

        assert stats["platform_id"] == platform.id
        assert stats["firmware_deleted"] == 1
        assert db_firmware_handler.get_firmware(mine.id) is None
        assert db_firmware_handler.get_firmware(theirs.id) is not None

    async def test_counts_delete_failures(self, task, platform, mocker):
        _add(platform, "gone-a.bin", missing=True)
        _add(platform, "gone-b.bin", missing=True)
        mocker.patch(
            "tasks.manual.cleanup_missing_firmware.db_firmware_handler.delete_firmware",
            side_effect=RuntimeError("boom"),
        )

        stats = await task.run()

        assert stats["firmware_found"] == 2
        assert stats["firmware_deleted"] == 0
        assert stats["errors"] == 2

    async def test_no_missing_firmware_is_a_no_op(self, task, platform):
        _add(platform, "present.bin", missing=False)

        stats = await task.run()

        assert stats == {
            "platform_id": None,
            "firmware_found": 0,
            "firmware_deleted": 0,
            "errors": 0,
        }
