import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.services import rom_converto
from adapters.services.rom_converto import (
    TARGETS_BY_PLATFORM,
    Operation,
    RomConvertoBinaryNotFoundError,
    RomConvertoInfo,
    RomConvertoOperationError,
    RomConvertoService,
    RomConvertoTimeoutError,
    resolve_operation,
)


class FakeProc:
    def __init__(
        self,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        delay: float = 0.0,
    ):
        self._stdout = stdout
        self._stderr = stderr
        self._delay = delay
        self.killed = False
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._delay and not self.killed:
            await asyncio.sleep(self._delay)
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True


@pytest.fixture
def service() -> RomConvertoService:
    return RomConvertoService()


class TestRun:
    async def test_binary_missing_raises(self) -> None:
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(RomConvertoBinaryNotFoundError),
        ):
            await rom_converto._run(["info", "--json", "x"], timeout_seconds=1)

    async def test_timeout_kills_process(self) -> None:
        proc = FakeProc(delay=5.0)
        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
            pytest.raises(RomConvertoTimeoutError),
        ):
            await rom_converto._run(["info", "--json", "x"], timeout_seconds=0.01)
        assert proc.killed is True


class TestIsEnabled:
    async def test_disabled_when_config_disabled(self, service: RomConvertoService):
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", False),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
        ):
            assert await service.is_enabled() is False

    async def test_probe_fail_cached_false(self, service: RomConvertoService):
        proc = FakeProc(returncode=1)
        spawn_count = 0

        async def spawn(*args, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            return proc

        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", spawn),
        ):
            assert await service.is_enabled() is False
            assert await service.is_enabled() is False
        assert spawn_count == 1

    async def test_probe_ok_logs_version(self, service: RomConvertoService, mocker):
        log_info = mocker.patch.object(rom_converto.log, "info")
        proc = FakeProc(stdout=b'{"version": "0.21.0"}')
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.is_enabled() is True
        assert log_info.call_count == 1

    async def test_missing_binary_not_cached(self, service: RomConvertoService):
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value=None),
        ):
            assert await service.is_enabled() is False

        proc = FakeProc(stdout=b'{"version": "0.21.0"}')
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.is_enabled() is True


class TestReadInfo:
    async def test_nonzero_returns_none(self, service: RomConvertoService):
        proc = FakeProc(
            returncode=1,
            stderr=b"error: could not detect console for path: /roms/junk.bin",
        )
        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.read_info(Path("/roms/junk.bin")) is None

    async def test_non_json_output_returns_none(self, service: RomConvertoService):
        proc = FakeProc(returncode=0, stdout=b"not json at all")
        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.read_info(Path("/roms/game.iso")) is None

    async def test_parses_nx_payload(self, service: RomConvertoService):
        payload = json.dumps(
            {
                "kind": "nx",
                "container_kind": "nsp",
                "full": {
                    "application_title_id_hex": "0100ABCD12345000",
                    "title_version": 65536,
                },
            }
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            info = await service.read_info(Path("/roms/game.nsp"))

        assert info == RomConvertoInfo(
            kind="nx", title_id="0100ABCD12345000", title_version=65536
        )


class TestParseInfo:
    def test_nx_without_prod_keys_has_no_title_id(self):
        payload = {"kind": "nx", "container_kind": "nsp"}

        info = rom_converto._parse_info(payload)

        assert info == RomConvertoInfo(kind="nx", title_id=None, title_version=None)

    def test_chd_inner_disc_flattens_content(self):
        payload = {"kind": "chd", "content": {"kind": "psx", "title_id": "SLUS-00594"}}

        info = rom_converto._parse_info(payload)

        assert info == RomConvertoInfo(
            kind="chd", title_id="SLUS-00594", title_version=None
        )

    def test_dol_hex_encodes_game_id(self):
        payload = {"kind": "dol", "game_id": "GZLE01"}

        info = rom_converto._parse_info(payload)

        assert info.title_id == "475A4C45"

    def test_rvl_hex_encodes_game_id(self):
        payload = {"kind": "rvl", "game_id": "RZTE01"}

        info = rom_converto._parse_info(payload)

        assert info.title_id == "525A5445"

    def test_wup_takes_last_8_of_title_id_hex(self):
        payload = {
            "kind": "wup",
            "title_id_hex": "0005000010143500",
            "title_version": 16,
        }

        info = rom_converto._parse_info(payload)

        assert info.title_id == "10143500"
        assert info.title_version == 16

    def test_xbox_uses_nested_xbe_title_id_code(self):
        payload = {
            "kind": "xbox",
            "xbe": {"title_id_code": "TT-027", "title_id_hex": "5454001B"},
        }

        info = rom_converto._parse_info(payload)

        assert info.title_id == "TT-027"

    def test_xenon_uses_nested_xex_title_id_hex(self):
        payload = {"kind": "xenon", "xex": {"title_id_hex": "4D5307DC"}}

        info = rom_converto._parse_info(payload)

        assert info.title_id == "4D5307DC"

    def test_ctr_title_id_ignores_product_code(self):
        payload = {
            "kind": "ctr",
            "title_id": "0004000000123456",
            "product_code": "CTR-P-AXXE",
        }

        info = rom_converto._parse_info(payload)

        assert info.title_id == "0004000000123456"

    def test_nds_falls_back_to_game_code(self):
        payload = {"kind": "nds", "game_code": "AXXE"}

        info = rom_converto._parse_info(payload)

        assert info.title_id == "AXXE"

    def test_ps3_string_version_is_none(self):
        payload = {"kind": "ps3", "title_id": "BLUS31426", "version": "01.00"}

        info = rom_converto._parse_info(payload)

        assert info.title_id == "BLUS31426"
        assert info.title_version is None


class TestConvert:
    def _op(self) -> Operation:
        return Operation(
            target="chd",
            platforms=frozenset({"psp"}),
            argv=("chd", "compress"),
            input_exts=frozenset({".iso"}),
            output_ext=".chd",
        )

    async def test_argv_is_operation_argv_plus_src_and_out(
        self, service: RomConvertoService, tmp_path: Path
    ):
        recorded: list[list[str]] = []

        async def fake_run(argv: list[str], timeout_seconds: float):
            recorded.append(argv)
            return 0, "", ""

        src = tmp_path / "game.iso"
        out = tmp_path / "game.chd"
        with patch.object(rom_converto, "_run", fake_run):
            await service.convert(self._op(), src, out)

        assert recorded == [["chd", "compress", str(src), str(out)]]

    async def test_nonzero_raises_operation_error_with_stderr(
        self, service: RomConvertoService, tmp_path: Path
    ):
        async def fake_run(argv: list[str], timeout_seconds: float):
            return 1, "", "error: bad disc key"

        src = tmp_path / "game.iso"
        out = tmp_path / "game.chd"
        with (
            patch.object(rom_converto, "_run", fake_run),
            pytest.raises(RomConvertoOperationError) as exc_info,
        ):
            await service.convert(self._op(), src, out)

        assert exc_info.value.returncode == 1
        assert exc_info.value.stderr == "error: bad disc key"
        assert "bad disc key" in str(exc_info.value)


class TestResolveOperation:
    def test_ngc_rvz_nkit_iso_picks_dol_migrate(self):
        resolved = resolve_operation("ngc", "rvz", "Game.nkit.iso")
        assert resolved is not None
        op, ext = resolved
        assert op.argv == ("dol", "migrate")
        assert ext == ".nkit.iso"

    def test_ngc_rvz_plain_iso_picks_dol_compress(self):
        resolved = resolve_operation("ngc", "rvz", "Game.iso")
        assert resolved is not None
        op, ext = resolved
        assert op.argv == ("dol", "compress")
        assert ext == ".iso"

    def test_psp_iso_already_target_returns_none(self):
        assert resolve_operation("psp", "iso", "Game.iso") is None

    def test_psx_chd_has_no_extract_operation(self):
        assert resolve_operation("psx", "iso", "Game.chd") is None

    def test_wii_wbfs_output_name(self):
        resolved = resolve_operation("wii", "wbfs", "Game.rvz")
        assert resolved is not None
        op, ext = resolved
        assert op.output_name(Path("Game.rvz"), ext) == "Game.wbfs"

    def test_3ds_decrypted_output_name_keeps_source_ext_casing(self):
        resolved = resolve_operation("3ds", "decrypted", "Game.CIA")
        assert resolved is not None
        op, ext = resolved
        assert op.output_name(Path("Game.CIA"), ext) == "Game.CIA"

    def test_3ds_z3ds_output_name(self):
        resolved = resolve_operation("3ds", "z3ds", "Game.3ds")
        assert resolved is not None
        op, ext = resolved
        assert op.output_name(Path("Game.3ds"), ext) == "Game.zcci"

    def test_case_insensitive_ext_match(self):
        resolved = resolve_operation("psp", "chd", "Game.ISO")
        assert resolved is not None
        _, ext = resolved
        assert ext == ".iso"


class TestTargetsByPlatform:
    def test_psp_targets(self):
        assert TARGETS_BY_PLATFORM["psp"] == {"chd", "cso", "iso", "zso"}

    def test_wiiu_and_psvita_have_no_conversions(self):
        assert "wiiu" not in TARGETS_BY_PLATFORM
        assert "psvita" not in TARGETS_BY_PLATFORM
