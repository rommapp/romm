"""Tests for ConvertLibraryTask (conversion cache pre-warming)."""

import pytest

from handler.database import db_rom_handler
from models.rom import Rom, RomFile
from tasks.manual.convert_library import ConvertLibraryTask, convert_library_task

FORMATS = {"test_platform_slug": "chd"}


@pytest.fixture
def convertto_config(mocker):
    """Point the task's config at a policy covering the test platform."""
    mocker.patch(
        "tasks.manual.convert_library.cm",
        mocker.Mock(**{"get_config.return_value.CONVERTTO.platform_formats": FORMATS}),
    )


@pytest.fixture
def conversion_enabled(mocker):
    mocker.patch(
        "tasks.manual.convert_library.rom_converto_service.is_enabled",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )


@pytest.fixture
def fake_convert(mocker):
    """Fake get_or_convert; returns the cache path per rom, or None."""
    return mocker.patch(
        "tasks.manual.convert_library.get_or_convert",
        side_effect=lambda rom_id, rom_file, target: mocker.Mock(name=str(rom_id)),
    )


class TestConvertLibraryTask:
    @pytest.fixture
    def task(self) -> ConvertLibraryTask:
        return ConvertLibraryTask()

    def test_module_singleton_exists(self):
        assert isinstance(convert_library_task, ConvertLibraryTask)

    def test_configuration(self, task: ConvertLibraryTask):
        assert task.title == "Convert library to target formats"
        assert task.task_type.value == "conversion"
        assert task.enabled is True
        assert task.manual_run is True
        assert task.can_run_manually is True
        assert task.cron_string is None

    async def test_gating_noop_when_conversion_disabled(
        self, task, convertto_config, fake_convert, rom, rom_file
    ):
        stats = await task.run()

        assert stats["converted"] == 0
        fake_convert.assert_not_called()

    async def test_gating_noop_when_no_platform_formats(
        self, task, mocker, conversion_enabled, fake_convert, rom, rom_file
    ):
        mocker.patch(
            "tasks.manual.convert_library.cm",
            mocker.Mock(**{"get_config.return_value.CONVERTTO.platform_formats": {}}),
        )

        stats = await task.run()

        assert stats["converted"] == 0
        fake_convert.assert_not_called()

    async def test_converts_single_file_roms_with_matching_extension(
        self,
        task,
        convertto_config,
        conversion_enabled,
        fake_convert,
        rom,
        rom_file,
    ):
        # rom_file fixture: test_rom.zip at the rom root; target is chd.
        stats = await task.run()

        assert stats["converted"] == 1
        assert stats["skipped"] == 0
        assert stats["failed"] == 0
        fake_convert.assert_called_once_with(rom.id, rom_file, "chd")

    async def test_skips_already_target_format_files(
        self,
        task,
        convertto_config,
        conversion_enabled,
        fake_convert,
        rom,
        rom_file,
    ):
        db_rom_handler.update_rom_file(rom_file.id, {"file_name": "test_rom.chd"})

        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["skipped"] == 1
        fake_convert.assert_not_called()

    async def test_skips_multi_file_roms(
        self,
        task,
        convertto_config,
        conversion_enabled,
        fake_convert,
        multi_file_rom,
    ):
        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["skipped"] == 1
        fake_convert.assert_not_called()

    async def test_counts_failed_conversions(
        self, task, convertto_config, conversion_enabled, mocker, rom, rom_file
    ):
        fake_convert = mocker.patch(
            "tasks.manual.convert_library.get_or_convert", return_value=None
        )

        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["failed"] == 1
        fake_convert.assert_called_once_with(rom.id, rom_file, "chd")

    async def test_platform_id_restricts_scope(
        self,
        task,
        convertto_config,
        conversion_enabled,
        fake_convert,
        other_platform,
        admin_user,
        rom,
        rom_file,
    ):
        """Roms on other platforms are untouched when scoped by platform_id."""
        other_rom = db_rom_handler.add_rom(
            Rom(
                platform_id=other_platform.id,
                name="other_rom",
                slug="other_rom_slug",
                fs_name="other_rom.zip",
                fs_name_no_tags="other_rom",
                fs_name_no_ext="other_rom",
                fs_extension="zip",
                fs_path=f"{other_platform.slug}/roms",
            )
        )
        db_rom_handler.add_rom_user(rom_id=other_rom.id, user_id=admin_user.id)
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=other_rom.id,
                file_name="other_rom.zip",
                file_path=other_rom.fs_path,
                file_size_bytes=1000,
            )
        )

        stats = await task.run(platform_id=rom.platform_id)

        assert stats["platform_id"] == rom.platform_id
        assert stats["converted"] == 1
        assert all(call.args[0] == rom.id for call in fake_convert.call_args_list)
