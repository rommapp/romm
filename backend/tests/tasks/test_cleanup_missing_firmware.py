"""Tests for CleanupMissingFirmwareTask."""

import pytest

from handler.database import db_firmware_handler
from tasks.manual.cleanup_missing_firmware import (
    CleanupMissingFirmwareTask,
    cleanup_missing_firmware_task,
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

    async def test_deletes_only_missing_firmware(self, task, platform, add_firmware):
        present = add_firmware(platform, "present.bin")
        gone = add_firmware(platform, "gone.bin", missing=True)

        stats = await task.run()

        assert stats["firmware_found"] == 1
        assert stats["firmware_deleted"] == 1
        assert stats["errors"] == 0
        assert db_firmware_handler.get_firmware(gone.id) is None
        assert db_firmware_handler.get_firmware(present.id) is not None

    async def test_scopes_to_the_given_platforms(
        self, task, platform, other_platform, add_firmware
    ):
        mine = add_firmware(platform, "gone.bin", missing=True)
        theirs = add_firmware(other_platform, "other-gone.bin", missing=True)

        stats = await task.run(platform_ids=[platform.id])

        assert stats["platform_ids"] == [platform.id]
        assert stats["firmware_deleted"] == 1
        assert db_firmware_handler.get_firmware(mine.id) is None
        assert db_firmware_handler.get_firmware(theirs.id) is not None

    async def test_scopes_to_several_platforms_at_once(
        self, task, platform, other_platform, add_firmware
    ):
        mine = add_firmware(platform, "gone.bin", missing=True)
        theirs = add_firmware(other_platform, "other-gone.bin", missing=True)

        stats = await task.run(platform_ids=[platform.id, other_platform.id])

        assert stats["firmware_deleted"] == 2
        assert db_firmware_handler.get_firmware(mine.id) is None
        assert db_firmware_handler.get_firmware(theirs.id) is None

    async def test_counts_delete_failures(self, task, platform, mocker, add_firmware):
        add_firmware(platform, "gone-a.bin", missing=True)
        add_firmware(platform, "gone-b.bin", missing=True)
        mocker.patch(
            "tasks.manual.cleanup_missing_firmware.db_firmware_handler.delete_firmware",
            side_effect=RuntimeError("boom"),
        )

        stats = await task.run()

        assert stats["firmware_found"] == 2
        assert stats["firmware_deleted"] == 0
        assert stats["errors"] == 2

    async def test_no_missing_firmware_is_a_no_op(self, task, platform, add_firmware):
        add_firmware(platform, "present.bin")

        stats = await task.run()

        assert stats == {
            "platform_ids": None,
            "firmware_found": 0,
            "firmware_deleted": 0,
            "errors": 0,
        }
