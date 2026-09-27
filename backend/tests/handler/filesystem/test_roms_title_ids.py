"""Tests for rom-converto title id extraction during scan."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.services.rom_converto import (
    RomConvertoInfo,
    rom_converto_service,
)
from adapters.services.sigil import SigilExtractionResult
from config.config_manager import Config, ConvertoConfig
from handler.filesystem.roms_handler import FSRom, FSRomsHandler, _rom_level_identity
from handler.scan_handler import ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom, RomFile, RomIdentity, SaveTargetLayout
from utils import switch


def _info(**overrides) -> RomConvertoInfo:
    defaults: dict[str, Any] = {
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


def _patch_service(mocker, read_infos=None, enabled: bool = True, scan_metadata=True):
    mocker.patch.object(
        rom_converto_service, "is_enabled", mocker.AsyncMock(return_value=enabled)
    )
    if read_infos is not None:
        mocker.patch.object(rom_converto_service, "read_infos", read_infos)
    mocker.patch(
        "handler.filesystem.roms_handler.cm.get_config",
        lambda: SimpleNamespace(CONVERTO=SimpleNamespace(scan_metadata=scan_metadata)),
    )


class TestReadConvertoTitleIds:
    @pytest.mark.asyncio
    async def test_fills_title_id_and_version(self, handler, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")
        path = Path("/romm/library/psx/roms/game.chd")
        read_infos = mocker.AsyncMock(return_value={path: _info(title_version=65536)})
        _patch_service(mocker, read_infos)

        await handler._read_converto_title_ids([(path, rom_file)])

        assert rom_file.title_id == "SCUS-94163"
        assert rom_file.title_version == 65536

    @pytest.mark.asyncio
    async def test_skips_files_sigil_identified(self, handler, mocker):
        sigil_file = RomFile(file_name="disc1.chd", file_path="psx/roms")
        sigil_file.title_id = "SIGIL-ID"
        other_file = RomFile(file_name="disc2.chd", file_path="psx/roms")
        sigil_path = Path("/lib/disc1.chd")
        other_path = Path("/lib/disc2.chd")
        read_infos = mocker.AsyncMock(
            return_value={other_path: _info(title_id="SLUS-00002")}
        )
        _patch_service(mocker, read_infos)

        await handler._read_converto_title_ids(
            [(sigil_path, sigil_file), (other_path, other_file)]
        )

        read_infos.assert_awaited_once_with([other_path])
        assert sigil_file.title_id == "SIGIL-ID"
        assert other_file.title_id == "SLUS-00002"

    @pytest.mark.asyncio
    async def test_nothing_pending_skips_the_subprocess(self, handler, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")
        rom_file.title_id = "SIGIL-ID"
        read_infos = mocker.AsyncMock()
        _patch_service(mocker, read_infos)

        await handler._read_converto_title_ids([(Path("/lib/game.chd"), rom_file)])

        read_infos.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unrecognized_or_idless_file_stays_unset(self, handler, mocker):
        unknown = RomFile(file_name="a.chd", file_path="psx/roms")
        idless = RomFile(file_name="b.chd", file_path="psx/roms")
        read_infos = mocker.AsyncMock(
            return_value={Path("/lib/b.chd"): _info(title_id=None, title_version=3)}
        )
        _patch_service(mocker, read_infos)

        await handler._read_converto_title_ids(
            [(Path("/lib/a.chd"), unknown), (Path("/lib/b.chd"), idless)]
        )

        assert (unknown.title_id, unknown.title_version) == (None, None)
        assert (idless.title_id, idless.title_version) == (None, None)


PS2_PLATFORM = Platform(name="PlayStation 2", slug="ps2", fs_slug="ps2")


class TestGetRomFilesWithConverto:
    """rom-converto only fills what sigil left unset, in one batch per rom."""

    @pytest.fixture
    def scan_env(self, tmp_path, mocker):
        config = Config(
            EXCLUDED_PLATFORMS=[],
            EXCLUDED_SINGLE_EXT=[],
            EXCLUDED_SINGLE_FILES=[],
            EXCLUDED_MULTI_FILES=[],
            EXCLUDED_MULTI_PARTS_EXT=[],
            EXCLUDED_MULTI_PARTS_FILES=[],
            PLATFORMS_BINDING={},
            PLATFORMS_VERSIONS={},
            STRUCTURE_TEMPLATES={
                "default": "{platform}/roms/{game}",
                "firmware": "{platform}/bios",
            },
            CONVERTO=ConvertoConfig(scan_metadata=True),
        )
        mocker.patch(
            "handler.filesystem.roms_handler.cm.get_config", return_value=config
        )
        mocker.patch.object(
            rom_converto_service, "is_enabled", mocker.AsyncMock(return_value=True)
        )
        mocker.patch.object(
            rom_converto_service, "_info_extensions", frozenset({".iso"})
        )
        handler = FSRomsHandler()
        handler.base_path = tmp_path
        rom_dir = tmp_path / "ps2" / "roms" / "Game"
        rom_dir.mkdir(parents=True)
        for name in ("Game (Disc 1).iso", "Game (Disc 2).iso", "readme.nfo"):
            (rom_dir / name).write_bytes(b"rom-bytes")
        rom = Rom(
            id=1,
            fs_name="Game",
            fs_extension="",
            fs_path="ps2/roms",
            platform=PS2_PLATFORM,
        )
        return SimpleNamespace(handler=handler, rom=rom, rom_dir=rom_dir)

    @pytest.mark.asyncio
    async def test_sigil_id_wins_and_converto_fills_the_rest(self, scan_env, mocker):
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(
                return_value=SigilExtractionResult(
                    title_id="SLUS-00001",
                    save_target="SLUS-00001",
                    usage="folder-prefix",
                )
            ),
        )
        disc2 = scan_env.rom_dir / "Game (Disc 2).iso"
        read_infos = mocker.AsyncMock(
            return_value={disc2: _info(title_id="SLUS-00002", title_version=1)}
        )
        mocker.patch.object(rom_converto_service, "read_infos", read_infos)

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        # Sigil stops after disc 1 off Switch; the nfo has no inspectable extension.
        read_infos.assert_awaited_once_with([disc2])
        ids = {f.file_name: (f.title_id, f.title_version) for f in parsed.rom_files}
        assert ids["Game (Disc 1).iso"] == ("SLUS-00001", None)
        assert ids["Game (Disc 2).iso"] == ("SLUS-00002", 1)
        assert ids["readme.nfo"] == (None, None)
        assert parsed.identity.title_id == "SLUS-00001"

    @pytest.mark.asyncio
    async def test_converto_identity_when_sigil_reads_nothing(self, scan_env, mocker):
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(return_value=None),
        )
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(return_value={disc1: _info(title_id="SLUS-00001")}),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        assert parsed.identity.title_id == "SLUS-00001"
        assert parsed.identity.save_target is None

    @pytest.mark.asyncio
    async def test_converto_identity_is_the_first_disc_whatever_the_listing(
        self, scan_env, mocker
    ):
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(return_value=None),
        )
        list_rom_dir = FSRomsHandler._list_rom_dir
        mocker.patch.object(
            FSRomsHandler,
            "_list_rom_dir",
            lambda self, *args: sorted(list_rom_dir(self, *args), reverse=True),
        )
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        disc2 = scan_env.rom_dir / "Game (Disc 2).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(
                return_value={
                    disc1: _info(title_id="SLUS-00001"),
                    disc2: _info(title_id="SLUS-00002"),
                }
            ),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        assert parsed.identity.title_id == "SLUS-00001"

    @pytest.mark.asyncio
    async def test_stored_ids_give_no_identity_when_extraction_is_skipped(
        self, scan_env, mocker
    ):
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(return_value=None),
        )
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(return_value={disc1: _info(title_id="SLUS-00001")}),
        )
        first = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        rescan = await scan_env.handler.get_rom_files(
            scan_env.rom,
            calculate_hashes=False,
            extract_title_ids=False,
            existing_files=first.rom_files,
        )

        assert {f.title_id for f in rescan.rom_files} >= {"SLUS-00001"}
        assert rescan.identity == RomIdentity()


@pytest.mark.parametrize(
    ("service_state", "expected"),
    [
        pytest.param({}, True, id="enabled"),
        pytest.param({"enabled": False}, False, id="service-disabled"),
        pytest.param({"scan_metadata": False}, False, id="scan-metadata-off"),
    ],
)
async def test_converto_active_for_supported_platform(
    handler, psx_rom, mocker, service_state: dict[str, bool], expected: bool
):
    _patch_service(mocker, **service_state)

    assert await handler._converto_active(psx_rom) is expected


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
) -> FSRom:
    fs_rom: FSRom = {
        "fs_name": "PaRappa the Rapper (USA).chd",
        "fs_path": "psx/roms",
        "flat": True,
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
    mocker.patch(
        "handler.scan_handler.db_rom_handler.add_rom", side_effect=lambda rom: rom
    )
    mocker.patch(
        "handler.scan_handler.cm.get_config",
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
            _rom_file("disc1.bin", title_id="0100ABCD12340800"),
            _rom_file("disc2.bin", title_id="0100ABCD12340000"),
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
