import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services import rom_converto
from adapters.services.rom_converto import (
    RomConvertoOperationError,
    RomConvertoTimeoutError,
    RomConvertoUnsupportedError,
    RomConvertoService,
)

DOL_INFO_JSON = json.dumps(
    {
        "kind": "dol",
        "physical_bytes": 1459970048,
        "container": "ISO",
        "game_id": "GALE01",
        "game_name": "Super Smash Bros. Melee",
        "region": "USA",
    }
)

CTR_INFO_JSON = json.dumps(
    {
        "kind": "ctr",
        "title_id": "00040000000EDF00",
        "product_code": "CTR-P-AQKE",
        "ncch_encrypted": True,
        "smdh": {
            "titles": [
                {"language": "english", "short_description": "Pokemon Y", "publisher": ""},
                {"language": "japanese", "short_description": "ポケモンY", "publisher": ""},
            ]
        },
    }
)


class FakeProc:
    def __init__(self, returncode=0, stdout=b"", stderr=b"", delay=0.0):
        self._result = (returncode, stdout, stderr)
        self._delay = delay
        self.killed = False
        self.returncode = returncode

    async def communicate(self):
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._result[1], self._result[2]

    def kill(self):
        self.killed = True

    async def wait(self):
        return self._result[0]


@pytest.fixture
def service():
    return RomConvertoService()


class TestIsEnabled:
    async def test_disabled_when_config_disabled(self, service):
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", False),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
        ):
            assert await service.is_enabled() is False

    async def test_disabled_when_binary_missing(self, service):
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value=None),
        ):
            assert await service.is_enabled() is False

    async def test_enabled_when_configured_and_present(self, service):
        proc = FakeProc(
            stdout=b'{"schema": "rom-converto.capabilities.v1", "version": "0.21.0"}'
        )
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", return_value=proc),
        ):
            assert await service.is_enabled() is True

    async def test_disabled_when_capability_probe_fails(self, service):
        proc = FakeProc(returncode=1)
        spawn = AsyncMock(return_value=proc)
        with (
            patch.object(rom_converto, "ROM_CONVERTO_ENABLED", True),
            patch("shutil.which", return_value="/usr/bin/rom-converto"),
            patch("asyncio.create_subprocess_exec", spawn),
        ):
            assert await service.is_enabled() is False
            # The failed probe verdict is cached: no second spawn.
            assert await service.is_enabled() is False
        assert spawn.await_count == 1


class TestReadInfo:
    async def test_parses_dol_json(self, service):
        proc = FakeProc(stdout=DOL_INFO_JSON.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/melee.iso"))

        assert info is not None
        assert info["kind"] == "dol"
        assert info["title_id"] == "GALE01"
        assert info["serial"] == "GALE01"
        assert info["names"] == {"": "Super Smash Bros. Melee"}
        assert info["region"] == "USA"
        assert info["version"] is None
        assert info["encrypted"] is None

    async def test_parses_ctr_smdh_names(self, service):
        proc = FakeProc(stdout=CTR_INFO_JSON.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/game.cia"))

        assert info is not None
        assert info["kind"] == "ctr"
        assert info["title_id"] == "00040000000EDF00"
        assert info["serial"] == "CTR-P-AQKE"
        assert info["names"] == {"english": "Pokemon Y", "japanese": "ポケモンY"}
        assert info["encrypted"] is True

    async def test_parses_nds_game_code(self, service):
        payload = json.dumps(
            {
                "kind": "nds",
                "game_title": "Mario Kart DS",
                "game_code": "AMCE",
                "maker_code": "01",
                "rom_version": 0,
            }
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/mkds.nds"))

        assert info is not None
        assert info["kind"] == "nds"
        assert info["title_id"] is None
        assert info["serial"] == "AMCE"
        assert info["names"] == {"": "Mario Kart DS"}

    async def test_parses_retro_saturn_nested_details(self, service):
        payload = json.dumps(
            {
                "kind": "retro",
                "file_size": 123,
                "details": {
                    "system": "sega_saturn",
                    "product_number": "T-8107H",
                    "title": "Panzer Dragoon",
                    "version": "V1.000",
                },
            }
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/panzer.cue"))

        assert info is not None
        assert info["kind"] == "retro"
        assert info["serial"] == "T-8107H"
        assert info["names"] == {"": "Panzer Dragoon"}
        assert info["version"] == "V1.000"

    async def test_parses_pbp_disc_id(self, service):
        payload = json.dumps(
            {
                "kind": "pbp",
                "version": 3,
                "title": "Wipeout Pure",
                "disc_id": "UCES-00001",
            }
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/EBOOT.PBP"))

        assert info is not None
        assert info["kind"] == "pbp"
        assert info["serial"] == "UCES-00001"
        assert info["names"] == {"": "Wipeout Pure"}
        assert info["version"] is None  # integer container version is skipped

    async def test_parses_xbox_nested_xbe(self, service):
        payload = json.dumps(
            {
                "kind": "xbox",
                "partition_kind": "ftx",
                "xbe": {
                    "title_id": 1297438724,
                    "title_id_hex": "4D530004",
                    "title_id_code": "MS-004",
                    "title_name": "Halo",
                },
            }
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/halo.iso"))

        assert info is not None
        assert info["kind"] == "xbox"
        assert info["title_id"] == "4D530004"
        assert info["serial"] == "MS-004"
        assert info["names"] == {"": "Halo"}

    async def test_parses_vpk_title_id(self, service):
        payload = json.dumps(
            {"kind": "vpk", "title": "Gravity Rush", "title_id": "PCSA00001"}
        )
        proc = FakeProc(stdout=payload.encode())
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            info = await service.read_info(Path("/roms/gr.vpk"))

        assert info is not None
        assert info["title_id"] == "PCSA00001"
        assert info["names"] == {"": "Gravity Rush"}

    async def test_unrecognized_file_returns_none(self, service):
        proc = FakeProc(
            returncode=1,
            stderr=b"error: could not detect console for path: /roms/junk.bin",
        )
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            assert await service.read_info(Path("/roms/junk.bin")) is None

    async def test_non_json_output_returns_none(self, service):
        proc = FakeProc(returncode=0, stdout=b"not json at all")
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            assert await service.read_info(Path("/roms/game.iso")) is None

    async def test_binary_missing_raises(self, service):
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(rom_converto.RomConvertoBinaryNotFoundError),
        ):
            await service.read_info(Path("/roms/game.iso"))


class TestRunTimeout:
    async def test_timeout_kills_process(self):
        proc = FakeProc(delay=5.0)
        with (
            patch("asyncio.create_subprocess_exec", return_value=proc),
            patch("shutil.which", return_value="rc"),
        ):
            with patch("shutil.which", return_value="/usr/bin/rom-converto"):
                with pytest.raises(RomConvertoTimeoutError):
                    await rom_converto._run(["info", "--json", "x"], timeout=0.01)
        assert proc.killed is True


class TestConvertDispatch:
    @pytest.fixture
    def runner(self):
        """Record the argv handed to _run and return a canned success."""
        recorded: list[list[str]] = []

        async def fake_run(argv, timeout):
            recorded.append(argv)
            return 0, "", ""

        return recorded, fake_run

    async def test_rvz_wii_iso_sniffs_rvl(self, service, tmp_path, runner):
        recorded, fake_run = runner
        src = tmp_path / "wii-game.iso"
        src.write_bytes(b"\x00" * 0x18 + b"\x5d\x1c\x9e\xa3")
        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            out = await service.convert("rvz", src, tmp_path)

        assert recorded == [["rvl", "compress", str(src), str(tmp_path / "wii-game.rvz")]]
        assert out == tmp_path / "wii-game.rvz"

    async def test_rvz_gc_iso_sniffs_dol(self, service, tmp_path, runner):
        recorded, fake_run = runner
        src = tmp_path / "gc-game.iso"
        src.write_bytes(b"\x00" * 0x1C + b"\xc2\x33\x9f\x3d")
        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            await service.convert("rvz", src, tmp_path)

        assert recorded == [["dol", "compress", str(src), str(tmp_path / "gc-game.rvz")]]

    async def test_rvz_wbfs_uses_rvl(self, service, tmp_path, runner):
        recorded, fake_run = runner
        src = tmp_path / "game.wbfs"
        src.write_bytes(b"x")
        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            await service.convert("rvz", src, tmp_path)

        assert recorded == [["rvl", "compress", str(src), str(tmp_path / "game.rvz")]]

    async def test_iso_from_cso_uses_cso_decompress(self, service, tmp_path, runner):
        recorded, fake_run = runner
        src = tmp_path / "game.cso"
        src.write_bytes(b"x")
        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            out = await service.convert("iso", src, tmp_path)

        assert recorded == [["cso", "decompress", str(src), str(tmp_path / "game.iso")]]
        assert out == tmp_path / "game.iso"

    async def test_cia_decrypted_uses_ctr_decrypt(self, service, tmp_path, runner):
        recorded, fake_run = runner
        src = tmp_path / "game.cia"
        src.write_bytes(b"x")
        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            out = await service.convert("cia-decrypted", src, tmp_path)

        assert recorded == [["ctr", "decrypt", str(src), str(tmp_path / "game.cia")]]
        assert out == tmp_path / "game.cia"

    async def test_unknown_target_raises(self, service, tmp_path):
        with pytest.raises(RomConvertoUnsupportedError):
            await service.convert("zip", tmp_path / "game.iso", tmp_path)

    async def test_target_rejects_wrong_input(self, service, tmp_path):
        with pytest.raises(RomConvertoUnsupportedError):
            await service.convert("rvz", tmp_path / "game.nds", tmp_path)

    async def test_failure_raises_operation_error(self, service, tmp_path):
        src = tmp_path / "game.iso"
        src.write_bytes(b"x")

        async def fake_run(argv, timeout):
            return 1, "", b"error: bad disc key"

        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
            pytest.raises(RomConvertoOperationError) as exc_info,
        ):
            await service.convert("iso-decrypted", src, tmp_path)

        assert exc_info.value.returncode == 1
        assert "bad disc key" in str(exc_info.value)


class TestConvertConcurrency:
    async def test_semaphore_bounds_concurrency(self, service, tmp_path):
        active = 0
        max_active = 0

        async def fake_run(argv, timeout):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return 0, "", ""

        sources = []
        for i in range(6):
            src = tmp_path / f"game-{i}.cso"
            src.write_bytes(b"x")
            sources.append(src)

        with (
            patch.object(rom_converto, "_run", fake_run),
            patch("shutil.which", return_value="rc"),
        ):
            await asyncio.gather(
                *(service.convert("iso", src, tmp_path) for src in sources)
            )

        assert max_active == rom_converto.ROM_CONVERTO_MAX_CONCURRENCY
