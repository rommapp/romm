"""Tests for CleanupMissingRomsTask."""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from handler.database import db_collection_handler, db_rom_handler
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import Rom
from models.user import User
from tasks.manual.cleanup_missing_roms import (
    CleanupMissingRomsTask,
    cleanup_missing_roms_task,
)


def _add_rom(platform: Platform, name: str, *, missing: bool) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            missing_from_fs=missing,
        )
    )


class TestCleanupMissingRomsTask:
    @pytest.fixture
    def task(self) -> CleanupMissingRomsTask:
        return CleanupMissingRomsTask()

    @pytest.fixture(autouse=True)
    def resources(self, mocker: MockerFixture) -> AsyncMock:
        return mocker.patch(
            "tasks.manual.cleanup_missing_roms.fs_resource_handler.remove_directory",
            new=AsyncMock(),
        )

    def test_module_singleton_exists(self):
        assert isinstance(cleanup_missing_roms_task, CleanupMissingRomsTask)

    async def test_deletes_only_missing_roms(
        self, task: CleanupMissingRomsTask, platform: Platform
    ):
        present = _add_rom(platform, "present", missing=False)
        gone = _add_rom(platform, "gone", missing=True)

        stats = await task.run()

        assert stats["roms_found"] == 1
        assert stats["roms_deleted"] == 1
        assert stats["errors"] == 0
        assert db_rom_handler.get_rom(gone.id) is None
        assert db_rom_handler.get_rom(present.id) is not None

    async def test_drops_cached_filter_values(
        self, task: CleanupMissingRomsTask, platform: Platform, mocker: MockerFixture
    ):
        _add_rom(platform, "gone", missing=True)
        invalidate = mocker.spy(db_rom_handler, "invalidate_filter_values_cache")

        await task.run()

        invalidate.assert_called_once_with()

    async def test_deleted_roms_leave_smart_collections(
        self,
        task: CleanupMissingRomsTask,
        platform: Platform,
        admin_user: User,
    ):
        present = _add_rom(platform, "present", missing=False)
        _add_rom(platform, "gone", missing=True)
        collection = db_collection_handler.add_smart_collection(
            SmartCollection(
                name="Everything here",
                description="",
                user_id=admin_user.id,
                filter_criteria={"platform_ids": [platform.id]},
            )
        )
        seeded = db_collection_handler.refresh_smart_collection(collection.id)
        assert seeded is not None and seeded.rom_count == 2

        await task.run()

        after = db_collection_handler.get_smart_collection(collection.id)
        assert after is not None
        assert after.rom_ids == [present.id]
        assert after.rom_count == 1

    async def test_nothing_deleted_leaves_the_caches_alone(
        self, task: CleanupMissingRomsTask, platform: Platform, mocker: MockerFixture
    ):
        _add_rom(platform, "present", missing=False)
        invalidate = mocker.spy(db_rom_handler, "invalidate_filter_values_cache")
        refresh = mocker.spy(
            db_collection_handler, "refresh_smart_collections_for_roms"
        )

        await task.run()

        invalidate.assert_not_called()
        refresh.assert_not_called()

    async def test_a_failed_delete_is_counted_and_not_refreshed(
        self, task: CleanupMissingRomsTask, platform: Platform, mocker: MockerFixture
    ):
        _add_rom(platform, "gone", missing=True)
        mocker.patch(
            "tasks.manual.cleanup_missing_roms.db_rom_handler.delete_rom",
            side_effect=RuntimeError("boom"),
        )
        refresh = mocker.spy(
            db_collection_handler, "refresh_smart_collections_for_roms"
        )

        stats = await task.run()

        assert stats["errors"] == 1
        assert stats["roms_deleted"] == 0
        refresh.assert_not_called()
