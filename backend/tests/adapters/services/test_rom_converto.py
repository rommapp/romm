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
    RomConvertoImages,
    RomConvertoInfo,
    RomConvertoOperationError,
    RomConvertoService,
    RomConvertoTimeoutError,
    resolve_operation,
)
from models.rom import ROM_FILE_INFO_MAX_LENGTH, RomFileContentType

_FAKE_PNG = b"\x89PNG\r\n\x1a\nfake"


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
                {
                    "kind": "nx",
                    "container_kind": "nsz",
                    "is_compressed": True,
                    "full": {
                        "title_kind": "application",
                        "required_system_version": 1073741824,
                        "title_version": 65536,
                        "application_title_id_hex": "0100000000010000",
                        "control": {
                            "icon": {"png_bytes": list(_FAKE_PNG)},
                            "display_version": "1.0.0",
                            "supported_languages": [
                                "AmericanEnglish",
                                "CanadianFrench",
                            ],
                            "titles": [
                                {
                                    "language": "Japanese",
                                    "name": "ゼルダの伝説",
                                    "publisher": "任天堂",
                                },
                                {
                                    "language": "AmericanEnglish",
                                    "name": "The Legend of Zelda",
                                    "publisher": "Nintendo",
                                },
                            ],
                        },
                    },
                },
                RomConvertoInfo(
                    title_id="0100000000010000",
                    title_version=65536,
                    title="The Legend of Zelda",
                    content_type="game",
                    display_version="1.0.0",
                    languages=("English", "French"),
                    publisher="Nintendo",
                    min_firmware_version="16.0.0",
                    is_compressed=True,
                    compression="zstd",
                    file_format="NSZ",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="nx-reads-the-full-header",
            ),
            pytest.param(
                {"kind": "nx", "container_kind": "nsp"},
                RomConvertoInfo(file_format="NSP"),
                id="nx-without-prod-keys",
            ),
            pytest.param(
                {"kind": "nx", "full": {"title_kind": "add_on_content"}},
                RomConvertoInfo(content_type="dlc"),
                id="nx-title-kind-maps-to-content-type",
            ),
            pytest.param(
                {
                    "kind": "ctr",
                    "title_id": "0004000000123456",
                    "product_code": "CTR-P-AZRE",
                    "content_kind": "game",
                    "compressed": True,
                    "format": "cia",
                    "icon": {"png_bytes": list(_FAKE_PNG)},
                    "small_icon": {"png_bytes": list(_FAKE_PNG + b"2")},
                    "smdh": {
                        "region_names": ["North America", "Japan"],
                        "titles": [
                            {
                                "language": "Japanese",
                                "short_description": "ロックマンゼロ",
                                "publisher": "カプコン",
                            },
                            {
                                "language": "English",
                                "short_description": "Mega Man Zero",
                                "long_description": "Mega Man Zero",
                                "publisher": "Capcom",
                            },
                        ],
                    },
                },
                RomConvertoInfo(
                    title_id="0004000000123456",
                    title="Mega Man Zero",
                    serial="CTR-P-AZRE",
                    content_type="game",
                    regions=("USA", "Japan"),
                    languages=("Japanese", "English"),
                    publisher="Capcom",
                    is_compressed=True,
                    compression="zstd",
                    file_format="CIA",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="ctr-reads-smdh-from-a-compressed-cia",
            ),
            pytest.param(
                {"kind": "ctr", "compressed": False, "format": "unknown"},
                RomConvertoInfo(is_compressed=False),
                id="ctr-format-unknown-has-no-file-format",
            ),
            pytest.param(
                {
                    "kind": "wup",
                    "title_id_hex": "0005000010143500",
                    "title_version": 16,
                    "content_kind": "game",
                    "image": {"png_bytes": list(_FAKE_PNG)},
                    "source_kind": "disc (GM0005000010143500)",
                    "meta": {
                        "product_code": "WUP-P-ARZE",
                        "company_name": "Nintendo",
                        "region_names": ["Europe", "Australia"],
                        "long_names": {
                            "entries": [
                                ["japanese", "ゼルダの伝説"],
                                ["english", "The Legend of Zelda"],
                            ]
                        },
                        "publishers": {
                            "entries": [["japanese", "任天堂"], ["english", "Nintendo"]]
                        },
                    },
                },
                RomConvertoInfo(
                    title_id="10143500",
                    title_version=16,
                    title="The Legend of Zelda",
                    serial="WUP-P-ARZE",
                    content_type="game",
                    regions=("Europe", "Australia"),
                    languages=("japanese", "english"),
                    publisher="Nintendo",
                    # .wud vs .wux cannot be told apart.
                    is_compressed=None,
                    file_format="DISC",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="wup-reads-the-xml-meta",
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
                {"kind": "wup", "source_kind": "wua (00050000101c9500)"},
                RomConvertoInfo(is_compressed=True, file_format="WUA"),
                id="wup-wua-archive-is-compressed",
            ),
            pytest.param(
                {"kind": "wup", "source_kind": "nus"},
                RomConvertoInfo(is_compressed=False, file_format="NUS"),
                id="wup-nus-content-is-not-compressed",
            ),
            pytest.param(
                {
                    "kind": "dol",
                    "game_id": "GZLE01",
                    "game_name": "The Legend of Zelda",
                    "disc_version": 2,
                    "region": "Usa",
                    "container": "RVZ",
                    "banner_image": {"png_bytes": list(_FAKE_PNG)},
                    "banner": {
                        "titles": [
                            {"language": "Default", "long_game_name": "ZELDA"},
                            {"language": "German", "long_game_name": ""},
                            {
                                "language": "English",
                                "long_game_name": "The Legend of Zelda",
                                "short_game_name": "Zelda",
                                "long_maker": "Nintendo",
                            },
                        ],
                    },
                },
                RomConvertoInfo(
                    title_id="475A4C45",
                    title="The Legend of Zelda",
                    serial="GZLE01",
                    content_type="game",
                    display_version="v2",
                    regions=("Usa",),
                    languages=("English",),
                    publisher="Nintendo",
                    is_compressed=True,
                    file_format="RVZ",
                    images=RomConvertoImages(banner=_FAKE_PNG),
                ),
                id="dol-reads-the-banner-and-rvz-container",
            ),
            pytest.param(
                {
                    "kind": "dol",
                    "game_id": "GZLE01",
                },
                RomConvertoInfo(
                    title_id="475A4C45", serial="GZLE01", content_type="game"
                ),
                id="dol-hex-encodes-game-id",
            ),
            pytest.param(
                {
                    "kind": "rvl",
                    "game_id": "SMNE01",
                    "game_name": "New Super Mario Bros. Wii",
                    "disc_version": 1,
                    "region": "PAL",
                    "container": "iso",
                    "tmd": {"title_version": 3},
                    "imet_names": {
                        "entries": [
                            ["Japanese", "ニュースーパーマリオブラザーズWii"],
                            ["English", "New Super Mario Bros. Wii"],
                        ]
                    },
                    "maker_name": "Nintendo",
                    "image": {"png_bytes": list(_FAKE_PNG)},
                },
                RomConvertoInfo(
                    title_id="534D4E45",
                    title_version=3,
                    title="New Super Mario Bros. Wii",
                    serial="SMNE01",
                    content_type="game",
                    display_version="v3",
                    regions=("Europe",),
                    languages=("Japanese", "English"),
                    publisher="Nintendo",
                    is_compressed=False,
                    file_format="DISC",
                    images=RomConvertoImages(banner=_FAKE_PNG),
                ),
                id="rvl-prefers-the-tmd-title-version",
            ),
            pytest.param(
                {"kind": "rvl", "game_id": "RZTE01"},
                RomConvertoInfo(
                    title_id="525A5445", serial="RZTE01", content_type="game"
                ),
                id="rvl-hex-encodes-game-id",
            ),
            pytest.param(
                {
                    "kind": "ntr",
                    "game_code": "ARZE",
                    "game_title": "Single Line",
                    "rom_version": 2,
                    "banner": {
                        "titles": {
                            "entries": [
                                ["Japanese", "ホームブルー\n作者不明"],
                                ["English", "Homebrew Game\nby TestDev\nfinal release"],
                            ]
                        },
                        "icon": {"png_bytes": list(_FAKE_PNG)},
                    },
                },
                RomConvertoInfo(
                    title_id="ARZE",
                    title="Homebrew Game",
                    serial="ARZE",
                    content_type="game",
                    display_version="v2",
                    publisher="final release",
                    is_compressed=False,
                    file_format="NDS",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="ntr-splits-the-banner-into-title-and-publisher",
            ),
            pytest.param(
                {
                    "kind": "xbox",
                    "xbe": {
                        "title_id_code": "TT-027",
                        "title_name": "Stubbs the Zombie",
                        "version": 1,
                        "region_names": ["NTSC-U"],
                        "icon": {"png_bytes": list(_FAKE_PNG)},
                    },
                    "xex": {"icon": {"png_bytes": list(_FAKE_PNG + b"2")}},
                },
                RomConvertoInfo(
                    title_id="TT-027",
                    title="Stubbs the Zombie",
                    serial="TT-027",
                    content_type="game",
                    display_version="1",
                    regions=("USA",),
                    is_compressed=False,
                    file_format="DISC",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="xbox-reads-the-xbe-header",
            ),
            pytest.param(
                {
                    "kind": "xbox",
                    "xex": {
                        "title_id_hex": "4D5307E6",
                        "title_name": "Halo 3",
                        "version": "1.0.0.0",
                        "region_names": ["NTSC-U", "PAL"],
                        "icon": {"png_bytes": list(_FAKE_PNG)},
                    },
                },
                RomConvertoInfo(
                    title_id="4D5307E6",
                    title="Halo 3",
                    content_type="game",
                    display_version="1.0.0.0",
                    regions=("USA", "Europe"),
                    is_compressed=False,
                    file_format="DISC",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="xbox-360-iso-reads-the-xex-header",
            ),
            pytest.param(
                {
                    "kind": "xbox",
                    "xbe": {"title_id_code": "TT-027", "title_id_hex": "5454001B"},
                },
                RomConvertoInfo(
                    title_id="TT-027",
                    serial="TT-027",
                    content_type="game",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="xbox-nested-xbe-code",
            ),
            pytest.param(
                {
                    "kind": "xenon",
                    "compressed_size": 725614592,
                    "logical_size": 786432000,
                    "xex": {
                        "title_id_hex": "4D5307DC",
                        "title_name": "Halo 3",
                        "version": "2.0.4552.0",
                        "region_names": ["RegionFree"],
                        "icon": {"png_bytes": list(_FAKE_PNG)},
                    },
                },
                RomConvertoInfo(
                    title_id="4D5307DC",
                    title="Halo 3",
                    content_type="game",
                    display_version="2.0.4552.0",
                    regions=("World",),
                    is_compressed=True,
                    file_format="ZAR",
                    uncompressed_size_bytes=786432000,
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="xenon-reads-the-xex-header-and-zar-sizes",
            ),
            pytest.param(
                {"kind": "xenon", "xex": {"title_id_hex": "4D5307DC"}},
                RomConvertoInfo(
                    title_id="4D5307DC", content_type="game", file_format="ZAR"
                ),
                id="xenon-nested-xex-hex",
            ),
            pytest.param(
                {"kind": "psx", "title_id": "SCUS-94163", "version": "1.1"},
                RomConvertoInfo(
                    title_id="SCUS-94163",
                    serial="SCUS-94163",
                    content_type="game",
                    display_version="1.1",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="psx-reads-the-disc-header",
            ),
            pytest.param(
                {
                    "kind": "psp",
                    "title": "Patapon",
                    "title_id": "UCUS-98696",
                    "content_kind": "game",
                    "version": "1.0",
                    "firmware": "5.00",
                },
                RomConvertoInfo(
                    title_id="UCUS-98696",
                    title="Patapon",
                    serial="UCUS-98696",
                    content_type="game",
                    display_version="1.0",
                    min_firmware_version="5.00",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="psp-reads-the-disc-header",
            ),
            pytest.param(
                {
                    "kind": "pbp",
                    "title": "Patapon",
                    "disc_id": "UCUS-98696",
                    "content_kind": "update",
                    "disc_version": "1.00",
                    "psp_system_ver": "5.55",
                    "icon": {"png_bytes": list(_FAKE_PNG)},
                },
                RomConvertoInfo(
                    title="Patapon",
                    serial="UCUS-98696",
                    content_type="update",
                    display_version="1.00",
                    min_firmware_version="5.55",
                    file_format="EBOOT.PBP",
                    images=RomConvertoImages(icon=_FAKE_PNG),
                ),
                id="pbp-reads-the-eboot-header",
            ),
            pytest.param(
                {
                    "kind": "ps3",
                    "title": "Gran Turismo 5",
                    "title_id": "BCUS98114",
                    "content_kind": "dlc",
                    "version": "01.02",
                    "region": "USA",
                    "firmware": "3.50",
                },
                RomConvertoInfo(
                    title_id="BCUS98114",
                    title="Gran Turismo 5",
                    serial="BCUS98114",
                    content_type="dlc",
                    display_version="01.02",
                    regions=("USA",),
                    min_firmware_version="3.50",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="ps3-reads-the-disc-metadata",
            ),
            pytest.param(
                {"kind": "ps3", "title_id": "BLUS31426", "version": "01.00"},
                RomConvertoInfo(
                    title_id="BLUS31426",
                    serial="BLUS31426",
                    content_type="game",
                    display_version="01.00",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="ps3-string-version-is-display-only",
            ),
            pytest.param(
                {
                    "kind": "vpk",
                    "title": "Vita Homebrew",
                    "content_id": "JM0000-ABCDEF12_00-0000000000000000",
                    "content_kind": "game",
                    "app_ver": "1.02",
                    "icon": {"png_bytes": list(_FAKE_PNG)},
                    "background": {"png_bytes": list(_FAKE_PNG)},
                },
                RomConvertoInfo(
                    title="Vita Homebrew",
                    serial="JM0000-ABCDEF12_00-0000000000000000",
                    content_type="game",
                    display_version="1.02",
                    file_format="VPK",
                    images=RomConvertoImages(icon=_FAKE_PNG, background=_FAKE_PNG),
                ),
                id="vpk-reads-the-package-header",
            ),
            pytest.param(
                {
                    "kind": "pkg",
                    "title": "Journey",
                    "content_id": "UP9000-CUSA00264_00-JOURNEY00000000",
                    "content_kind": "game",
                },
                RomConvertoInfo(
                    title="Journey",
                    serial="UP9000-CUSA00264_00-JOURNEY00000000",
                    content_type="game",
                    file_format="PKG",
                ),
                id="pkg-reads-the-package-header",
            ),
            pytest.param(
                {
                    "kind": "chd",
                    "compressors": ["zstd"],
                    "logical_bytes": 1234567890,
                    "content": {
                        "kind": "psp",
                        "title": "Daxter",
                        "title_id": "UCUS-98718",
                        "content_kind": "game",
                        "version": "1.00",
                        "icon": {"png_bytes": list(_FAKE_PNG)},
                        "background": {"png_bytes": list(_FAKE_PNG)},
                    },
                },
                RomConvertoInfo(
                    title_id="UCUS-98718",
                    title="Daxter",
                    serial="UCUS-98718",
                    content_type="game",
                    display_version="1.00",
                    is_compressed=True,
                    compression="zstd",
                    file_format="CHD",
                    uncompressed_size_bytes=1234567890,
                    images=RomConvertoImages(icon=_FAKE_PNG, background=_FAKE_PNG),
                ),
                id="chd-layers-the-container-over-the-inner-psp-disc",
            ),
            pytest.param(
                {"kind": "chd", "compressors": [], "logical_bytes": 786432000},
                RomConvertoInfo(
                    is_compressed=False,
                    file_format="CHD",
                    uncompressed_size_bytes=786432000,
                ),
                id="chd-without-an-inner-disc-has-only-container-fields",
            ),
            pytest.param(
                {
                    "kind": "chd",
                    "compressors": [1, "zstd"],
                    "logical_bytes": 2**64 - 1,
                },
                RomConvertoInfo(
                    is_compressed=True,
                    compression="zstd",
                    file_format="CHD",
                ),
                id="chd-corrupt-header-values-are-dropped",
            ),
            pytest.param(
                {
                    "kind": "cso",
                    "format": "zso",
                    "uncompressed_size": 456789012,
                    "content": {
                        "kind": "psx",
                        "title_id": "SCUS-94163",
                        "version": "1.1",
                    },
                },
                RomConvertoInfo(
                    title_id="SCUS-94163",
                    serial="SCUS-94163",
                    content_type="game",
                    display_version="1.1",
                    is_compressed=True,
                    file_format="ZSO",
                    uncompressed_size_bytes=456789012,
                ),
                id="cso-layers-the-container-over-the-inner-psx-disc",
            ),
            pytest.param(
                {"kind": "nds", "game_code": "AXXE"},
                RomConvertoInfo(title_id="AXXE", title_version=None),
                id="nds-falls-back-to-game-code",
            ),
            pytest.param(
                {"kind": "psp", "title": "Gran\n\nTurismo\t5"},
                RomConvertoInfo(
                    title="Gran Turismo 5",
                    content_type="game",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="text-cleaner-collapses-newline-and-tab-runs",
            ),
            pytest.param(
                {"kind": "psp", "title": "Home\x00brew\x00\x00"},
                RomConvertoInfo(
                    title="Homebrew",
                    content_type="game",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="text-cleaner-drops-nul-bytes",
            ),
            pytest.param(
                {"kind": "psp", "title": "A" * 300},
                RomConvertoInfo(
                    title="A" * ROM_FILE_INFO_MAX_LENGTH,
                    content_type="game",
                    is_compressed=False,
                    file_format="DISC",
                ),
                id="text-cleaner-clips-at-the-column-limit",
            ),
            pytest.param(
                {
                    "kind": "ctr",
                    "smdh": {
                        "region_names": [
                            "NorthAmerica",
                            "PAL",
                            "Rest of World",
                            "RegionFree",
                            "NTSC-J Japan",
                            "NTSC-J China",
                            "NTSC-J",
                            "PAL Australia/New Zealand",
                            "Manufacturing",
                            "Other",
                            "Unknown 12",
                            "Korea",
                        ],
                    },
                },
                RomConvertoInfo(
                    # The scan handler drops the duplicates once names are canonical.
                    regions=(
                        "USA",
                        "Europe",
                        "Europe",
                        "World",
                        "Japan",
                        "China",
                        "Asia",
                        "Australia",
                        "Korea",
                    )
                ),
                id="region-names-map-aliases-and-drop-junk",
            ),
            pytest.param(
                {
                    "kind": "nx",
                    "full": {
                        "control": {
                            "supported_languages": [
                                "AmericanEnglish",
                                "BritishEnglish",
                                "CanadianFrench",
                                "LatinAmericanSpanish",
                                "BrazilianPortuguese",
                                "SimplifiedChinese",
                                "TraditionalChinese",
                                "TaiwaneseChinese",
                                "Japanese",
                                "german",
                                "Default",
                            ],
                        },
                    },
                },
                RomConvertoInfo(
                    languages=(
                        "English",
                        "English",
                        "French",
                        "Spanish",
                        "Portuguese",
                        "Chinese",
                        "Chinese",
                        "Chinese",
                        "Japanese",
                        "german",
                    )
                ),
                id="language-variants-fold-and-default-drops",
            ),
            pytest.param(
                {
                    "kind": "nx",
                    "is_compressed": "yes",
                    "full": {
                        "title_kind": ["patch"],
                        "control": {"titles": {"language": "English"}},
                    },
                },
                RomConvertoInfo(),
                id="malformed-shapes-yield-nothing",
            ),
        ],
    )
    def test_parse_info(self, payload: dict[str, Any], expected: RomConvertoInfo):
        assert rom_converto._parse_info(payload) == expected

    def test_every_content_type_is_a_stored_enum_value(self):
        # The scan builds a `RomFileContentType` from each one; a value the
        # enum lacks would abort the whole platform scan.
        stored = {member.value for member in RomFileContentType}
        assert rom_converto._CONTENT_TYPES == stored
        assert set(rom_converto._SWITCH_CONTENT_TYPES.values()) <= stored


class TestImage:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param(
                {"png_bytes": list(_FAKE_PNG)},
                _FAKE_PNG,
                id="valid-png-list",
            ),
            pytest.param({}, None, id="missing-png-bytes"),
            pytest.param(
                {"png_bytes": tuple(_FAKE_PNG)},
                None,
                id="png-bytes-not-a-list",
            ),
            pytest.param(
                {"png_bytes": [256]},
                None,
                id="byte-out-of-range",
            ),
            pytest.param(
                {"png_bytes": list(b"not png")},
                None,
                id="not-png",
            ),
        ],
    )
    def test_image_returns_only_valid_png_bytes(
        self, value: Any, expected: bytes | None
    ) -> None:
        assert rom_converto._image(value) == expected


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
