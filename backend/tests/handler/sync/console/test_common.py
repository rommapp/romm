from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from tests.handler.sync.console.fakes import FakeConsole

from handler.sync.console import common as common_module
from handler.sync.console.common import (
    ConsoleSyncConfig,
    ConsoleUserProfile,
    normalize_title_id,
    probe_console_ftp,
    title_id_of,
)
from handler.sync.console.ftp import AsyncConsoleFtp
from handler.sync.console.profiles import CONSOLE_PROFILES, ConsoleKind
from handler.sync.console.ps3 import PS3
from handler.sync.console.ps4 import PS4


class TestTitleIds:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("BLES01138SAVAUTOSAVE_SLOT1_SAV", "BLES01138"),
            ("BCES00006", "BCES00006"),
            ("CUSA18886", "CUSA18886"),
            ("NP0APOLLO-OPTIONS", None),
            ("bles01138", None),
        ],
    )
    def test_title_id_of(self, name: str, expected: str | None):
        assert title_id_of(name) == expected

    def test_normalize_drops_the_dash(self):
        assert normalize_title_id("bles-01138") == "BLES01138"


class TestConsoleSyncConfig:
    def test_defaults_to_the_console_port(self):
        assert ConsoleSyncConfig.of(PS3, {"user_id": "00000001"}).ftp_port == 21
        assert ConsoleSyncConfig.of(PS4, {"user_id": "1cabafc9"}).ftp_port == 2121

    @pytest.mark.parametrize(
        ("profile", "sync_config"),
        [
            (PS3, {}),
            (PS3, {"user_id": "1"}),
            (PS3, {"user_id": "1cabafc9"}),
            (PS4, {"user_id": "00000001X"}),
            (PS3, {"user_id": "00000001", "ftp_port": 0}),
            (PS4, {"user_id": "1cabafc9", "poll_interval_minutes": 0}),
        ],
    )
    def test_rejects_invalid_settings(self, profile, sync_config: dict[str, object]):
        with pytest.raises(ValidationError):
            ConsoleSyncConfig.of(profile, sync_config)


def test_every_kind_has_a_profile():
    assert set(CONSOLE_PROFILES) == set(ConsoleKind.__args__)


class TestProbeConsole:
    async def test_unreachable(self):
        with patch.object(common_module, "probe", AsyncMock(return_value=None)):
            result = await probe_console_ftp(PS3, "192.168.1.2", 21)
        assert not result.reachable
        assert result.users == []

    @pytest.mark.parametrize(
        ("profile", "home", "name_file", "user", "not_users"),
        [
            (PS3, "/dev_hdd0/home", "localusername", "00000001", ["notauser"]),
            (PS4, "/user/home", "username.dat", "1cabafc9", ["00000001X"]),
        ],
    )
    async def test_lists_user_profiles(self, profile, home, name_file, user, not_users):
        console = FakeConsole()
        console.add_file(f"{home}/{user}/{name_file}", b"Fil2k\x00\x00\x00")
        for name in not_users:
            console.add_dir(f"{home}/{name}")
        with (
            patch.object(common_module, "probe", AsyncMock(return_value="FTP")),
            patch.object(AsyncConsoleFtp, "connect", AsyncMock(return_value=console)),
        ):
            result = await probe_console_ftp(profile, "192.168.1.2", 21)
        assert result.reachable and result.is_ftp
        assert result.users == [ConsoleUserProfile(id=user, name="Fil2k")]

    async def test_a_profile_without_a_name(self):
        console = FakeConsole()
        console.add_dir("/dev_hdd0/home/00000002")
        with (
            patch.object(common_module, "probe", AsyncMock(return_value="webMAN")),
            patch.object(AsyncConsoleFtp, "connect", AsyncMock(return_value=console)),
        ):
            result = await probe_console_ftp(PS3, "192.168.1.2", 21)
        assert result.users == [ConsoleUserProfile(id="00000002", name=None)]

    async def test_not_ftp(self):
        with (
            patch.object(common_module, "probe", AsyncMock(return_value="")),
            patch.object(AsyncConsoleFtp, "connect", AsyncMock(side_effect=EOFError())),
        ):
            result = await probe_console_ftp(PS3, "192.168.1.2", 21)
        assert result.reachable and not result.is_ftp
