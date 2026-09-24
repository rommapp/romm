"""Tests for ConvertLibraryTask (conversion cache pre-warming)."""

from pathlib import Path

import pytest

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile
from tasks.manual.convert_library import ConvertLibraryTask


@pytest.fixture
def converto_config(mocker):
    """Point the task's config at a policy covering both test platforms."""
    formats = {"test_platform_slug": "chd", "psp": "chd"}
    mocker.patch(
        "tasks.manual.convert_library.cm",
        mocker.Mock(
            **{
                "get_config.return_value.CONVERTO.platform_formats": formats,
                "get_config.return_value.CONVERTO.download_conversion_enabled": True,
            }
        ),
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
    """Fake get_or_convert; returns a cache path per rom."""
    return mocker.patch(
        "tasks.manual.convert_library.get_or_convert",
        side_effect=lambda rom_id, rom_file, platform_slug, target: Path(
            f"/cache/{rom_id}"
        ),
    )


@pytest.fixture
def psp_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(name="psp", slug="psp", fs_slug="psp")
    )


@pytest.fixture
def psp_rom(admin_user, psp_platform: Platform) -> Rom:
    rom = Rom(
        platform_id=psp_platform.id,
        name="psp_rom",
        slug="psp_rom_slug",
        fs_name="game.iso",
        fs_name_no_tags="game",
        fs_name_no_ext="game",
        fs_extension="iso",
        fs_path=f"{psp_platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


@pytest.fixture
def psp_rom_file(psp_rom: Rom) -> RomFile:
    rom_file = RomFile(
        rom_id=psp_rom.id,
        file_name="game.iso",
        file_path=psp_rom.fs_path,
        file_size_bytes=1000,
    )
    return db_rom_handler.add_rom_file(rom_file)


class TestConvertLibraryTask:
    @pytest.fixture
    def task(self) -> ConvertLibraryTask:
        return ConvertLibraryTask()

    def test_configuration(self, task: ConvertLibraryTask):
        assert task.title == "Convert library to target formats"
        assert task.task_type.value == "conversion"
        assert task.enabled is True
        assert task.manual_run is True
        assert task.can_run_manually is True
        assert task.cron_string is None

    async def test_gating_noop_when_conversion_disabled(
        self, task, mocker, converto_config, fake_convert, rom, rom_file
    ):
        mocker.patch(
            "tasks.manual.convert_library.rom_converto_service.is_enabled",
            new_callable=mocker.AsyncMock,
            return_value=False,
        )

        stats = await task.run()

        assert stats["converted"] == 0
        fake_convert.assert_not_called()

    async def test_gating_noop_when_no_platform_formats(
        self, task, mocker, conversion_enabled, fake_convert, rom, rom_file
    ):
        mocker.patch(
            "tasks.manual.convert_library.cm",
            mocker.Mock(**{"get_config.return_value.CONVERTO.platform_formats": {}}),
        )

        stats = await task.run()

        assert stats["converted"] == 0
        fake_convert.assert_not_called()

    async def test_gating_noop_when_download_conversion_disabled(
        self, task, mocker, conversion_enabled, fake_convert, rom, rom_file
    ):
        mocker.patch(
            "tasks.manual.convert_library.cm",
            mocker.Mock(
                **{
                    "get_config.return_value.CONVERTO.platform_formats": {
                        "test_platform_slug": "chd"
                    },
                    "get_config.return_value.CONVERTO.download_conversion_enabled": False,
                }
            ),
        )

        stats = await task.run()

        assert stats["converted"] == 0
        fake_convert.assert_not_called()

    async def test_skips_unresolvable_files(
        self, task, converto_config, conversion_enabled, fake_convert, rom, rom_file
    ):
        # `rom`/`rom_file` live on "test_platform_slug", which rom-converto has
        # no operations for, so resolve_operation always misses.
        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["skipped"] == 1
        assert stats["failed"] == 0
        fake_convert.assert_not_called()

    async def test_skips_multi_file_roms(
        self,
        task,
        converto_config,
        conversion_enabled,
        fake_convert,
        multi_file_rom,
    ):
        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["skipped"] == 1
        fake_convert.assert_not_called()

    async def test_converts_matching_single_file_roms(
        self,
        task,
        converto_config,
        conversion_enabled,
        fake_convert,
        psp_rom,
        psp_rom_file,
    ):
        stats = await task.run()

        assert stats["converted"] == 1
        assert stats["skipped"] == 0
        assert stats["failed"] == 0
        # The task re-queries roms/files in its own session, so the RomFile
        # passed to get_or_convert is a different ORM instance; compare by id.
        fake_convert.assert_called_once()
        rom_id, rom_file, platform_slug, target = fake_convert.call_args.args
        assert (rom_id, rom_file.id, platform_slug, target) == (
            psp_rom.id,
            psp_rom_file.id,
            "psp",
            "chd",
        )

    async def test_counts_failed_conversions(
        self, task, converto_config, conversion_enabled, mocker, psp_rom, psp_rom_file
    ):
        fake_convert = mocker.patch(
            "tasks.manual.convert_library.get_or_convert", return_value=None
        )

        stats = await task.run()

        assert stats["converted"] == 0
        assert stats["failed"] == 1
        fake_convert.assert_called_once()
        rom_id, rom_file, platform_slug, target = fake_convert.call_args.args
        assert (rom_id, rom_file.id, platform_slug, target) == (
            psp_rom.id,
            psp_rom_file.id,
            "psp",
            "chd",
        )

    async def test_platform_id_restricts_scope(
        self,
        task,
        converto_config,
        conversion_enabled,
        fake_convert,
        psp_rom,
        psp_rom_file,
        rom,
        rom_file,
    ):
        """Roms on other platforms are untouched when scoped by platform_id."""
        stats = await task.run(platform_id=psp_rom.platform_id)

        assert stats["platform_id"] == psp_rom.platform_id
        assert stats["converted"] == 1
        assert all(call.args[0] == psp_rom.id for call in fake_convert.call_args_list)
