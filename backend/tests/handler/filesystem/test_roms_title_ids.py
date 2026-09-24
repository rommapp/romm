"""Tests for rom-converto title id extraction during scan."""

from types import SimpleNamespace

import pytest

from adapters.services.rom_converto import (
    RomConvertoError,
    RomConvertoInfo,
    rom_converto_service,
)
from adapters.services.sigil import SigilExtractionResult
from handler import scan_handler as scan_handler_module
from handler.filesystem.roms_handler import FSRomsHandler, _rom_level_identity
from handler.scan_handler import ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom, RomFile, RomIdentity, SaveTargetLayout
from utils import switch


def _info(**overrides) -> RomConvertoInfo:
    defaults = {
        "kind": "psx",
        "title_id": "SCUS-94163",
        "title_version": None,
    }
    defaults.update(overrides)
    return RomConvertoInfo(**defaults)


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
        lambda: SimpleNamespace(CONVERTO=SimpleNamespace(scan_metadata=scan_metadata)),
    )


class TestReadConvertoTitleId:
    @pytest.mark.asyncio
    async def test_sets_title_id_and_version(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return _info(title_version=65536)

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id == "SCUS-94163"
        assert rom_file.title_version == 65536

    @pytest.mark.asyncio
    async def test_no_title_id_leaves_column_none(self, handler, psx_rom, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")

        async def read_info(path):
            return _info(title_id=None)

        _patch_service(mocker, read_info)

        await handler._read_converto_title_id(rom_file)

        assert rom_file.title_id is None
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


async def test_converto_active_for_supported_platform(handler, psx_rom, mocker):
    _patch_service(mocker)

    assert await handler._converto_active(psx_rom) is True


async def test_converto_active_false_when_service_disabled(handler, psx_rom, mocker):
    _patch_service(mocker, enabled=False)

    assert await handler._converto_active(psx_rom) is False


async def test_converto_active_false_when_scan_metadata_disabled(
    handler, psx_rom, mocker
):
    _patch_service(mocker, scan_metadata=False)

    assert await handler._converto_active(psx_rom) is False


async def test_converto_active_false_for_unsupported_platform(handler, mocker):
    rom = Rom(
        id=1,
        fs_name="Paper Mario (USA).z64",
        fs_path="n64/roms",
        fs_extension="z64",
        platform=Platform(name="Nintendo 64", slug="n64", fs_slug="n64"),
    )
    _patch_service(mocker)

    assert await handler._converto_active(rom) is False


def _fs_rom(
    files: list[RomFile], sha1_hash: str, identity: RomIdentity | None = None
) -> dict:
    fs_rom = {
        "fs_name": "PaRappa the Rapper (USA).chd",
        "flat": True,
        "nested": False,
        "files": files,
        "crc_hash": "",
        "md5_hash": "",
        "sha1_hash": sha1_hash,
        "ra_hash": "",
    }
    if identity is not None:
        fs_rom["identity"] = identity
    return fs_rom


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
    async def test_title_id_flows_from_identity(self, patched_scan_env, psx_rom):
        # get_rom_files resolves the rom-level identity from converto/sigil;
        # scan_rom trusts what fs_rom carries.
        scanned = await scan_rom(
            scan_type=ScanType.QUICK,
            platform=psx_rom.platform,
            rom=psx_rom,
            fs_rom=_fs_rom(
                [_rom_file("game.chd", sha1_hash="abc123")],
                sha1_hash="abc123",
                identity=RomIdentity(title_id="SCUS-94163"),
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
                identity=RomIdentity(title_id="SCUS-94163"),
            ),
            metadata_sources=[],
            newly_added=True,
        )

        assert scanned.title_id == "SCUS-94163"


class TestRomLevelIdentity:
    """Sigil wins when it ran; otherwise a converto-tagged file's bare id is used."""

    def test_no_files_returns_empty_identity(self):
        assert _rom_level_identity("psx", [], []) == RomIdentity()

    def test_converto_only_ids_use_first_found(self):
        files = [
            _rom_file("disc1.chd", title_id=None),
            _rom_file("disc2.chd", title_id="SCUS-94163"),
            _rom_file("disc3.chd", title_id="OTHER-ID"),
        ]
        identity = _rom_level_identity("psx", [], files)
        assert identity.title_id == "SCUS-94163"
        assert identity.save_target is None

    def test_non_switch_first_file_id_wins_even_if_later_looks_like_base_id(self):
        # These ids are shaped like Switch update/base ids, but the platform
        # is not Switch, so the base-id preference must not kick in.
        files = [
            _rom_file("update.bin", title_id="0100ABCD12340800"),
            _rom_file("base.bin", title_id="0100ABCD12340000"),
        ]
        identity = _rom_level_identity("psx", [], files)
        assert identity.title_id == "0100ABCD12340800"

    def test_switch_picks_base_id_when_present_among_converto_ids(self):
        files = [
            _rom_file("update.nsp", title_id="0100ABCD12340800"),
            _rom_file("base.nsp", title_id="0100ABCD12340000"),
        ]
        identity = _rom_level_identity("switch", [], files)
        assert identity.title_id == "0100ABCD12340000"
        assert switch.is_base_title_id(identity.title_id)

    def test_switch_derives_base_id_when_only_update_id_present(self):
        files = [_rom_file("update.nsp", title_id="0100ABCD12340800")]
        identity = _rom_level_identity("switch", [], files)

        assert identity.title_id == "0100ABCD12340000"
        assert identity.save_target == "0100ABCD12340000"
        assert identity.save_target_layout == SaveTargetLayout.FOLDER_EXACT

    def test_sigil_extraction_wins_over_converto_ids(self):
        files = [_rom_file("game.chd", title_id="CONVERTO-ID")]
        extraction = SigilExtractionResult(
            title_id="SIGIL-ID", save_target="SIGIL-TARGET", usage="file-prefix"
        )

        identity = _rom_level_identity("psx", [extraction], files)

        assert identity.title_id == "SIGIL-ID"
        assert identity.save_target == "SIGIL-TARGET"
        assert identity.save_target_layout == SaveTargetLayout.FILE_PREFIX
