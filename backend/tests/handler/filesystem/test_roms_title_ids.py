"""Tests for rom-converto title id extraction during scan."""

import asyncio
from types import SimpleNamespace

import pytest
from adapters.services.rom_converto import RomConvertoError, rom_converto_service
from handler import scan_handler as scan_handler_module
from handler.filesystem.roms_handler import FSRomsHandler, _merged_rom_title_id
from handler.scan_handler import ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom, RomFile


def _info(**overrides) -> dict:
    return {
        "kind": "psx",
        "title_id": "SCUS-94163",
        "serial": "SCUS-94163",
        "names": {"": "PaRappa the Rapper"},
        "region": "NTSC-U",
        "version": None,
        "encrypted": False,
        **overrides,
    }


@pytest.fixture
def handler() -> FSRomsHandler:
    return FSRomsHandler()


@pytest.fixture
def psx_rom() -> Rom:
    return Rom(
        id=1,
        fs_name="PaRappa the Rapper (USA).chd",
        fs_path="psx/roms",
        fs_extension="chd",
        platform=Platform(name="PlayStation", slug="psx", fs_slug="psx"),
    )


def _patch_service(mocker, read_info=None, enabled: bool = True, scan_metadata=True):
    mocker.patch.object(
        rom_converto_service, "is_enabled", mocker.AsyncMock(return_value=enabled)
    )
    if read_info is not None:
        mocker.patch.object(rom_converto_service, "read_info", read_info)
    mocker.patch(
        "handler.filesystem.roms_handler.cm.get_config",
        lambda: SimpleNamespace(CONVERTTO=SimpleNamespace(scan_metadata=scan_metadata)),
    )


class TestReadConvertoTitleId:
    @pytest.mark.asyncio
    async def test_sets_title_id_and_version(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return _info(version="65536")

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id == "SCUS-94163"
        assert rom_file.title_version == 65536

    @pytest.mark.asyncio
    async def test_serial_fallback(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return _info(title_id=None, serial="SLPS-91100")

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id == "SLPS-91100"
        assert rom_file.title_version is None

    @pytest.mark.asyncio
    async def test_non_integer_version_is_none(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return _info(title_id="TITLE-1", version="1.2.3")

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id == "TITLE-1"
        assert rom_file.title_version is None

    @pytest.mark.asyncio
    async def test_unrecognized_file_is_skipped(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return None

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id is None
        assert rom_file.title_version is None

    @pytest.mark.asyncio
    async def test_error_does_not_fail_scan(self, handler, psx_rom, mocker):
        rom_files = [
            RomFile(file_name="game.chd", file_path="psx/roms"),
            RomFile(file_name="game2.chd", file_path="psx/roms"),
        ]

        async def read_info(path):
            if "game.chd" in str(path):
                raise RomConvertoError("boom")
            return _info(title_id="TITLE-2")

        _patch_service(mocker, read_info)

        for rom_file in rom_files:
            await handler._read_converto_title_id(rom_file)

        assert rom_files[0].title_id is None
        assert rom_files[0].title_version is None
        assert rom_files[1].title_id == "TITLE-2"

    @pytest.mark.asyncio
    async def test_unexpected_error_does_not_fail_scan(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            raise RuntimeError("boom")

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id is None
        assert rom_file.title_version is None


def test_converto_active_for_supported_platform(handler, psx_rom, mocker):
    _patch_service(mocker)

    assert asyncio.run(handler._converto_active(psx_rom)) is True


def test_converto_active_false_when_service_disabled(handler, psx_rom, mocker):
    _patch_service(mocker, enabled=False)

    assert asyncio.run(handler._converto_active(psx_rom)) is False


def test_converto_active_false_when_scan_metadata_disabled(handler, psx_rom, mocker):
    _patch_service(mocker, scan_metadata=False)

    assert asyncio.run(handler._converto_active(psx_rom)) is False


def test_converto_active_false_for_unsupported_platform(handler, mocker):
    rom = Rom(
        id=1,
        fs_name="Paper Mario (USA).z64",
        fs_path="n64/roms",
        fs_extension="z64",
        platform=Platform(name="Nintendo 64", slug="n64", fs_slug="n64"),
    )
    _patch_service(mocker)

    assert asyncio.run(handler._converto_active(rom)) is False


def _fs_rom(files: list[RomFile], sha1_hash: str, title_id: str | None = None) -> dict:
    return {
        "fs_name": "PaRappa the Rapper (USA).chd",
        "flat": True,
        "nested": False,
        "files": files,
        "crc_hash": "",
        "md5_hash": "",
        "sha1_hash": sha1_hash,
        "ra_hash": "",
        "title_id": title_id,
    }


def _rom_file(name: str, **kwargs) -> RomFile:
    return RomFile(file_name=name, file_path="psx/roms", file_size_bytes=1, **kwargs)


@pytest.fixture
def patched_scan_env(mocker):
    mocker.patch.object(
        scan_handler_module.db_rom_handler, "add_rom", side_effect=lambda rom: rom
    )
    mocker.patch.object(
        scan_handler_module.cm,
        "get_config",
        return_value=SimpleNamespace(
            SCAN_METADATA_PRIORITY=[],
            SCAN_ARTWORK_PRIORITY=[],
            SCAN_ARTWORK_PRIORITY_OVERRIDES={},
        ),
    )


class TestScanRomTitleId:
    @pytest.mark.asyncio
    async def test_title_id_flows_from_merged_value(self, patched_scan_env, psx_rom):
        # get_rom_files merged converto's file ids with sigil's rom-level
        # value; scan_rom trusts what fs_rom carries.
        scanned = await scan_rom(
            scan_type=ScanType.QUICK,
            platform=psx_rom.platform,
            rom=psx_rom,
            fs_rom=_fs_rom(
                [_rom_file("game.chd", sha1_hash="abc123")],
                sha1_hash="abc123",
                title_id="SCUS-94163",
            ),
            metadata_sources=[],
            newly_added=True,
        )

        assert scanned.title_id == "SCUS-94163"

    @pytest.mark.asyncio
    async def test_title_id_carried_forward_without_files(
        self, patched_scan_env, psx_rom
    ):
        psx_rom.title_id = "SCUS-94163"
        scanned = await scan_rom(
            scan_type=ScanType.QUICK,
            platform=psx_rom.platform,
            rom=psx_rom,
            fs_rom=_fs_rom([], sha1_hash=""),
            metadata_sources=[],
            newly_added=True,
        )

        assert scanned.title_id == "SCUS-94163"

    @pytest.mark.asyncio
    async def test_title_id_preserved_when_files_yield_none(
        self, patched_scan_env, psx_rom
    ):
        # Files are present but extraction finds no title id on any of them;
        # the re-scan must keep the value already stored on the rom.
        psx_rom.title_id = "SCUS-94163"
        scanned = await scan_rom(
            scan_type=ScanType.QUICK,
            platform=psx_rom.platform,
            rom=psx_rom,
            fs_rom=_fs_rom(
                [_rom_file("game.chd", sha1_hash="abc123")], sha1_hash="abc123"
            ),
            metadata_sources=[],
            newly_added=True,
        )

        assert scanned.title_id == "SCUS-94163"

    @pytest.mark.asyncio
    async def test_title_id_updated_with_new_value(self, patched_scan_env, psx_rom):
        # A new truthy title id from the re-scan must overwrite the stored one.
        psx_rom.title_id = "OLD-ID"
        scanned = await scan_rom(
            scan_type=ScanType.QUICK,
            platform=psx_rom.platform,
            rom=psx_rom,
            fs_rom=_fs_rom(
                [_rom_file("game.chd", sha1_hash="abc123")],
                sha1_hash="abc123",
                title_id="SCUS-94163",
            ),
            metadata_sources=[],
            newly_added=True,
        )

        assert scanned.title_id == "SCUS-94163"


class TestMergedRomTitleId:
    """Converto-first precedence: converto's file ids win, sigil fills gaps."""

    def test_converto_id_wins_over_sigil(self):
        files = [_rom_file("game.chd", title_id="CONVERTO-ID")]
        assert _merged_rom_title_id(files, "SIGIL-ID") == "CONVERTO-ID"

    def test_first_converto_id_in_scan_order_wins(self):
        files = [
            _rom_file("disc1.chd", title_id=None),
            _rom_file("disc2.chd", title_id="FIRST-FOUND"),
            _rom_file("dlc.chd", title_id="LATER"),
        ]
        assert _merged_rom_title_id(files, "SIGIL-ID") == "FIRST-FOUND"

    def test_sigil_fills_when_converto_found_none(self):
        files = [_rom_file("game.chd"), _rom_file("game2.chd")]
        assert _merged_rom_title_id(files, "SIGIL-ID") == "SIGIL-ID"

    def test_none_when_neither_extracted(self):
        files = [_rom_file("game.chd")]
        assert _merged_rom_title_id(files, None) is None
