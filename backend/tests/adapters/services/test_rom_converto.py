import asyncio
import os
import stat
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.services import rom_converto
from adapters.services.rom_converto import (
    LIBRARY_TARGETS_BY_PLATFORM,
    OPERATIONS,
    Operation,
    RomConvertoBinaryNotFoundError,
    RomConvertoOperationError,
    RomConvertoService,
    RomConvertoTimeoutError,
    RomConvertoUnsafeSourceError,
    canonical_format,
    cue_tracks,
    download_targets,
    file_format,
    resolve_operation,
)
from utils.filesystem import SERVED_FILE_MODE


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


class TestIsolation:
    async def test_every_run_skips_the_update_check_config_and_cache(self):
        calls: list[tuple[str, ...]] = []
        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", _capture_spawn(FakeProc(), calls)),
        ):
            await rom_converto._run(["capabilities"], timeout_seconds=1)

        binary, *flags, config, subcommand = calls[0]
        assert binary == "/usr/bin/rom-converto"
        assert flags == ["--no-update-check", "--no-cache", "--config"]
        assert subcommand == "capabilities"
        assert Path(config).name == "config.toml"

    async def test_runs_from_an_empty_dir_it_removes_after(self):
        seen: list[tuple[Path, list[str], int]] = []

        def record(cwd: Path, config: str) -> None:
            assert Path(config).parent == cwd
            seen.append((cwd, os.listdir(cwd), Path(config).stat().st_size))

        async def spawn(*args, cwd, **kwargs):
            record(Path(cwd), args[args.index("--config") + 1])
            return FakeProc()

        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", spawn),
        ):
            await rom_converto._run(["capabilities"], timeout_seconds=1)

        [(cwd, listing, config_size)] = seen
        assert listing == ["config.toml"]
        assert config_size == 0
        assert not await asyncio.to_thread(cwd.exists)

    async def test_a_run_cancelled_while_making_its_dir_still_removes_it(self):
        made: list[Path] = []
        release = threading.Event()

        def slow_sandbox() -> tuple[Path, Path]:
            release.wait(timeout=5)
            sandbox, config = make_sandbox()
            made.append(sandbox)
            return sandbox, config

        make_sandbox = rom_converto._make_sandbox
        with (
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch.object(rom_converto, "_make_sandbox", slow_sandbox),
        ):
            run = asyncio.create_task(
                rom_converto._run(["capabilities"], timeout_seconds=1)
            )
            await asyncio.sleep(0.05)
            run.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run
            release.set()
            for _ in range(100):
                if made and not await asyncio.to_thread(made[0].exists):
                    break
                await asyncio.sleep(0.01)

        assert made
        assert not await asyncio.to_thread(made[0].exists)


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

        src = tmp_path / "game.iso"
        out = tmp_path / "stage" / "game.chd"
        out.parent.mkdir()

        async def fake_run(argv: list[str], timeout_seconds: float):
            recorded.append(argv)
            out.write_bytes(b"converted")
            return 0, "", ""

        with patch.object(rom_converto, "_run", fake_run):
            await service.convert(self._op(), src, out)

        assert recorded == [["chd", "compress", str(src), str(out)]]

    async def test_an_owner_only_output_is_made_readable_for_nginx(
        self, service: RomConvertoService, tmp_path: Path
    ):
        out = tmp_path / "game.chd"

        async def fake_run(argv: list[str], timeout_seconds: float):
            out.write_bytes(b"converted")
            out.chmod(0o600)
            return 0, "", ""

        with patch.object(rom_converto, "_run", fake_run):
            await service.convert(self._op(), tmp_path / "src" / "game.iso", out)

        assert stat.S_IMODE(out.stat().st_mode) == SERVED_FILE_MODE

    @pytest.mark.parametrize(
        "written",
        [
            pytest.param(["game.chd", "game.bin"], id="split"),
            pytest.param([], id="nothing"),
        ],
    )
    async def test_output_other_than_out_raises_operation_error(
        self, service: RomConvertoService, tmp_path: Path, written: list[str]
    ):
        async def fake_run(argv: list[str], timeout_seconds: float):
            for name in written:
                (tmp_path / name).write_bytes(b"x")
            return 0, "", ""

        with (
            patch.object(rom_converto, "_run", fake_run),
            pytest.raises(RomConvertoOperationError, match="did not write exactly"),
        ):
            await service.convert(self._op(), tmp_path / "x.iso", tmp_path / "game.chd")

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

    async def test_a_cue_reaching_outside_its_folder_never_runs(
        self, service: RomConvertoService, tmp_path: Path
    ):
        cue = tmp_path / "game.cue"
        cue.write_text('FILE "/romm/config/config.yml" BINARY\n')

        async def fake_run(argv: list[str], timeout_seconds: float):
            raise AssertionError("rom-converto must not run")

        with (
            patch.object(rom_converto, "_run", fake_run),
            pytest.raises(RomConvertoUnsafeSourceError),
        ):
            await service.convert(self._op(), cue, tmp_path / "stage" / "game.chd")


class TestCueTracks:
    @pytest.mark.parametrize(
        "line",
        [
            pytest.param('FILE "game (Track 1).bin" BINARY', id="quoted"),
            pytest.param("FILE track.bin BINARY", id="bare"),
            pytest.param('  file "track.bin" BINARY', id="lowercase-indented"),
        ],
    )
    def test_reads_a_track_beside_the_cue(self, tmp_path: Path, line: str):
        cue = tmp_path / "game.cue"
        cue.write_text(f'REM FILE "../ignored.bin" BINARY\n{line}\n  TRACK 01 AUDIO\n')

        [track] = cue_tracks(cue)

        assert track.parent == tmp_path
        assert track.name in ("game (Track 1).bin", "track.bin")

    @pytest.mark.parametrize(
        "line",
        [
            pytest.param('FILE "../other.bin" BINARY', id="parent"),
            pytest.param('FILE "/etc/passwd" BINARY', id="absolute"),
            pytest.param("FILE ../other.bin BINARY", id="bare-parent"),
            pytest.param('FILE "sub/track.bin" BINARY', id="subfolder"),
            pytest.param('FILE ".." BINARY', id="dotdot"),
            pytest.param('FILE "" BINARY', id="empty"),
            pytest.param('FILE "track.bin BINARY', id="unbalanced-quote"),
            # The CLI reads from the first quote to the last, not the first pair.
            pytest.param('FILE "a.bin" "/../../etc/passwd" BINARY', id="two-quoted"),
        ],
    )
    def test_refuses_a_track_outside_the_cue_folder(self, tmp_path: Path, line: str):
        cue = tmp_path / "game.cue"
        cue.write_text(f"{line}\n")

        with pytest.raises(RomConvertoUnsafeSourceError):
            cue_tracks(cue)


class TestFileFormat:
    @pytest.mark.parametrize(
        ("file_name", "expected"),
        [
            pytest.param("Game.ISO", "iso", id="target-extension"),
            pytest.param("game.zcia", "z3ds", id="compressed-3ds"),
            pytest.param("game.3ds", "cci", id="alias"),
            pytest.param("game.nkit.iso", "nkit-iso", id="compound-extension"),
            pytest.param("game.pbp", "pbp", id="input-only-extension"),
            pytest.param("game.zip", "zip", id="unknown-extension"),
            pytest.param("README", "", id="no-extension"),
        ],
    )
    def test_names_the_format(self, file_name: str, expected: str):
        assert file_format(file_name) == expected

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            pytest.param("iso", "iso", id="plain"),
            pytest.param("3ds", "cci", id="alias"),
            pytest.param("zcia", "z3ds", id="compressed-alias"),
            pytest.param("nkit-iso", "nkit-iso", id="compound-not-iso"),
        ],
    )
    def test_canonical_format_reads_aliases(self, name: str, expected: str):
        assert canonical_format(name) == expected


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
            pytest.param("psx", "iso", "Game.cue", id="psx-cue-can-have-audio"),
            pytest.param("saturn", "iso", "Game.cue", id="saturn-cue-can-have-audio"),
            pytest.param("segacd", "iso", "Game.cue", id="segacd-cue-can-have-audio"),
            pytest.param("dc", "iso", "Game.cue", id="dc-cue-can-have-audio"),
        ],
    )
    def test_returns_none_when_nothing_applies(
        self, platform: str, target: str, file_name: str
    ):
        assert resolve_operation(platform, target, file_name) is None

    @pytest.mark.parametrize(
        "platform",
        [
            pytest.param("psp", id="psp"),
            pytest.param("ps2", id="ps2"),
        ],
    )
    def test_dvd_cue_still_converts_to_iso(self, platform: str):
        resolved = resolve_operation(platform, "iso", "Game.cue")

        assert resolved is not None
        op, ext = resolved
        assert op.argv == ("cue", "to-iso")
        assert op.output_name(Path("Game.cue"), ext) == "Game.iso"


class TestLibraryTargetsByPlatform:
    def test_psp_targets(self):
        assert LIBRARY_TARGETS_BY_PLATFORM["psp"] == {"chd", "cso", "iso", "zso"}

    def test_platforms_without_format_conversions(self):
        for slug in ("wiiu", "psvita", "nds", "ps3"):
            assert slug not in LIBRARY_TARGETS_BY_PLATFORM

    def test_a_lossy_conversion_is_no_library_target(self):
        assert "xbox" not in LIBRARY_TARGETS_BY_PLATFORM
        assert resolve_operation("xbox", "xiso", "game.iso") is not None
        assert resolve_operation("xbox", "xiso", "game.iso", lossless=True) is None


class TestDownloadTargets:
    @pytest.mark.parametrize(
        "platform_slug, file_name, expected",
        [
            ("psp", "game.chd", ["cso", "iso", "zso"]),
            ("psp", "game.iso", ["chd", "cso", "zso"]),
            ("xbox", "game.iso", ["xiso"]),
            ("psp", "game.txt", []),
            ("gb", "game.gb", []),
        ],
    )
    def test_lists_the_targets_a_file_converts_to(
        self, platform_slug: str, file_name: str, expected: list[str]
    ):
        assert download_targets(platform_slug, file_name) == expected

    def test_leaves_out_the_stored_format(self):
        assert "iso" not in download_targets("psp", "GAME.ISO")

    def test_no_decrypt_or_encrypt_targets(self):
        targets = {
            target
            for op in OPERATIONS
            for slug in op.platforms
            for ext in op.input_exts
            for target in download_targets(slug, f"game{ext}")
        }
        assert not targets & {"decrypted", "encrypted"}
