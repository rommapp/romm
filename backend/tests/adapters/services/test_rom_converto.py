import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
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

    async def test_cancellation_kills_process(self) -> None:
        proc = FakeProc(delay=5.0)
        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            run = asyncio.create_task(
                rom_converto._run(["info", "--json", "x"], timeout_seconds=10)
            )
            await asyncio.sleep(0.01)
            run.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run
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

    @pytest.mark.parametrize(
        "error",
        [OSError(8, "Exec format error"), RomConvertoTimeoutError("timed out")],
    )
    async def test_probe_that_cannot_run_is_cached_false(
        self, service: RomConvertoService, error: Exception
    ):
        spawn_count = 0

        async def spawn(*args, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            raise error

        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", spawn),
        ):
            assert await service.is_enabled() is False
            assert await service.is_enabled() is False
        assert spawn_count == 1

    async def test_probe_ok_logs_version(self, service: RomConvertoService, mocker):
        log_info = mocker.patch("adapters.services.rom_converto.log.info")
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


def _capture_spawn(proc: FakeProc, calls: list[tuple[str, ...]]):
    async def spawn(*args, **kwargs):
        calls.append(args)
        return proc

    return spawn


class TestReadInfos:
    async def test_batches_paths_and_keys_recognized_files(
        self, service: RomConvertoService
    ):
        records = [
            {
                "path": "/roms/game.nsp",
                "ok": True,
                "info": {
                    "kind": "nx",
                    "full": {
                        "application_title_id_hex": "0100ABCD12345000",
                        "title_version": 65536,
                    },
                },
            },
            {"path": "/roms/junk.bin", "ok": False, "error": "could not detect"},
        ]
        calls: list[tuple[str, ...]] = []
        listed: list[str] = []
        proc = FakeProc(stdout=json.dumps(records).encode())

        async def spawn(*args, **kwargs):
            calls.append(args)
            paths_file = anyio.Path(args[args.index("--paths-file") + 1])
            listed.extend((await paths_file.read_text()).split())
            return proc

        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", spawn),
        ):
            infos = await service.read_infos(
                [Path("/roms/game.nsp"), Path("/roms/junk.bin")]
            )

        assert len(calls) == 1
        assert listed == ["/roms/game.nsp", "/roms/junk.bin"]
        assert infos == {
            Path("/roms/game.nsp"): RomConvertoInfo(
                title_id="0100ABCD12345000", title_version=65536
            )
        }

    async def test_paths_file_is_removed(self, service: RomConvertoService):
        calls: list[tuple[str, ...]] = []
        with (
            patch("shutil.which", return_value="rc"),
            patch(
                "asyncio.create_subprocess_exec",
                _capture_spawn(FakeProc(stdout=b"[]"), calls),
            ),
        ):
            await service.read_infos([Path("/roms/game.iso")])

        paths_file = calls[0][calls[0].index("--paths-file") + 1]
        assert not await anyio.Path(paths_file).exists()

    async def test_nonzero_returns_empty(self, service: RomConvertoService):
        proc = FakeProc(returncode=2, stderr=b"error: bad arguments")
        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.read_infos([Path("/roms/game.iso")]) == {}

    async def test_non_json_output_returns_empty(self, service: RomConvertoService):
        proc = FakeProc(stdout=b"not json at all")
        with (
            patch("shutil.which", return_value="rc"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.read_infos([Path("/roms/game.iso")]) == {}

    async def test_no_listable_paths_skips_the_subprocess(
        self, service: RomConvertoService
    ):
        with patch("asyncio.create_subprocess_exec") as spawn:
            assert await service.read_infos([Path("/roms/bad\nname.iso")]) == {}
        spawn.assert_not_called()


class TestReadInfosFailures:
    @pytest.mark.parametrize(
        "error", [RomConvertoTimeoutError("slow"), OSError(8, "Exec format error")]
    )
    async def test_run_failure_returns_empty(
        self, service: RomConvertoService, error: Exception
    ):
        with patch.object(rom_converto, "_run", side_effect=error):
            assert await service.read_infos([Path("/roms/game.iso")]) == {}


class TestUpdateCheck:
    async def test_every_run_disables_the_update_check(self):
        calls: list[tuple[str, ...]] = []
        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", _capture_spawn(FakeProc(), calls)),
        ):
            await rom_converto._run(["capabilities"], timeout_seconds=1)

        assert calls[0][:3] == (
            "/usr/bin/rom-converto",
            "--no-update-check",
            "capabilities",
        )


class TestCanInspect:
    async def test_manifest_extensions_gate_inspection(
        self, service: RomConvertoService
    ):
        proc = FakeProc(
            stdout=b'{"version": "0.21.0", "info_extensions": ["ISO", "nsp"]}'
        )
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.is_enabled() is True

        assert service.can_inspect(Path("/roms/Game.iso")) is True
        assert service.can_inspect(Path("/roms/game.NSP")) is True
        assert service.can_inspect(Path("/roms/readme.nfo")) is False

    def test_unknown_manifest_inspects_everything(self, service: RomConvertoService):
        assert service.can_inspect(Path("/roms/anything.xyz")) is True


class TestParseInfo:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param(
                {"kind": "nx", "container_kind": "nsp"},
                RomConvertoInfo(title_id=None, title_version=None),
                id="nx-without-prod-keys",
            ),
            pytest.param(
                {"kind": "chd", "content": {"kind": "psx", "title_id": "SLUS-00594"}},
                RomConvertoInfo(title_id="SLUS-00594", title_version=None),
                id="chd-flattens-inner-disc",
            ),
            pytest.param(
                {"kind": "dol", "game_id": "GZLE01"},
                RomConvertoInfo(title_id="475A4C45", title_version=None),
                id="dol-hex-encodes-game-id",
            ),
            pytest.param(
                {"kind": "rvl", "game_id": "RZTE01"},
                RomConvertoInfo(title_id="525A5445", title_version=None),
                id="rvl-hex-encodes-game-id",
            ),
            pytest.param(
                {
                    "kind": "wup",
                    "title_id_hex": "0005000010143500",
                    "title_version": 16,
                },
                RomConvertoInfo(title_id="10143500", title_version=16),
                id="wup-last-8-of-title-id",
            ),
            pytest.param(
                {
                    "kind": "xbox",
                    "xbe": {"title_id_code": "TT-027", "title_id_hex": "5454001B"},
                },
                RomConvertoInfo(title_id="TT-027", title_version=None),
                id="xbox-nested-xbe-code",
            ),
            pytest.param(
                {"kind": "xenon", "xex": {"title_id_hex": "4D5307DC"}},
                RomConvertoInfo(title_id="4D5307DC", title_version=None),
                id="xenon-nested-xex-hex",
            ),
            pytest.param(
                {
                    "kind": "ctr",
                    "title_id": "0004000000123456",
                    "product_code": "CTR-P-AXXE",
                },
                RomConvertoInfo(title_id="0004000000123456", title_version=None),
                id="ctr-ignores-product-code",
            ),
            pytest.param(
                {"kind": "nds", "game_code": "AXXE"},
                RomConvertoInfo(title_id="AXXE", title_version=None),
                id="nds-falls-back-to-game-code",
            ),
            pytest.param(
                {"kind": "ps3", "title_id": "BLUS31426", "version": "01.00"},
                RomConvertoInfo(title_id="BLUS31426", title_version=None),
                id="ps3-string-version-is-none",
            ),
        ],
    )
    def test_parse_info(self, payload: dict[str, Any], expected: RomConvertoInfo):
        assert rom_converto._parse_info(payload) == expected


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

    async def test_nonzero_raises_operation_error_with_diagnostic(
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

        assert "bad disc key" in str(exc_info.value)


class TestResolveOperation:
    @pytest.mark.parametrize(
        ("platform", "target", "file_name", "argv", "input_ext", "output_name"),
        [
            (
                "ngc",
                "rvz",
                "Game.nkit.iso",
                ("dol", "migrate"),
                ".nkit.iso",
                "Game.rvz",
            ),
            ("ngc", "rvz", "Game.iso", ("dol", "compress"), ".iso", "Game.rvz"),
            ("wii", "wbfs", "Game.rvz", ("rvl", "decompress"), ".rvz", "Game.wbfs"),
            ("3ds", "z3ds", "Game.3ds", ("ctr", "compress"), ".3ds", "Game.zcci"),
            ("3ds", "cci", "My Game.CIA", ("ctr", "convert"), ".cia", "My Game.cci"),
            ("psp", "chd", "Game.ISO", ("chd", "compress"), ".iso", "Game.chd"),
        ],
    )
    def test_resolves_operation_and_output_name(
        self,
        platform: str,
        target: str,
        file_name: str,
        argv: tuple[str, ...],
        input_ext: str,
        output_name: str,
    ):
        resolved = resolve_operation(platform, target, file_name)

        assert resolved is not None
        op, ext = resolved
        assert (op.argv, ext) == (argv, input_ext)
        assert op.output_name(Path(file_name), ext) == output_name

    @pytest.mark.parametrize(
        ("platform", "target", "file_name"),
        [
            pytest.param("psp", "iso", "Game.iso", id="already-in-target-format"),
            pytest.param("psx", "iso", "Game.chd", id="cd-chd-has-no-extract"),
        ],
    )
    def test_returns_none_when_nothing_applies(
        self, platform: str, target: str, file_name: str
    ):
        assert resolve_operation(platform, target, file_name) is None


class TestTargetsByPlatform:
    def test_psp_targets(self):
        assert TARGETS_BY_PLATFORM["psp"] == {"chd", "cso", "iso", "zso"}

    def test_platforms_without_format_conversions(self):
        for slug in ("wiiu", "psvita", "nds", "ps3"):
            assert slug not in TARGETS_BY_PLATFORM

    def test_no_decrypt_or_encrypt_targets(self):
        targets = set().union(*TARGETS_BY_PLATFORM.values())
        assert not targets & {"decrypted", "encrypted"}
