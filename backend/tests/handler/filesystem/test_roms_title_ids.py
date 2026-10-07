"""Tests for rom-converto's per-file title ids during scan."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.services.rom_converto import RomConvertoInfo, rom_converto_service
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


class TestReadConvertoInfos:
    @pytest.mark.asyncio
    async def test_fills_title_id_and_version(self, handler, mocker):
        rom_file = RomFile(file_name="game.chd", file_path="psx/roms")
        path = Path("/romm/library/psx/roms/game.chd")
        read_infos = mocker.AsyncMock(return_value={path: _info(title_version=65536)})
        _patch_service(mocker, read_infos)

        await handler._read_converto_infos([(path, rom_file)])

        assert rom_file.title_id == "SCUS-94163"
        assert rom_file.title_version == 65536

    @pytest.mark.asyncio
    async def test_no_sources_skip_the_subprocess(self, handler, mocker):
        read_infos = mocker.AsyncMock()
        _patch_service(mocker, read_infos)

        await handler._read_converto_infos([])

        read_infos.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_idless_info_still_sets_version(self, handler, mocker):
        unknown = RomFile(
            file_name="a.chd",
            file_path="psx/roms",
            title_id="old-id",
            title_version=2,
        )
        idless = RomFile(
            file_name="b.chd",
            file_path="psx/roms",
            title_id="old-id",
            title_version=2,
        )
        read_infos = mocker.AsyncMock(
            return_value={Path("/lib/b.chd"): _info(title_id=None, title_version=3)}
        )
        _patch_service(mocker, read_infos)

        await handler._read_converto_infos(
            [(Path("/lib/a.chd"), unknown), (Path("/lib/b.chd"), idless)]
        )

        assert (unknown.title_id, unknown.title_version) == ("old-id", 2)
        assert (idless.title_id, idless.title_version) == (None, 3)

    @pytest.mark.asyncio
    async def test_marks_only_recognized_files(self, handler, mocker):
        recognized = RomFile(file_name="game.chd", file_path="psx/roms")
        unrecognized = RomFile(file_name="missing.chd", file_path="psx/roms")
        recognized_path = Path("/lib/game.chd")
        read_infos = mocker.AsyncMock(return_value={recognized_path: _info()})
        _patch_service(mocker, read_infos)

        await handler._read_converto_infos(
            [(recognized_path, recognized), (Path("/lib/missing.chd"), unrecognized)]
        )

        assert recognized.converto_read_at is not None
        assert unrecognized.converto_read_at is None


PS2_PLATFORM = Platform(name="PlayStation 2", slug="ps2", fs_slug="ps2")


class TestGetRomFilesWithConverto:
    """rom-converto reads each rom's ids in one batch; sigil fills what it left unset."""

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

    @pytest.fixture
    def sigil_reads(self, mocker):
        """Sigil identifies every file as SLUS-00001 with its own save target."""
        return mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(
                return_value=SigilExtractionResult(
                    title_id="SLUS-00001",
                    save_target="SIGIL-TARGET",
                    usage="folder-prefix",
                )
            ),
        )

    @pytest.mark.asyncio
    async def test_converto_id_wins_and_sigil_keeps_the_save_target(
        self, scan_env, sigil_reads, mocker
    ):
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        disc2 = scan_env.rom_dir / "Game (Disc 2).iso"
        read_infos = mocker.AsyncMock(
            return_value={
                disc1: _info(title_id="SLUS-10001", title_version=2),
                disc2: _info(title_id="SLUS-00002", title_version=1),
            }
        )
        mocker.patch.object(rom_converto_service, "read_infos", read_infos)

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        # The nfo has no inspectable extension, so it is never listed.
        await_args = read_infos.await_args
        assert await_args is not None
        (listed,) = await_args.args
        assert sorted(listed) == [disc1, disc2]
        ids = {f.file_name: (f.title_id, f.title_version) for f in parsed.rom_files}
        assert ids["Game (Disc 1).iso"] == ("SLUS-10001", 2)
        assert ids["Game (Disc 2).iso"] == ("SLUS-00002", 1)
        assert ids["readme.nfo"] == (None, None)
        assert parsed.identity.title_id == "SLUS-10001"
        assert parsed.identity.save_target == "SIGIL-TARGET"

    @pytest.mark.asyncio
    async def test_sigil_reads_every_disc_converto_does_not_recognize(
        self, scan_env, mocker
    ):
        mocker.patch.object(
            rom_converto_service, "read_infos", mocker.AsyncMock(return_value={})
        )
        reads = {
            "Game (Disc 1).iso": ("SLUS-20001", "SLUS_200.01", 0),
            "Game (Disc 2).iso": ("SLUS-20002", "SLUS_200.02", 1),
            "readme.nfo": ("SLUS-99999", "SLUS_999.99", 0),
        }

        async def extract(_platform_slug: str, path: str) -> SigilExtractionResult:
            title_id, raw_serial, features = reads[Path(path).name]
            return SigilExtractionResult(
                title_id=title_id,
                save_target=f"BA{title_id}",
                usage="folder-prefix",
                raw_serial=raw_serial,
                features=features,
            )

        extract_title_id = mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            side_effect=extract,
        )
        list_rom_dir = FSRomsHandler._list_rom_dir
        mocker.patch.object(
            FSRomsHandler,
            "_list_rom_dir",
            lambda self, *args: sorted(list_rom_dir(self, *args), reverse=True),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        read = {
            f.file_name: (f.title_id, f.raw_serial, f.sigil_features)
            for f in parsed.rom_files
        }
        assert read == {
            "Game (Disc 1).iso": ("SLUS-20001", "SLUS_200.01", 0),
            "Game (Disc 2).iso": ("SLUS-20002", "SLUS_200.02", 1),
            # Not a disc of the set, so never read.
            "readme.nfo": (None, None, None),
        }
        assert extract_title_id.await_count == 2
        assert parsed.identity.title_id == "SLUS-20001"
        assert parsed.identity.save_target == "BASLUS-20001"

    @pytest.mark.asyncio
    async def test_converto_id_wins_and_sigil_still_stores_the_serial(
        self, scan_env, mocker
    ):
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(return_value={disc1: _info(title_id="SLUS-10001")}),
        )
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(
                return_value=SigilExtractionResult(
                    title_id="SLUS-00001",
                    save_target="SIGIL-TARGET",
                    usage="folder-prefix",
                    raw_serial="SLUS_000.01",
                    features=1,
                )
            ),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        disc1_row = {f.file_name: f for f in parsed.rom_files}["Game (Disc 1).iso"]
        assert (
            disc1_row.title_id,
            disc1_row.raw_serial,
            disc1_row.sigil_features,
        ) == ("SLUS-10001", "SLUS_000.01", 1)

    @pytest.mark.asyncio
    async def test_a_stored_sigil_id_yields_to_a_fresh_extraction(
        self, scan_env, sigil_reads, mocker
    ):
        mocker.patch.object(
            rom_converto_service, "read_infos", mocker.AsyncMock(return_value={})
        )
        first = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )
        by_name = {f.file_name: f for f in first.rom_files}
        by_name["Game (Disc 1).iso"].title_id = "SLUS-99999"

        rescan = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False, existing_files=first.rom_files
        )

        ids = {f.file_name: f.title_id for f in rescan.rom_files}
        assert ids["Game (Disc 1).iso"] == "SLUS-00001"
        assert rescan.identity.title_id == "SLUS-00001"

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
    async def test_stored_identity_survives_matching_converto_id(
        self, scan_env, mocker
    ):
        stored = RomIdentity(
            title_id="SLUS-00001",
            save_target="stored-target",
            save_target_layout=SaveTargetLayout.FILE_PREFIX,
        )
        scan_env.rom.title_id = stored.title_id
        scan_env.rom.save_target = stored.save_target
        scan_env.rom.save_target_layout = stored.save_target_layout
        mocker.patch(
            "adapters.services.sigil.SigilService.extract_title_id",
            mocker.AsyncMock(return_value=None),
        )
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(return_value={disc1: _info(title_id=stored.title_id)}),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        assert parsed.identity == stored

    @pytest.mark.asyncio
    async def test_title_ids_land_on_new_file_rows(self, scan_env, mocker):
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(
                return_value={disc1: _info(title_id="SLUS-10001", title_version=1)}
            ),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )

        by_name = {f.file_name: f for f in parsed.rom_files}
        disc1_row = by_name["Game (Disc 1).iso"]
        assert (disc1_row.title_id, disc1_row.title_version) == ("SLUS-10001", 1)
        # A file rom-converto returned nothing for stays unread.
        assert by_name["Game (Disc 2).iso"].converto_read_at is None

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

    @pytest.mark.asyncio
    async def test_title_ids_still_land_when_extraction_is_skipped(
        self, scan_env, mocker
    ):
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        mocker.patch.object(
            rom_converto_service,
            "read_infos",
            mocker.AsyncMock(return_value={disc1: _info(title_id="SLUS-10001")}),
        )

        parsed = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False, extract_title_ids=False
        )

        by_name = {f.file_name: f for f in parsed.rom_files}
        assert by_name["Game (Disc 1).iso"].title_id == "SLUS-10001"
        # Skipping extraction also skips the rom-level id fallback, so the
        # save target sigil wrote stays untouched.
        assert parsed.identity == RomIdentity()

    @pytest.mark.asyncio
    async def test_unchanged_rows_are_not_reread(self, scan_env, sigil_reads, mocker):
        discs = [scan_env.rom_dir / f"Game (Disc {n}).iso" for n in (1, 2)]
        read_infos = mocker.AsyncMock(return_value={disc: _info() for disc in discs})
        mocker.patch.object(rom_converto_service, "read_infos", read_infos)
        first = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )
        read_infos.reset_mock()

        rescan = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False, existing_files=first.rom_files
        )

        read_infos.assert_not_awaited()
        assert {f.file_name for f in rescan.rom_files} == {
            "Game (Disc 1).iso",
            "Game (Disc 2).iso",
            "readme.nfo",
        }

    @pytest.mark.asyncio
    async def test_unchanged_rows_rom_converto_never_read_are_backfilled(
        self, scan_env, sigil_reads, mocker
    ):
        disc1 = scan_env.rom_dir / "Game (Disc 1).iso"
        read_infos = mocker.AsyncMock(return_value={})
        mocker.patch.object(rom_converto_service, "read_infos", read_infos)
        first = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False
        )
        read_infos.reset_mock()
        read_infos.return_value = {disc1: _info(title_id="SLUS-10001")}

        rescan = await scan_env.handler.get_rom_files(
            scan_env.rom, calculate_hashes=False, existing_files=first.rom_files
        )

        read_infos.assert_awaited_once()
        await_args = read_infos.await_args
        assert await_args is not None
        assert set(await_args.args[0]) == {
            disc1,
            scan_env.rom_dir / "Game (Disc 2).iso",
        }
        by_name = {f.file_name: f for f in rescan.rom_files}
        assert by_name["Game (Disc 1).iso"].title_id == "SLUS-10001"
        assert by_name["Game (Disc 1).iso"].converto_read_at is not None
        assert by_name["Game (Disc 2).iso"].converto_read_at is None


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

    assert await handler.converto_active(psx_rom.platform_slug) is expected


async def test_converto_active_false_for_unsupported_platform(handler, mocker):
    _patch_service(mocker)

    assert await handler.converto_active("n64") is False


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
    """A sigil extraction (already holding rom-converto's id) wins; else a file's bare id."""

    def test_no_files_returns_empty_identity(self):
        assert _rom_level_identity("psx", [], [], RomIdentity()) == RomIdentity()

    def test_converto_only_ids_use_first_found(self):
        files = [
            _rom_file("disc1.chd", title_id=None),
            _rom_file("disc2.chd", title_id="SCUS-94163"),
            _rom_file("disc3.chd", title_id="OTHER-ID"),
        ]
        identity = _rom_level_identity("psx", [], files, RomIdentity())
        assert identity.title_id == "SCUS-94163"
        assert identity.save_target is None

    def test_non_switch_first_file_id_wins_even_if_later_looks_like_base_id(self):
        # These ids are shaped like Switch update/base ids, but the platform
        # is not Switch, so the base-id preference must not kick in.
        files = [
            _rom_file("disc1.bin", title_id="0100ABCD12340800"),
            _rom_file("disc2.bin", title_id="0100ABCD12340000"),
        ]
        identity = _rom_level_identity("psx", [], files, RomIdentity())
        assert identity.title_id == "0100ABCD12340800"

    def test_non_switch_first_extraction_wins_even_if_later_looks_like_base_id(
        self,
    ):
        extractions = [
            SigilExtractionResult("SLUS-21000", "BASLUS-21000", "folder-prefix"),
            SigilExtractionResult("SLUS-20000", "BASLUS-20000", "folder-prefix"),
        ]
        assert switch.is_base_title_id("SLUS-20000")

        identity = _rom_level_identity("ps2", extractions, [], RomIdentity())

        assert identity.title_id == "SLUS-21000"

    def test_switch_picks_base_id_when_present_among_converto_ids(self):
        files = [
            _rom_file("update.nsp", title_id="0100ABCD12340800"),
            _rom_file("base.nsp", title_id="0100ABCD12340000"),
        ]
        identity = _rom_level_identity("switch", [], files, RomIdentity())
        assert identity.title_id == "0100ABCD12340000"
        assert switch.is_base_title_id(identity.title_id)
        assert identity.save_target == "0100ABCD12340000"
        assert identity.save_target_layout == SaveTargetLayout.FOLDER_EXACT

    def test_switch_base_id_keeps_the_stored_save_target(self):
        stored = RomIdentity(
            title_id="0100ABCD12340000",
            save_target="stored-target",
            save_target_layout=SaveTargetLayout.FOLDER_EXACT,
        )
        files = [_rom_file("base.nsp", title_id="0100ABCD12340000")]
        assert _rom_level_identity("switch", [], files, stored) == stored

    def test_switch_derives_base_id_when_only_update_id_present(self):
        files = [_rom_file("update.nsp", title_id="0100ABCD12340800")]
        identity = _rom_level_identity("switch", [], files, RomIdentity())

        assert identity.title_id == "0100ABCD12340000"
        assert identity.save_target == "0100ABCD12340000"
        assert identity.save_target_layout == SaveTargetLayout.FOLDER_EXACT

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [
            pytest.param(
                RomIdentity(
                    title_id="SCUS-94163",
                    save_target="SCUS-94163",
                    save_target_layout=SaveTargetLayout.FILE_PREFIX,
                ),
                RomIdentity(
                    title_id="SCUS-94163",
                    save_target="SCUS-94163",
                    save_target_layout=SaveTargetLayout.FILE_PREFIX,
                ),
                id="same-id-keeps-the-stored-save-target",
            ),
            pytest.param(
                RomIdentity(
                    title_id="SLUS-00001",
                    save_target="SLUS-00001",
                    save_target_layout=SaveTargetLayout.FILE_PREFIX,
                ),
                RomIdentity(title_id="SCUS-94163"),
                id="another-id-drops-the-stored-save-target",
            ),
        ],
    )
    def test_converto_fallback_against_the_stored_identity(
        self, stored: RomIdentity, expected: RomIdentity
    ):
        # sigil read nothing this pass, e.g. a transient read error.
        files = [_rom_file("game.chd", title_id="SCUS-94163")]

        assert _rom_level_identity("psx", [], files, stored) == expected

    def test_extraction_wins_over_file_ids(self):
        files = [_rom_file("game.chd", title_id="CONVERTO-ID")]
        extraction = SigilExtractionResult(
            title_id="SIGIL-ID", save_target="SIGIL-TARGET", usage="file-prefix"
        )

        identity = _rom_level_identity("psx", [extraction], files, RomIdentity())

        assert identity.title_id == "SIGIL-ID"
        assert identity.save_target == "SIGIL-TARGET"
        assert identity.save_target_layout == SaveTargetLayout.FILE_PREFIX
