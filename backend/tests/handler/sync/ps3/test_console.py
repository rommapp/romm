from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from tests.handler.sync.ps3.fakes import FakeConsole, build_ps3_iso, build_sfo

from handler.sync.ps3 import console as console_module
from handler.sync.ps3.console import (
    PS3SyncConfig,
    discover_title_ids,
    normalize_title_id,
    probe_ps3,
    title_id_of,
)
from handler.sync.ps3.ftp import AsyncPS3Ftp


class TestTitleIds:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("BLES01138SAVAUTOSAVE_SLOT1_SAV", "BLES01138"),
            ("BCES00006", "BCES00006"),
            ("NP0APOLLO-OPTIONS", None),
            ("bles01138", None),
        ],
    )
    def test_title_id_of(self, name: str, expected: str | None):
        assert title_id_of(name) == expected

    def test_normalize_drops_the_dash(self):
        assert normalize_title_id("bles-01138") == "BLES01138"


class TestPS3SyncConfig:
    def test_defaults(self):
        config = PS3SyncConfig.of(None)
        assert config.ftp_port == 21
        assert config.savedata_path == "/dev_hdd0/home/00000001/savedata"

    @pytest.mark.parametrize(
        "sync_config",
        [{"ps3_user": "1"}, {"ftp_port": 0}, {"poll_interval_minutes": 0}],
    )
    def test_rejects_invalid_settings(self, sync_config: dict[str, object]):
        with pytest.raises(ValidationError):
            PS3SyncConfig.of(sync_config)


class TestDiscoverTitleIds:
    async def test_finds_installed_iso_and_folder_games(self):
        console = FakeConsole()
        console.add_dir("/dev_hdd0/game/BLES00801")
        console.add_dir("/dev_hdd0/game/PKGLAUNCH")
        console.add_file(
            "/dev_hdd0/PS3ISO/FALLOUT 3.ISO",
            build_ps3_iso(build_sfo(TITLE_ID="BLES00333", TITLE="FALLOUT 3")),
        )
        console.add_file("/dev_hdd0/PS3ISO/FALLOUT 3.png", b"cover")
        console.add_file("/dev_usb000/PS3ISO/Jak [BCUS98281].iso", b"never read")
        console.add_file(
            "/dev_hdd0/GAMES/MotorStorm/PS3_GAME/PARAM.SFO",
            build_sfo(TITLE_ID="BCES00006"),
        )

        title_ids = await discover_title_ids(console.ftp, "device-1")

        assert title_ids == {"BLES00801", "BLES00333", "BCUS98281", "BCES00006"}
        assert "/dev_usb000/PS3ISO/Jak [BCUS98281].iso" not in console.reads

    async def test_reads_each_image_once(self):
        console = FakeConsole()
        console.add_file(
            "/dev_hdd0/PS3ISO/Game.iso",
            build_ps3_iso(build_sfo(TITLE_ID="BLES00333")),
        )
        await discover_title_ids(console.ftp, "device-1")
        console.reads.clear()

        assert await discover_title_ids(console.ftp, "device-1") == {"BLES00333"}
        assert console.reads == []

    async def test_skips_an_image_it_cannot_read(self):
        console = FakeConsole()
        console.add_file("/dev_hdd0/PS3ISO/Broken.iso", b"not an image")

        assert await discover_title_ids(console.ftp, "device-1") == set()


class TestProbePS3:
    async def test_unreachable(self):
        with patch.object(console_module, "probe", AsyncMock(return_value=None)):
            result = await probe_ps3("192.168.1.2", 21)
        assert not result.reachable
        assert result.users == []

    async def test_lists_user_profiles(self):
        console = FakeConsole()
        console.add_dir("/dev_hdd0/home/00000001")
        console.add_dir("/dev_hdd0/home/00000002")
        console.add_dir("/dev_hdd0/home/notauser")
        with (
            patch.object(console_module, "probe", AsyncMock(return_value="webMAN")),
            patch.object(
                AsyncPS3Ftp,
                "connect",
                AsyncMock(return_value=console.ftp),
            ),
        ):
            result = await probe_ps3("192.168.1.2", 21)
        assert result.reachable and result.is_ftp
        assert result.users == ["00000001", "00000002"]

    async def test_not_ftp(self):
        with (
            patch.object(console_module, "probe", AsyncMock(return_value="")),
            patch.object(
                AsyncPS3Ftp,
                "connect",
                AsyncMock(side_effect=EOFError()),
            ),
        ):
            result = await probe_ps3("192.168.1.2", 21)
        assert result.reachable and not result.is_ftp
