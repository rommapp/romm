import asyncio
import hashlib
import itertools
import os
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from tests import factories
from tests.factories import make_rom, make_save, make_screenshot
from tests.handler.snapshots.pushes import SRAM, md5, part, push, save_entry

from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_snapshot_handler,
    db_state_handler,
)
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler, fs_retroarch_sync_handler
from handler.middleware.upload_size_middleware import UploadSizeLimitMiddleware
from handler.redis_handler import async_cache
from handler.snapshots.manifest import Manifest
from handler.snapshots.write import SAVE_PART, write_snapshot
from handler.sync.retroarch import psp, sync_handler
from handler.sync.retroarch.device import CLIENT_DEVICE_IDENTIFIER
from handler.sync.retroarch.emulator_names import (
    retroarch_aliases,
    to_retroarch_dir_name,
    to_romm_emulator,
)
from models.assets import Save, SaveFormat, Screenshot, State
from models.channel import DEFAULT_CHANNEL_LABEL
from models.device import SyncMode
from models.platform import Platform
from models.rom import Rom, RomFile
from models.snapshot import Snapshot, SnapshotKind, SnapshotState
from models.user import User

ADMIN_AUTH = ("test_admin", "test_admin_password")
EDITOR_AUTH = ("test_editor", "test_editor_password")
EMPTY_MD5 = "d41d8cd98f00b204e9800998ecf8427e"


def _mock_asset_md5():
    async def md5s(assets: Sequence[Save | State | Screenshot]) -> list[str | None]:
        return [EMPTY_MD5] * len(assets)

    return mock.patch(
        "handler.sync.retroarch.sync_handler.asset_md5s",
        new_callable=mock.AsyncMock,
        side_effect=md5s,
    )


def _retroarch_upload_cap(client: TestClient, max_size: int):
    """Lower the upload size limit guarding `/api/sync/retroarch` for one test."""
    app = client.app
    layer = app.middleware_stack or app.build_middleware_stack()  # type: ignore[attr-defined]
    app.middleware_stack = layer  # type: ignore[attr-defined]
    while layer is not None:
        if isinstance(layer, UploadSizeLimitMiddleware) and any(
            pattern.match("/api/sync/retroarch/") for pattern in layer.paths
        ):
            return mock.patch.object(layer, "max_size", max_size)
        layer = getattr(layer, "app", None)
    raise AssertionError("No upload size limit guards /api/sync/retroarch")


@pytest.fixture(autouse=True)
def _isolated_sync_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep assets and sync files per test, since user ids repeat across test databases."""
    for handler, name in (
        (fs_asset_handler, "assets"),
        (fs_retroarch_sync_handler, "retroarch_sync"),
    ):
        base = (tmp_path / name).resolve()
        base.mkdir()
        monkeypatch.setattr(handler, "base_path", base)


@pytest.fixture
def saves_path(admin_user: User, rom: Rom):
    return fs_asset_handler.build_saves_file_path(
        user=admin_user,
        platform_fs_slug="test_platform_slug",
        rom_id=rom.id,
        emulator="snes9x",
    )


@pytest.fixture
def synced_save(admin_user: User, rom: Rom, saves_path: str):
    """A save where `saves/Snes9x/test_rom.srm` resolves, unlike the shared fixture's legacy layout."""
    return make_save(
        rom,
        admin_user,
        "test_rom.srm",
        file_path=saves_path,
        file_size_bytes=4,
        emulator="snes9x",
        slot=None,
    )


@pytest.fixture
def states_path(admin_user: User, rom: Rom):
    return fs_asset_handler.build_states_file_path(
        user=admin_user,
        platform_fs_slug="test_platform_slug",
        rom_id=rom.id,
        emulator="snes9x",
    )


@pytest.fixture
def make_state(admin_user: User, rom: Rom, states_path: str):
    def make(file_name: str) -> State:
        return factories.make_state(
            rom,
            admin_user,
            file_name,
            file_path=states_path,
            file_size_bytes=4,
            emulator="snes9x",
        )

    return make


@pytest.fixture
def synced_state(make_state):
    """A state with RetroArch's own `<rom>.state` name, unlike the shared fixture."""
    return make_state("test_rom.state")


@pytest.fixture
def synced_state_screenshot(admin_user: User, rom: Rom, synced_state: State):
    """The `<state file name>.png` screenshot RetroArch syncs next to a state."""
    return make_screenshot(
        rom,
        admin_user,
        f"{synced_state.file_name}.png",
        file_path=sync_handler.state_screenshot_dir(admin_user, rom, "snes9x"),
        file_size_bytes=8,
    )


@pytest.fixture
def web_state(make_state):
    """A state with the web player's label-plus-timestamp name."""
    return make_state("test_rom [2026-07-24 12-04-52-733].state")


class TestRetroArchSyncEmulatorNames:
    @pytest.mark.parametrize(
        ("retroarch_dir_name", "romm_emulator"),
        [
            ("Snes9x", "snes9x"),
            ("Genesis Plus GX", "genesis_plus_gx"),
            ("PCSX-ReARMed", "pcsx_rearmed"),
            # The web player stores the Beetle cores under their mednafen ids.
            ("Beetle PSX", "mednafen_psx"),
            ("Beetle PSX HW", "mednafen_psx_hw"),
            ("Beetle PCE", "mednafen_pce"),
            ("RetroArduous", "RetroArduous"),
            ("Beetle VB", "Beetle VB"),
        ],
    )
    def test_to_romm_emulator(self, retroarch_dir_name, romm_emulator):
        assert to_romm_emulator(retroarch_dir_name) == romm_emulator

    @pytest.mark.parametrize(
        "retroarch_dir_name",
        [
            "Snes9x",
            "Beetle PSX",
            "PPSSPP",
            "RetroArduous",
            "Beetle VB",
            "bsnes-hd beta",
        ],
    )
    def test_dir_name_round_trips(self, retroarch_dir_name):
        assert (
            to_retroarch_dir_name(to_romm_emulator(retroarch_dir_name))
            == retroarch_dir_name
        )

    @pytest.mark.parametrize(
        ("romm_emulator", "retroarch_dir_name"),
        [
            ("snes9x", "Snes9x"),
            ("genesis_plus_gx", "Genesis Plus GX"),
            ("pcsx_rearmed", "PCSX-ReARMed"),
            # A core outside the table round-trips unchanged rather than
            # guessing at a casing/spacing that hasn't been verified.
            ("retroarduous", "retroarduous"),
            ("test_emulator", "test_emulator"),
        ],
    )
    def test_to_retroarch_dir_name(self, romm_emulator, retroarch_dir_name):
        assert to_retroarch_dir_name(romm_emulator) == retroarch_dir_name

    @pytest.mark.parametrize(
        "emulator", ["mednafen_psx_hw", "beetle_psx_hw", "Beetle PSX HW"]
    )
    def test_aliases_cover_every_emulator_sharing_a_folder(self, emulator):
        assert retroarch_aliases(emulator) == (
            "Beetle PSX HW",
            "beetle_psx_hw",
            "mednafen_psx_hw",
        )

    def test_a_core_outside_the_table_is_its_only_alias(self):
        assert retroarch_aliases("retroarduous") == ("retroarduous",)


class TestRetroArchSyncPathParsing:
    @pytest.mark.parametrize(
        ("path", "kind", "emulator", "file_name"),
        [
            ("saves/test_rom.srm", "saves", None, "test_rom.srm"),
            ("saves/Snes9x/test_rom.srm", "saves", "snes9x", "test_rom.srm"),
            ("states/Snes9x/test_rom.state", "states", "snes9x", "test_rom.state"),
            ("/states/test_rom.state.auto", "states", None, "test_rom.state.auto"),
            # A core outside the translation table round-trips unchanged.
            (
                "saves/RetroArduous/test_rom.srm",
                "saves",
                "RetroArduous",
                "test_rom.srm",
            ),
        ],
    )
    def test_parses_supported_paths(self, path, kind, emulator, file_name):
        parsed = sync_handler.parse_retroarch_sync_path(path)

        assert parsed is not None
        assert parsed.kind == kind
        assert parsed.emulator == emulator
        assert parsed.file_name == file_name

    @pytest.mark.parametrize(
        "path",
        [
            "manifest.server",
            "config/retroarch.cfg",
            "thumbnails/Nintendo/img.png",
            "system/bios.bin",
            "saves",
            "saves/Snes9x/nested/test_rom.srm",
            "saves/../../etc/passwd",
            "saves/Snes9x/test\x00rom.srm",
            f"saves/{'x' * 51}/test_rom.srm",
        ],
    )
    def test_rejects_unsupported_paths(self, path):
        assert sync_handler.parse_retroarch_sync_path(path) is None

    @pytest.mark.parametrize(
        ("kind", "file_name", "game_name"),
        [
            ("saves", "Super Mario World.srm", "Super Mario World"),
            ("saves", "Game v1.1.sav", "Game v1.1"),
            ("states", "Super Mario World.state", "Super Mario World"),
            ("states", "Super Mario World.state3", "Super Mario World"),
            # The auto suffix makes this a two-segment extension.
            ("states", "Super Mario World.state.auto", "Super Mario World"),
        ],
    )
    def test_derives_game_name(self, kind, file_name, game_name):
        assert sync_handler.game_name_from_file_name(kind, file_name) == game_name


class TestRetroArchSyncAuth:
    def test_options_without_credentials_challenges(self, client):
        response = client.options("/api/sync/retroarch/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["www-authenticate"].startswith("Basic")
        assert response.content == b""

    def test_options_with_basic_auth_advertises_dav(self, client, admin_user: User):
        response = client.options("/api/sync/retroarch/", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["dav"] == "1, 2"
        assert "MKCOL" in response.headers["allow"]
        assert "PROPFIND" in response.headers["allow"]

    def test_get_without_credentials_challenges(self, client):
        response = client.get("/api/sync/retroarch/manifest.server")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_without_credentials_challenges(self, client):
        response = client.put("/api/sync/retroarch/saves/test_rom.srm", content=b"data")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_kiosk_guest_is_challenged_outside_the_game_library(self, client):
        with mock.patch("handler.auth.hybrid_auth.KIOSK_MODE", True):
            options = client.options("/api/sync/retroarch/")
            manifest = client.get("/api/sync/retroarch/manifest.server")
            saves = client.request("PROPFIND", "/api/sync/retroarch/saves/")
            blob = client.get("/api/sync/retroarch/config/retroarch.cfg")

        for response in (options, manifest, saves, blob):
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_kiosk_guest_can_browse_the_game_library(self, client, rom: Rom):
        with mock.patch("handler.auth.hybrid_auth.KIOSK_MODE", True):
            root = client.request("PROPFIND", "/api/sync/retroarch/")
            platform = client.request(
                "PROPFIND", f"/api/sync/retroarch/roms/{rom.platform.fs_slug}/"
            )

        assert root.status_code == status.HTTP_207_MULTI_STATUS
        assert "<D:href>/api/sync/retroarch/roms/</D:href>" in root.text
        assert "/api/sync/retroarch/saves/" not in root.text
        assert platform.status_code == status.HTTP_207_MULTI_STATUS
        assert rom.fs_name in platform.text


class TestRetroArchSyncStateSlotResolution:
    def test_resolves_canonical_name_to_the_web_created_row(
        self, admin_user: User, rom: Rom, web_state: State
    ):
        """The canonical slot name resolves to a web-player state despite its timestamped name."""
        resolved = sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is not None
        assert resolved.id == web_state.id

    def test_resolves_to_the_newer_of_two_competing_states(
        self, admin_user: User, rom: Rom, make_state
    ):
        older = make_state("test_rom.state")
        newer = make_state("test_rom [2026-07-24 12-04-52-733].state")
        assert newer.id > older.id

        resolved = sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is not None
        assert resolved.id == newer.id

    def test_does_not_cross_slots(self, admin_user: User, rom: Rom, make_state):
        """A slot-1 state never resolves for a slot-0 request."""
        make_state("test_rom.state1")

        resolved = sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is None


class TestRetroArchSyncManifest:
    @_mock_asset_md5()
    def test_lists_saves_and_states(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        synced_save: Save,
        synced_state: State,
    ):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/Snes9x/test_rom.srm",
                "hash": EMPTY_MD5,
            },
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": EMPTY_MD5,
            },
        ]

    @_mock_asset_md5()
    def test_remaps_web_player_state_to_canonical_slot(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, web_state: State
    ):
        """RetroArch only loads numbered slots, so a web-player state is listed under slot 0's name."""
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": EMPTY_MD5,
            }
        ]

    @_mock_asset_md5()
    def test_newest_state_in_a_slot_wins_regardless_of_origin(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        make_state,
    ):
        """The newest state in a slot wins, whichever client created it."""
        older = make_state("test_rom.state")
        newer = make_state("test_rom [2026-07-24 12-04-52-733].state")
        assert newer.id > older.id

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": EMPTY_MD5,
            }
        ]

    @_mock_asset_md5()
    def test_lists_an_autosave_srm_under_retroarchs_name(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        make_save(
            rom,
            admin_user,
            "web name [2026-01-01_00-00-00].srm",
            emulator="test_emulator",
            slot="autosave",
        )

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {"path": "saves/test_emulator/test_rom.srm", "hash": EMPTY_MD5}
        ]

    def test_leaves_out_slotted_saves_retroarch_does_not_sync(
        self, client, admin_user: User, save: Save
    ):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_empty_library_returns_empty_manifest(self, client, admin_user: User):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_flags_a_state_whose_file_is_gone(
        self, client, admin_user: User, synced_state: State
    ):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        state = db_state_handler.get_state(user_id=admin_user.id, id=synced_state.id)
        assert state is not None
        assert state.missing_from_fs

    @_mock_asset_md5()
    def test_round_trips_emulator_casing_through_the_manifest(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        """The manifest uses RetroArch's directory casing (`Snes9x`), not RomM's."""
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/Snes9x/test_rom.srm",
                "hash": EMPTY_MD5,
            }
        ]

    @_mock_asset_md5()
    def test_omits_assets_of_a_shadowed_same_named_rom(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        synced_save: Save,
        other_platform: Platform,
    ):
        shadowed_rom = make_rom(other_platform, "test_rom")
        make_save(
            shadowed_rom,
            admin_user,
            "test_rom.srm",
            file_path=fs_asset_handler.build_saves_file_path(
                user=admin_user,
                platform_fs_slug=other_platform.fs_slug,
                rom_id=shadowed_rom.id,
                emulator="snes9x",
            ),
            file_size_bytes=4,
            emulator="snes9x",
            slot=None,
        )

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/Snes9x/test_rom.srm",
                "hash": EMPTY_MD5,
            }
        ]


class TestRetroArchSyncStateScreenshots:
    def test_game_name_strips_png_before_state_suffix(self):
        """`test_rom.state.png` resolves to game `test_rom`, not `test_rom.state`."""
        assert (
            sync_handler.game_name_from_file_name("states", "test_rom.state.png")
            == "test_rom"
        )
        assert (
            sync_handler.game_name_from_file_name("states", "test_rom.state3.png")
            == "test_rom"
        )
        assert (
            sync_handler.game_name_from_file_name("states", "test_rom.state.auto.png")
            == "test_rom"
        )

    @_mock_asset_md5()
    def test_manifest_includes_the_state_screenshot(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        synced_state: State,
        synced_state_screenshot: Screenshot,
    ):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": EMPTY_MD5,
            },
            {
                "path": "states/Snes9x/test_rom.state.png",
                "hash": EMPTY_MD5,
            },
        ]

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_screenshot", new_callable=mock.AsyncMock)
    def test_creates_screenshot_for_a_new_state(
        self,
        mock_scan_screenshot: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        synced_state: State,
    ):
        mock_scan_screenshot.return_value = Screenshot(
            file_name="test_rom.state.png",
            file_path=synced_state.file_path,
            file_size_bytes=8,
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state.png",
            content=b"pngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        screenshots = db_screenshot_handler.get_screenshot(
            rom_id=rom.id, user_id=admin_user.id, file_name="test_rom.state.png"
        )
        assert screenshots is not None

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    def test_rejects_a_screenshot_the_owning_state_name_pushes_over_255_bytes(
        self, mock_write_file: mock.AsyncMock, client, make_state
    ):
        # The client's name fits, but the screenshot takes the slot's longer state name.
        make_state(f"test_rom [{'x' * 236}].state")

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state.png",
            content=b"pngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        mock_write_file.assert_not_awaited()

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_screenshot", new_callable=mock.AsyncMock)
    def test_overwrites_existing_screenshot_for_a_state(
        self,
        mock_scan_screenshot: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        synced_state: State,
        synced_state_screenshot: Screenshot,
    ):
        mock_scan_screenshot.return_value = Screenshot(
            file_name="test_rom.state.png",
            file_path=synced_state.file_path,
            file_size_bytes=16,
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state.png",
            content=b"newpngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_same_named_states_under_two_cores_keep_separate_screenshots(
        self, client, admin_user: User, rom: Rom, synced_state: State
    ):
        factories.make_state(
            rom,
            admin_user,
            synced_state.file_name,
            file_path=fs_asset_handler.build_states_file_path(
                user=admin_user,
                platform_fs_slug=rom.platform.fs_slug,
                rom_id=rom.id,
                emulator="bsnes",
            ),
            file_size_bytes=4,
            emulator="bsnes",
        )

        for core, content in (("Snes9x", b"snes9x-png"), ("bsnes", b"bsnes-png")):
            response = client.put(
                f"/api/sync/retroarch/states/{core}/test_rom.state.png",
                content=content,
                auth=ADMIN_AUTH,
            )
            assert response.status_code == status.HTTP_201_CREATED

        for core, content in (("Snes9x", b"snes9x-png"), ("bsnes", b"bsnes-png")):
            response = client.get(
                f"/api/sync/retroarch/states/{core}/test_rom.state.png",
                auth=ADMIN_AUTH,
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.content == content

    def test_slot_without_a_screenshot_does_not_claim_another_slots(
        self,
        client,
        admin_user: User,
        rom: Rom,
        make_state,
        synced_state_screenshot: Screenshot,
    ):
        make_state("test_rom.state1")

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/states/Snes9x/test_rom.state1.png",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert db_screenshot_handler.get_screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name=synced_state_screenshot.file_name,
        )


class TestRetroArchSyncUpload:
    def test_rejects_a_name_sanitizing_would_change(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom%3F.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    def test_rejects_a_name_over_255_bytes(
        self, mock_write_file: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        # The ROM's own 254-byte name fits; its save's longer extension does not.
        stem = "a" * 252
        db_rom_handler.update_rom(
            rom.id, {"fs_name": f"{stem}.z", "fs_name_no_ext": stem}
        )

        response = client.put(
            f"/api/sync/retroarch/saves/Snes9x/{stem}.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        mock_write_file.assert_not_awaited()

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_state", new_callable=mock.AsyncMock)
    def test_creates_state_from_auto_savestate_name(
        self,
        mock_scan_state: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
    ):
        states_path = fs_asset_handler.build_states_file_path(
            user=admin_user,
            platform_fs_slug="test_platform_slug",
            rom_id=rom.id,
            emulator="snes9x",
        )
        mock_scan_state.return_value = State(
            file_name="test_rom.state.auto",
            file_path=states_path,
            file_size_bytes=8,
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state.auto",
            content=b"statedat",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED

        states = db_state_handler.get_states(user_id=admin_user.id, rom_ids=[rom.id])
        assert len(states) == 1
        assert states[0].file_name == "test_rom.state.auto"

    def test_rejects_upload_with_no_matching_rom(self, client, admin_user: User):
        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/not_in_library.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        # A conflict rather than a fake success: the client keeps its copy and
        # retries, instead of recording a file the server never stored.
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.content == b""

    def test_rejects_unsupported_sync_root(self, client, admin_user: User, rom: Rom):
        response = client.put(
            "/api/sync/retroarch/deleted/saves/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_accepts_and_drops_client_manifest(self, client, admin_user: User):
        response = client.put(
            "/api/sync/retroarch/manifest.server", content=b"[]", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    def test_rejects_a_chunked_body_over_the_upload_cap(
        self,
        mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
    ):
        # A generator body goes out chunked, with no Content-Length to reject on.
        with _retroarch_upload_cap(client, 4):
            response = client.put(
                "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
                content=iter([b"dat", b"a!"]),
                auth=ADMIN_AUTH,
            )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        mock_write_file.assert_not_awaited()
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id]) == []

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_state", new_callable=mock.AsyncMock)
    def test_state_filed_elsewhere_moves_with_the_upload(
        self,
        mock_scan_state: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        states_path: str,
    ):
        legacy_state = factories.make_state(
            rom,
            admin_user,
            "test_rom.state",
            file_path="legacy/states/snes9x",
            file_size_bytes=4,
            emulator="snes9x",
        )
        mock_scan_state.return_value = State(
            file_name="test_rom.state", file_path=states_path, file_size_bytes=8
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state",
            content=b"statedat",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        state = db_state_handler.get_state(user_id=admin_user.id, id=legacy_state.id)
        assert state is not None
        assert state.file_path == states_path
        mock_remove_file.assert_awaited_once_with(file_path=legacy_state.full_path)


@pytest.fixture
def version_names():
    """Distinct version names, since real tags only change once a second."""
    counter = itertools.count()

    def tag(file_name: str, at: datetime | None = None) -> str:
        name, ext = os.path.splitext(file_name)
        return f"{name} [2026-01-01_00-00-{next(counter):02d}]{ext}"

    with mock.patch("handler.asset_store.apply_datetime_tag", side_effect=tag):
        yield


@pytest.mark.usefixtures("version_names")
class TestRetroArchSyncSaveSlots:
    SAVE_URL = "/api/sync/retroarch/saves/Snes9x/test_rom.srm"
    RTC_URL = "/api/sync/retroarch/saves/Snes9x/test_rom.rtc"

    def _put(self, client: TestClient, content: bytes, url: str = SAVE_URL) -> int:
        return client.put(url, content=content, auth=ADMIN_AUTH).status_code

    def _get(self, client: TestClient, url: str = SAVE_URL) -> bytes:
        response = client.get(url, auth=ADMIN_AUTH)
        assert response.status_code == status.HTTP_200_OK
        return response.content

    def _versions(self, admin_user: User, rom: Rom) -> Sequence[Save]:
        return db_save_handler.get_saves(
            user_id=admin_user.id, rom_ids=[rom.id], order_by="updated_at"
        )

    def _other_client_save(
        self, admin_user: User, rom: Rom, saves_path: str, content: bytes, **fields
    ) -> Save:
        file_name = "test_rom [2025-12-31_23-59-59].srm"
        disk_path = fs_asset_handler.validate_path(f"{saves_path}/{file_name}")
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_bytes(content)
        return make_save(
            rom,
            admin_user,
            file_name,
            file_path=saves_path,
            file_size_bytes=len(content),
            content_hash=hashlib.md5(content).hexdigest(),
            **({"emulator": "snes9x", "slot": "autosave"} | fields),
        )

    def test_upload_files_a_version_in_autosave(
        self, client, admin_user: User, rom: Rom
    ):
        assert self._put(client, b"data") == status.HTTP_201_CREATED

        [save] = self._versions(admin_user, rom)
        assert re.fullmatch(r"test_rom \[2026-01-01_00-00-\d{2}\]\.srm", save.file_name)
        assert (save.slot, save.emulator) == ("autosave", "snes9x")
        assert self._get(client) == b"data"

    def test_upload_becomes_the_default_channels_next_snapshot(
        self, client, admin_user: User, rom: Rom
    ):
        rom_file = db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name="test_rom.sfc",
                file_path=rom.fs_path,
                file_size_bytes=1024,
                sha1_hash="d" * 40,
            )
        )
        first = asyncio.run(
            write_snapshot(
                push(
                    admin_user,
                    rom,
                    rom_file,
                    Manifest(save=save_entry(fmt=SaveFormat.NATIVE), emulator="snes9x"),
                    expected=None,
                    parts={SAVE_PART: part(SRAM)},
                )
            )
        )

        assert self._put(client, b"retroarch progress") == status.HTTP_201_CREATED

        assert first.snapshot.channel_id is not None
        channel = db_snapshot_handler.get_channel(first.snapshot.channel_id)
        assert channel is not None and channel.label == DEFAULT_CHANNEL_LABEL
        assert channel.current_snapshot_id is not None
        current = db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
        assert current is not None and current.parent_snapshot_id == first.snapshot.id
        held = db_snapshot_handler.get_stored_content(current).save
        assert held is not None
        assert held.content_hash == md5(b"retroarch progress")

    def test_upload_queries_and_writes_off_the_event_loop(
        self, client, rom: Rom, monkeypatch: pytest.MonkeyPatch
    ):
        on_loop: dict[str, bool] = {}

        def spy(owner: object, name: str) -> None:
            original = getattr(owner, name)

            def recording(*args: Any, **kwargs: Any) -> Any:
                try:
                    asyncio.get_running_loop()
                    on_loop[name] = True
                except RuntimeError:
                    on_loop[name] = False
                return original(*args, **kwargs)

            monkeypatch.setattr(owner, name, recording)

        spy(sync_handler, "resolve_rom")
        spy(db_save_handler, "get_lineage_head")
        spy(db_save_handler, "get_save_by_path")
        spy(db_save_handler, "add_save")

        assert self._put(client, b"data") == status.HTTP_201_CREATED
        assert on_loop == {
            "resolve_rom": False,
            "get_lineage_head": False,
            "get_save_by_path": False,
            "add_save": False,
        }

    @_mock_asset_md5()
    def test_manifest_lists_the_newest_version_under_retroarchs_name(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._put(client, b"old")
        self._put(client, b"new")

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.json() == [
            {"path": "saves/Snes9x/test_rom.srm", "hash": EMPTY_MD5}
        ]
        assert self._get(client) == b"new"

    @_mock_asset_md5()
    def test_manifest_keeps_the_clients_spelling_of_the_game(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        url = "/api/sync/retroarch/saves/Snes9x/TEST_ROM.srm"
        assert self._put(client, b"data", url) == status.HTTP_201_CREATED

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.json() == [
            {"path": "saves/Snes9x/TEST_ROM.srm", "hash": EMPTY_MD5}
        ]

    def test_each_changed_upload_adds_a_version(
        self, client, admin_user: User, rom: Rom
    ):
        self._put(client, b"old")
        assert self._put(client, b"new") == status.HTTP_201_CREATED

        assert len(self._versions(admin_user, rom)) == 2
        assert self._get(client) == b"new"

    def test_an_unchanged_upload_writes_nothing(
        self, client, admin_user: User, rom: Rom
    ):
        self._put(client, b"data")

        with mock.patch.object(fs_asset_handler, "write_file") as write_file:
            assert self._put(client, b"data") == status.HTTP_204_NO_CONTENT

        write_file.assert_not_called()
        assert len(self._versions(admin_user, rom)) == 1

    def test_serves_and_continues_another_clients_autosave(
        self, client, admin_user: User, rom: Rom, saves_path: str
    ):
        self._other_client_save(admin_user, rom, saves_path, b"native")

        assert self._get(client) == b"native"
        self._put(client, b"retroarch")

        assert [save.slot for save in self._versions(admin_user, rom)] == [
            "autosave",
            "autosave",
        ]
        assert self._get(client) == b"retroarch"

    def test_leaves_named_slots_alone(
        self, client, admin_user: User, rom: Rom, saves_path: str
    ):
        checkpoint = self._other_client_save(
            admin_user, rom, saves_path, b"checkpoint", slot="speedrun"
        )

        assert client.get(self.SAVE_URL, auth=ADMIN_AUTH).status_code == (
            status.HTTP_404_NOT_FOUND
        )
        self._put(client, b"retroarch")
        client.request("DELETE", self.SAVE_URL, auth=ADMIN_AUTH)

        assert [save.id for save in self._versions(admin_user, rom)] == [checkpoint.id]

    def test_ignores_another_cores_versions(
        self, client, admin_user: User, rom: Rom, platform: Platform
    ):
        mgba_path = fs_asset_handler.build_saves_file_path(
            user=admin_user,
            platform_fs_slug=platform.fs_slug,
            rom_id=rom.id,
            emulator="mgba",
        )
        self._other_client_save(admin_user, rom, mgba_path, b"gba", emulator="mgba")

        response = client.get(self.SAVE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_an_unslotted_save_serves_until_the_first_upload(
        self, client, admin_user: User, rom: Rom, synced_save: Save
    ):
        disk_path = fs_asset_handler.validate_path(synced_save.full_path)
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_bytes(b"legacy")
        assert self._get(client) == b"legacy"

        self._put(client, b"slotted")

        assert [save.slot for save in self._versions(admin_user, rom)] == [
            "autosave",
            None,
        ]
        assert self._get(client) == b"slotted"

    @_mock_asset_md5()
    def test_a_companion_file_stays_one_unslotted_save(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._put(client, b"save")
        assert self._put(client, b"clock", self.RTC_URL) == status.HTTP_201_CREATED
        assert self._put(client, b"ticked", self.RTC_URL) == (
            status.HTTP_204_NO_CONTENT
        )

        rtc = [save for save in self._versions(admin_user, rom) if save.slot is None]
        assert [(save.file_name, save.file_size_bytes) for save in rtc] == [
            ("test_rom.rtc", len(b"ticked"))
        ]
        assert self._get(client, self.RTC_URL) == b"ticked"
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)
        assert sorted(entry["path"] for entry in response.json()) == [
            "saves/Snes9x/test_rom.rtc",
            "saves/Snes9x/test_rom.srm",
        ]

    def test_prunes_versions_past_the_slot_cap(
        self, client, admin_user: User, rom: Rom
    ):
        with mock.patch("handler.sync.retroarch.sync_handler.MAX_SAVES_PER_SLOT", 2):
            for content in (b"one", b"two", b"three"):
                self._put(client, content)

        assert [save.file_size_bytes for save in self._versions(admin_user, rom)] == [
            len(b"three"),
            len(b"two"),
        ]

    def test_pruning_keeps_other_cores_versions(
        self, client, admin_user: User, rom: Rom
    ):
        mgba_save = make_save(
            rom, admin_user, "test_rom.srm", emulator="mgba", slot="autosave"
        )

        with mock.patch("handler.sync.retroarch.sync_handler.MAX_SAVES_PER_SLOT", 1):
            for content in (b"one", b"two"):
                self._put(client, content)

        versions = self._versions(admin_user, rom)
        assert mgba_save.id in {save.id for save in versions}
        assert len(versions) == 2
        assert self._get(client) == b"two"

    def test_delete_removes_everything_the_path_serves(
        self, client, admin_user: User, rom: Rom, saves_path: str, synced_save: Save
    ):
        self._other_client_save(admin_user, rom, saves_path, b"native")
        self._put(client, b"retroarch")
        mgba_save = make_save(
            rom, admin_user, "test_rom.srm", emulator="mgba", slot="autosave"
        )

        response = client.request("DELETE", self.SAVE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert [save.id for save in self._versions(admin_user, rom)] == [mgba_save.id]
        assert client.get(self.SAVE_URL, auth=ADMIN_AUTH).status_code == (
            status.HTTP_404_NOT_FOUND
        )

    def test_delete_removes_an_unslotted_save_spelled_in_another_case(
        self, client, admin_user: User, rom: Rom, saves_path: str
    ):
        make_save(
            rom,
            admin_user,
            "TEST_ROM.srm",
            file_path=saves_path,
            emulator="snes9x",
            slot=None,
        )
        self._put(client, b"retroarch")

        response = client.request("DELETE", self.SAVE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self._versions(admin_user, rom) == []


def test_uploads_in_the_same_second_keep_both_versions(
    client, admin_user: User, rom: Rom
):
    url = "/api/sync/retroarch/saves/Snes9x/test_rom.srm"
    frozen = datetime(2026, 1, 1, 12, 0, 0)

    with mock.patch("handler.asset_store.datetime") as clock:
        clock.now.return_value = frozen
        for content in (b"first", b"second"):
            assert client.put(url, content=content, auth=ADMIN_AUTH).status_code == (
                status.HTTP_201_CREATED
            )

    versions = db_save_handler.get_saves(
        user_id=admin_user.id, rom_ids=[rom.id], order_by="updated_at", order_dir="asc"
    )
    assert [save.file_size_bytes for save in versions] == [
        len(b"first"),
        len(b"second"),
    ]
    assert len({save.file_name for save in versions}) == 2
    assert all(
        save.file_name.startswith("test_rom [2026-01-01_12-") for save in versions
    )


@pytest.mark.usefixtures("version_names")
class TestRetroArchSyncCoreAliases:
    """Assets another client filed under a different id for a core folder RetroArch reads."""

    SAVE_URL = "/api/sync/retroarch/saves/Beetle%20PSX%20HW/test_rom.srm"
    STATE_URL = "/api/sync/retroarch/states/Beetle%20PSX%20HW/test_rom.state"

    def _write(
        self,
        admin_user: User,
        rom: Rom,
        kind: sync_handler.AssetKind,
        emulator: str,
        file_name: str,
        content: bytes,
    ) -> str:
        path = sync_handler.build_asset_file_path(admin_user, rom, kind, emulator)
        disk_path = fs_asset_handler.validate_path(f"{path}/{file_name}")
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_bytes(content)
        return path

    def _save(
        self,
        admin_user: User,
        rom: Rom,
        emulator: str,
        content: bytes,
        file_name: str = "test_rom [2025-12-31_23-59-59].srm",
        slot: str | None = "autosave",
    ) -> Save:
        path = self._write(admin_user, rom, "saves", emulator, file_name, content)
        return make_save(
            rom,
            admin_user,
            file_name,
            file_path=path,
            file_size_bytes=len(content),
            content_hash=hashlib.md5(content).hexdigest(),
            emulator=emulator,
            slot=slot,
        )

    def _state(
        self,
        admin_user: User,
        rom: Rom,
        emulator: str,
        content: bytes,
        file_name: str = "test_rom.state",
    ) -> State:
        path = self._write(admin_user, rom, "states", emulator, file_name, content)
        return factories.make_state(
            rom,
            admin_user,
            file_name,
            file_path=path,
            file_size_bytes=len(content),
            emulator=emulator,
        )

    def _manifest_paths(self, client: TestClient) -> list[str]:
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)
        return [entry["path"] for entry in response.json()]

    @_mock_asset_md5()
    def test_a_version_under_an_alias_is_listed_and_served(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._save(admin_user, rom, "beetle_psx_hw", b"argosy")

        assert self._manifest_paths(client) == ["saves/Beetle PSX HW/test_rom.srm"]
        response = client.get(self.SAVE_URL, auth=ADMIN_AUTH)
        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"argosy"

    @_mock_asset_md5()
    def test_versions_under_two_aliases_list_once_and_serve_the_newest(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._save(admin_user, rom, "beetle_psx_hw", b"older")
        self._save(
            admin_user,
            rom,
            "mednafen_psx_hw",
            b"newer",
            file_name="test_rom [2026-01-01_00-00-00].srm",
        )

        assert self._manifest_paths(client) == ["saves/Beetle PSX HW/test_rom.srm"]
        assert client.get(self.SAVE_URL, auth=ADMIN_AUTH).content == b"newer"

    def test_reuploading_an_aliased_head_adds_no_version(
        self, client, admin_user: User, rom: Rom
    ):
        self._save(admin_user, rom, "beetle_psx_hw", b"same")

        response = client.put(self.SAVE_URL, content=b"same", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(db_save_handler.get_saves(user_id=admin_user.id)) == 1

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_delete_removes_versions_under_every_alias(
        self, _mock_remove_file: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._save(admin_user, rom, "beetle_psx_hw", b"argosy")
        self._save(
            admin_user,
            rom,
            "mednafen_psx_hw",
            b"retroarch",
            file_name="test_rom [2026-01-01_00-00-00].srm",
        )

        response = client.request("DELETE", self.SAVE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_saves(user_id=admin_user.id) == []

    def test_an_unslotted_file_under_an_alias_is_served_and_updated_in_place(
        self, client, admin_user: User, rom: Rom
    ):
        save = self._save(
            admin_user, rom, "beetle_psx_hw", b"clock", "test_rom.rtc", slot=None
        )
        url = "/api/sync/retroarch/saves/Beetle%20PSX%20HW/test_rom.rtc"
        assert client.get(url, auth=ADMIN_AUTH).content == b"clock"

        response = client.put(url, content=b"ticked", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        [updated] = db_save_handler.get_saves(user_id=admin_user.id)
        assert (updated.id, updated.file_path) == (save.id, save.file_path)
        assert client.get(url, auth=ADMIN_AUTH).content == b"ticked"

    @_mock_asset_md5()
    def test_an_unslotted_file_on_disk_wins_over_a_newer_missing_alias(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._save(
            admin_user, rom, "beetle_psx_hw", b"clock", "test_rom.rtc", slot=None
        )
        missing = self._save(
            admin_user, rom, "mednafen_psx_hw", b"gone", "test_rom.rtc", slot=None
        )
        db_save_handler.update_save(missing.id, {"missing_from_fs": True}, touch=False)
        url = "/api/sync/retroarch/saves/Beetle%20PSX%20HW/test_rom.rtc"

        assert self._manifest_paths(client) == ["saves/Beetle PSX HW/test_rom.rtc"]
        assert client.get(url, auth=ADMIN_AUTH).content == b"clock"

    @_mock_asset_md5()
    def test_a_state_under_an_alias_is_listed_served_and_updated_in_place(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        state = self._state(admin_user, rom, "beetle_psx_hw", b"argosy")

        assert self._manifest_paths(client) == ["states/Beetle PSX HW/test_rom.state"]
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"argosy"

        response = client.put(self.STATE_URL, content=b"retroarch", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        [updated] = db_state_handler.get_states(user_id=admin_user.id)
        assert (updated.id, updated.file_path) == (state.id, state.file_path)
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"retroarch"

    @_mock_asset_md5()
    def test_states_under_two_aliases_in_one_slot_list_once(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        self._state(admin_user, rom, "mednafen_psx_hw", b"newer")

        assert self._manifest_paths(client) == ["states/Beetle PSX HW/test_rom.state"]
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"newer"

    def _missing_state(
        self, admin_user: User, rom: Rom, emulator: str, file_name: str
    ) -> State:
        state = self._state(admin_user, rom, emulator, b"gone", file_name)
        return db_state_handler.update_state(
            state.id, {"missing_from_fs": True}, touch=False
        )

    @_mock_asset_md5()
    def test_a_state_on_disk_wins_over_a_newer_missing_one_in_its_slot(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        self._missing_state(
            admin_user, rom, "beetle_psx_hw", "test_rom [2026-01-01 00-00-00].state"
        )

        assert self._manifest_paths(client) == ["states/Beetle PSX HW/test_rom.state"]
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"older"

    @_mock_asset_md5()
    def test_a_state_on_disk_wins_over_a_newer_missing_alias(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        self._missing_state(admin_user, rom, "mednafen_psx_hw", "test_rom.state")

        assert self._manifest_paths(client) == ["states/Beetle PSX HW/test_rom.state"]
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"older"

    def _vanished_state(self, admin_user: User, rom: Rom, emulator: str) -> State:
        state = self._state(admin_user, rom, emulator, b"gone")
        fs_asset_handler.validate_path(state.full_path).unlink()
        return state

    def test_the_manifest_falls_back_when_the_newest_state_file_vanished(
        self, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        vanished = self._vanished_state(admin_user, rom, "mednafen_psx_hw")

        assert self._manifest_paths(client) == ["states/Beetle PSX HW/test_rom.state"]
        state = db_state_handler.get_state(user_id=admin_user.id, id=vanished.id)
        assert state is not None and state.missing_from_fs

    def test_get_falls_back_when_the_newest_state_file_vanished(
        self, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        vanished = self._vanished_state(admin_user, rom, "mednafen_psx_hw")

        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"older"
        state = db_state_handler.get_state(user_id=admin_user.id, id=vanished.id)
        assert state is not None and state.missing_from_fs

    def test_get_404s_when_every_state_file_in_the_slot_vanished(
        self, client, admin_user: User, rom: Rom
    ):
        self._vanished_state(admin_user, rom, "beetle_psx_hw")
        self._vanished_state(admin_user, rom, "mednafen_psx_hw")

        response = client.get(self.STATE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_uploading_to_a_slot_revives_its_newest_missing_state(
        self, client, admin_user: User, rom: Rom
    ):
        older = self._state(admin_user, rom, "beetle_psx_hw", b"older")
        missing = self._missing_state(
            admin_user, rom, "mednafen_psx_hw", "test_rom.state"
        )

        response = client.put(self.STATE_URL, content=b"fresh", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        states = {s.id: s for s in db_state_handler.get_states(user_id=admin_user.id)}
        assert states.keys() == {older.id, missing.id}
        assert not states[missing.id].missing_from_fs
        assert states[missing.id].file_size_bytes == len(b"fresh")
        assert client.get(self.STATE_URL, auth=ADMIN_AUTH).content == b"fresh"

    @_mock_asset_md5()
    def test_delete_removes_states_under_every_alias_in_the_slot(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"older")
        self._state(admin_user, rom, "mednafen_psx_hw", b"newer")

        response = client.request("DELETE", self.STATE_URL, auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_state_handler.get_states(user_id=admin_user.id) == []
        assert self._manifest_paths(client) == []

    @_mock_asset_md5()
    def test_a_screenshot_for_an_aliased_state_is_filed_beside_it(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, rom: Rom
    ):
        self._state(admin_user, rom, "beetle_psx_hw", b"argosy")

        response = client.put(f"{self.STATE_URL}.png", content=b"png", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_201_CREATED
        assert self._manifest_paths(client) == [
            "states/Beetle PSX HW/test_rom.state",
            "states/Beetle PSX HW/test_rom.state.png",
        ]


class TestRetroArchSyncDownload:
    def test_missing_file_is_not_found(self, client, admin_user: User, rom: Rom):
        response = client.get(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content == b""


def _hold(state: State) -> None:
    """Hold `state` in a snapshot's bank, as a sync channel would."""
    with sync_session.begin() as session:
        snapshot = Snapshot(
            user_id=state.user_id,
            rom_id=state.rom_id,
            kind=SnapshotKind.BRANCH,
            digest="0" * 64,
        )
        snapshot.states = [SnapshotState(core="snes9x", slot="0", state_id=state.id)]
        session.add(snapshot)


def _hold_save(save: Save) -> None:
    """Hold `save` in a snapshot, as a sync channel would."""
    with sync_session.begin() as session:
        session.add(
            Snapshot(
                user_id=save.user_id,
                rom_id=save.rom_id,
                kind=SnapshotKind.BRANCH,
                digest="0" * 64,
                save_id=save.id,
            )
        )


class TestRetroArchSyncHeldState:
    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_state", new_callable=mock.AsyncMock)
    def test_an_upload_files_a_new_state_beside_a_held_one(
        self,
        mock_scan_state: mock.AsyncMock,
        mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        states_path: str,
        make_state,
    ):
        held = make_state("test_rom [2026-07-24 12-04-52-733].state")
        _hold(held)
        mock_scan_state.return_value = State(
            file_name="test_rom.state", file_path=states_path, file_size_bytes=8
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state",
            content=b"statedat",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_write_file.assert_awaited_once()
        assert mock_write_file.call_args.kwargs["filename"] == "test_rom.state"
        kept = db_state_handler.get_state(user_id=admin_user.id, id=held.id)
        assert kept is not None and kept.file_size_bytes == 4

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_state", new_callable=mock.AsyncMock)
    def test_an_upload_onto_a_held_states_own_name_lands_beside_it(
        self,
        mock_scan_state: mock.AsyncMock,
        mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        states_path: str,
        make_state,
    ):
        held = make_state("test_rom.state")
        _hold(held)
        mock_scan_state.return_value = State(
            file_name="test_rom [2026-07-24_12-04-52-733].state",
            file_path=states_path,
            file_size_bytes=8,
        )

        response = client.put(
            "/api/sync/retroarch/states/Snes9x/test_rom.state",
            content=b"statedat",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        written = mock_write_file.call_args.kwargs["filename"]
        assert written != "test_rom.state"
        assert written.startswith("test_rom [") and written.endswith("].state")

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    def test_an_upload_onto_a_held_unslotted_save_is_a_conflict(
        self,
        mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        saves_path: str,
    ):
        held = make_save(
            rom,
            admin_user,
            "test_rom.rtc",
            file_path=saves_path,
            emulator="snes9x",
            slot=None,
        )
        _hold_save(held)

        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.rtc",
            content=b"clock",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        mock_write_file.assert_not_awaited()

    def test_an_upload_onto_a_held_save_ram_adds_a_version_beside_it(
        self, client, admin_user: User, synced_save: Save
    ):
        _hold_save(synced_save)

        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            content=b"savedata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        kept = db_save_handler.get_save(user_id=admin_user.id, id=synced_save.id)
        assert kept is not None and kept.file_size_bytes == 4

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_a_delete_leaves_a_held_state(
        self,
        mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        make_state,
    ):
        held = make_state("test_rom.state")
        _hold(held)

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/states/Snes9x/test_rom.state",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_remove_file.assert_not_awaited()
        assert db_state_handler.get_state(user_id=admin_user.id, id=held.id)

    @mock.patch(
        "handler.asset_store.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_a_delete_leaves_a_held_save(
        self,
        mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        synced_save: Save,
    ):
        _hold_save(synced_save)

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_remove_file.assert_not_awaited()
        assert db_save_handler.get_save(user_id=admin_user.id, id=synced_save.id)


class TestRetroArchSyncDelete:
    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_delete_removes_the_save(
        self,
        mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        synced_save: Save,
    ):
        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_remove_file.assert_awaited_once()
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id]) == []

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.compute_content_hash",
        new_callable=mock.AsyncMock,
        return_value="hash_of_file",
    )
    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_deleting_a_slotted_save_never_hashed_records_its_file_hash(
        self,
        _mock_remove_file: mock.AsyncMock,
        _mock_hash: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        synced_save: Save,
    ):
        db_save_handler.update_save(synced_save.id, {"slot": "autosave"})

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        [record] = db_deleted_asset_handler.get_deletions(
            user_id=admin_user.id, rom_ids=[rom.id]
        )
        assert (record.slot, record.content_hashes) == ("autosave", ["hash_of_file"])

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_deleting_a_slotted_save_records_the_deletion(
        self,
        _mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        saves_path: str,
    ):
        """A device still holding the save must be told it was deleted, not asked for it."""
        make_save(
            rom,
            admin_user,
            "test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            emulator="snes9x",
            slot="autosave",
            content_hash="0123456789abcdef0123456789abcdef",
        )

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        deletions = db_deleted_asset_handler.get_deletions(
            user_id=admin_user.id, rom_ids=[rom.id]
        )
        assert [(d.slot, d.content_hashes) for d in deletions] == [
            ("autosave", ["0123456789abcdef0123456789abcdef"])
        ]

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.remove_file",
        new_callable=mock.AsyncMock,
    )
    def test_move_is_treated_as_a_delete(
        self,
        _mock_remove_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        synced_save: Save,
    ):
        response = client.request(
            "MOVE",
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            headers={"Destination": "/api/sync/retroarch/deleted/saves/test_rom.srm"},
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id]) == []

    def test_delete_of_unknown_file_is_not_found(self, client, admin_user: User):
        response = client.request(
            "DELETE", "/api/sync/retroarch/saves/Snes9x/nope.srm", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


UNKNOWN_FOLDER_URL = "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/UNKNOWN99999DATA0"


def _unknown_folder_pending_dir(user: User) -> Path:
    return fs_retroarch_sync_handler.validate_path(
        psp._pending_dir(user, "UNKNOWN99999DATA0")
    )


class TestRetroArchSyncPsp:
    """PSP save-folder bundling, with roms resolved via the serial map rather than search."""

    @pytest.fixture(autouse=True)
    def _serial_map(self, monkeypatch: pytest.MonkeyPatch, rom: Rom):
        monkeypatch.setattr(
            psp,
            "SYNC_RETROARCH_PSP_SERIAL_MAP",
            {"TEST12345": rom.fs_name_no_ext},
        )

    def test_ignores_system_cache_files(self, client, admin_user: User):
        response = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SYSTEM/CACHE/shader.bin",
            content=b"cache data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_bundles_multiple_files_into_one_save(
        self, client, admin_user: User, rom: Rom
    ):
        put_sfo = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"not real sfo bytes, resolved via SYNC_RETROARCH_PSP_SERIAL_MAP instead",
            auth=ADMIN_AUTH,
        )
        assert put_sfo.status_code == status.HTTP_201_CREATED

        put_data = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"the actual save data",
            auth=ADMIN_AUTH,
        )
        assert put_data.status_code == status.HTTP_201_CREATED

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert len(saves) == 1
        assert saves[0].file_name == "PSP-TEST12345DATA0.zip"

        get_sfo = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_sfo.status_code == status.HTTP_200_OK
        assert (
            get_sfo.content
            == b"not real sfo bytes, resolved via SYNC_RETROARCH_PSP_SERIAL_MAP instead"
        )

        get_data = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert get_data.status_code == status.HTTP_200_OK
        assert get_data.content == b"the actual save data"

    def test_a_held_bundle_is_never_rewritten(self, client, admin_user: User, rom: Rom):
        save_path = "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0"
        client.put(f"{save_path}/PARAM.SFO", content=b"sfo", auth=ADMIN_AUTH)
        client.put(f"{save_path}/SAVE.BIN", content=b"first", auth=ADMIN_AUTH)
        (held,) = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        held_hash = held.content_hash

        with mock.patch(
            "handler.database.db_snapshot_handler.is_frozen",
            side_effect=lambda **kw: kw.get("save_id") == held.id,
        ):
            response = client.put(
                f"{save_path}/SAVE.BIN", content=b"second", auth=ADMIN_AUTH
            )
        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        get_data = client.get(f"{save_path}/SAVE.BIN", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_201_CREATED
        assert len(saves) == 2
        kept = next(s for s in saves if s.id == held.id)
        assert kept.content_hash == held_hash
        assert fs_asset_handler.validate_path(kept.full_path).is_file()
        assert get_data.content == b"second"

    def test_emptying_a_bundle_a_backup_snapshot_holds_deletes_it(
        self, client, admin_user: User, rom: Rom
    ):
        save_path = "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0"
        client.put(f"{save_path}/SAVE.BIN", content=b"only", auth=ADMIN_AUTH)
        (bundle,) = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        with sync_session.begin() as session:
            session.add(
                Snapshot(
                    user_id=admin_user.id,
                    rom_id=rom.id,
                    kind=SnapshotKind.ARCHIVAL,
                    digest="0" * 64,
                    save_id=bundle.id,
                )
            )

        response = client.request("DELETE", f"{save_path}/SAVE.BIN", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id]) == []

    def test_manifest_lists_each_bundle_member_separately(
        self, client, admin_user: User
    ):
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        paths = {entry["path"] for entry in response.json()}
        assert paths == {
            "saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            "saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
        }

    @pytest.mark.parametrize("uploads", [1, 2], ids=["added", "rewritten"])
    def test_upload_primes_the_member_hash_cache(
        self, uploads: int, client, admin_user: User
    ):
        members = {"PARAM.SFO": b"sfo", "SAVE.BIN": b"data"}
        uploaded = list(members.items())[:uploads]
        for name, data in uploaded:
            client.put(
                f"/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/{name}",
                content=data,
                auth=ADMIN_AUTH,
            )

        with mock.patch.object(
            psp, "_load_bundle_entries", wraps=psp._load_bundle_entries
        ) as load_entries:
            response = client.get(
                "/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": f"saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/{name}",
                "hash": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            }
            for name, data in uploaded
        ]
        load_entries.assert_not_called()

    def test_manifest_reads_bundle_hashes_without_per_bundle_gets(
        self, client, admin_user: User
    ):
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        with mock.patch.object(async_cache, "get") as get:
            response = client.get(
                "/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
                "hash": hashlib.md5(b"data", usedforsecurity=False).hexdigest(),
            }
        ]
        get.assert_not_called()

    def test_upload_succeeds_when_priming_the_cache_fails(
        self, client, admin_user: User
    ):
        with mock.patch.object(async_cache, "set", side_effect=RedisError("down")):
            response = client.put(
                "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
                content=b"data",
                auth=ADMIN_AUTH,
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_propfind_lists_bundle_members_without_inflating(
        self, client, admin_user: User
    ):
        for name in ("PARAM.SFO", "SAVE.BIN"):
            client.put(
                f"/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/{name}",
                content=b"data",
                auth=ADMIN_AUTH,
            )

        with mock.patch.object(
            psp, "_load_bundle_entries", wraps=psp._load_bundle_entries
        ) as load_entries:
            response = client.request(
                "PROPFIND",
                "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/",
                auth=ADMIN_AUTH,
            )

        assert response.status_code == 207
        for name in ("PARAM.SFO", "SAVE.BIN"):
            assert f"TEST12345DATA0/{name}</D:href>" in response.text
        load_entries.assert_not_called()

    def test_updates_a_tagged_bundle_in_place(self, client, admin_user: User, rom: Rom):
        tagged_path = fs_asset_handler.build_saves_file_path(
            user=admin_user,
            platform_fs_slug="test_platform_slug",
            rom_id=rom.id,
            emulator="ppsspp",
        )
        tagged_name = "PSP-TEST12345DATA0 [2026-01-01 00-00-00].zip"
        zip_bytes = psp._write_bundle({"PARAM.SFO": b"sfo"})
        disk_path = fs_asset_handler.validate_path(f"{tagged_path}/{tagged_name}")
        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_bytes(zip_bytes)
        make_save(
            rom,
            admin_user,
            tagged_name,
            file_path=tagged_path,
            file_size_bytes=len(zip_bytes),
            emulator="ppsspp",
            slot=None,
        )

        response = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_201_CREATED

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert [save.file_name for save in saves] == [tagged_name]

        get_data = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert get_data.content == b"data"

    def test_slotted_bundle_does_not_shadow_the_manifest_bundle(
        self, client, admin_user: User, rom: Rom
    ):
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"synced",
            auth=ADMIN_AUTH,
        )
        slotted_path = fs_asset_handler.build_saves_file_path(
            user=admin_user,
            platform_fs_slug="test_platform_slug",
            rom_id=rom.id,
            emulator="ppsspp",
        )
        slotted_name = "PSP-TEST12345DATA0 [2026-01-01 00-00-00].zip"
        zip_bytes = psp._write_bundle({"SAVE.BIN": b"history"})
        disk_path = fs_asset_handler.validate_path(f"{slotted_path}/{slotted_name}")
        disk_path.write_bytes(zip_bytes)
        make_save(
            rom,
            admin_user,
            slotted_name,
            file_path=slotted_path,
            file_size_bytes=len(zip_bytes),
            emulator="ppsspp",
            slot="Slot 1",
        )

        get_data = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert get_data.content == b"synced"

        client.delete(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert [save.file_name for save in saves] == [slotted_name]

    def test_bundles_a_folder_synced_without_core_sorting(
        self, client, admin_user: User
    ):
        client.put(
            "/api/sync/retroarch/saves/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert [entry["path"] for entry in response.json()] == [
            "saves/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN"
        ]

    def test_unresolved_folder_is_buffered_until_it_resolves(
        self, client, admin_user: User, rom: Rom, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {})

        response = client.put(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            content=b"orphaned save data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        pending_file = _unknown_folder_pending_dir(admin_user) / "SAVE.BIN"
        assert pending_file.read_bytes() == b"orphaned save data"

        response = client.get(
            "/api/sync/retroarch/psp_pending/UNKNOWN99999DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        monkeypatch.setattr(
            psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {"UNKNOWN99999": rom.fs_name_no_ext}
        )
        response = client.put(
            f"{UNKNOWN_FOLDER_URL}/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert not pending_file.parent.exists()

        response = client.get(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"orphaned save data"

    def test_buffer_past_the_bundle_limits_conflicts(
        self, client, admin_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {})
        monkeypatch.setattr(psp, "_BUNDLE_MAX_MEMBERS", 1)
        client.put(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.put(
            f"{UNKNOWN_FOLDER_URL}/ICON0.PNG",
            content=b"icon",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        pending_dir = _unknown_folder_pending_dir(admin_user)
        assert [path.name for path in pending_dir.iterdir()] == ["SAVE.BIN"]

    def test_delete_drops_the_buffered_copy(
        self, client, admin_user: User, rom: Rom, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {})
        client.put(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            content=b"deleted save data",
            auth=ADMIN_AUTH,
        )

        response = client.delete(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        pending_dir = _unknown_folder_pending_dir(admin_user)
        assert not pending_dir.exists()

        monkeypatch.setattr(
            psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {"UNKNOWN99999": rom.fs_name_no_ext}
        )
        client.put(
            f"{UNKNOWN_FOLDER_URL}/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        response = client.get(
            f"{UNKNOWN_FOLDER_URL}/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_keeps_the_rest_of_the_bundle(
        self, client, admin_user: User, rom: Rom
    ):
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_sfo = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_sfo.status_code == status.HTTP_200_OK
        assert get_sfo.content == b"sfo"

        get_data = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert get_data.status_code == status.HTTP_404_NOT_FOUND

    def test_deleting_every_member_removes_the_bundle(
        self, client, admin_user: User, rom: Rom
    ):
        for name in ("PARAM.SFO", "SAVE.BIN"):
            client.put(
                f"/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/{name}",
                content=b"data",
                auth=ADMIN_AUTH,
            )

        for name in ("PARAM.SFO", "SAVE.BIN"):
            response = client.request(
                "DELETE",
                f"/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/{name}",
                auth=ADMIN_AUTH,
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        assert db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id]) == []

        get_response = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_upload_past_the_bundle_limits_conflicts(
        self, client, admin_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(psp, "_BUNDLE_MAX_MEMBERS", 1)
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )

        response = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        get_sfo = client.get(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_sfo.content == b"sfo"

    def test_unreadable_bundle_survives_a_member_delete(
        self, client, admin_user: User, rom: Rom
    ):
        client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        [bundle] = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        bundle_file = fs_asset_handler.validate_path(bundle.full_path)
        bundle_file.write_bytes(b"not a zip")

        response = client.request(
            "DELETE",
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_save(user_id=admin_user.id, id=bundle.id)
        assert bundle_file.is_file()

        put_response = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )
        assert put_response.status_code == status.HTTP_409_CONFLICT


class TestRetroArchSyncDevice:
    def test_first_manifest_fetch_registers_a_device(self, client, admin_user: User):
        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        devices = db_device_handler.get_devices(user_id=admin_user.id)
        assert len(devices) == 1
        assert devices[0].client == "retroarch"
        assert devices[0].client_device_identifier == CLIENT_DEVICE_IDENTIFIER
        assert devices[0].sync_mode == SyncMode.API
        assert devices[0].last_seen is not None

    def test_later_fetches_reuse_the_device(self, client, admin_user: User):
        client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)
        client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert len(db_device_handler.get_devices(user_id=admin_user.id)) == 1

    def test_each_user_gets_their_own_device(
        self, client, admin_user: User, editor_user: User
    ):
        client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)
        client.get("/api/sync/retroarch/manifest.server", auth=EDITOR_AUTH)

        assert len(db_device_handler.get_devices(user_id=admin_user.id)) == 1
        assert len(db_device_handler.get_devices(user_id=editor_user.id)) == 1

    def test_browsing_does_not_register_a_device(self, client, admin_user: User):
        client.request("PROPFIND", "/api/sync/retroarch/", auth=ADMIN_AUTH)

        assert db_device_handler.get_devices(user_id=admin_user.id) == []


class TestRetroArchSyncMkcol:
    def test_mkcol_succeeds_without_creating_anything(self, client, admin_user: User):
        response = client.request(
            "MKCOL", "/api/sync/retroarch/saves/Snes9x", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_201_CREATED


class TestRetroArchSyncBlobPathParsing:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("config/retroarch.cfg", "config/retroarch.cfg"),
            (
                "thumbnails/Nintendo - Game Boy/Named_Boxarts/Game.png",
                "thumbnails/Nintendo - Game Boy/Named_Boxarts/Game.png",
            ),
            ("system/bios/scph5501.bin", "system/bios/scph5501.bin"),
            ("/system/bios.bin", "system/bios.bin"),
        ],
    )
    def test_parses_blob_paths(self, path, expected):
        assert sync_handler.parse_retroarch_sync_blob_path(path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "config",
            "saves/test_rom.srm",
            "deleted/config/retroarch.cfg",
            "config/../../etc/passwd",
        ],
    )
    def test_rejects_non_blob_paths(self, path):
        assert sync_handler.parse_retroarch_sync_blob_path(path) is None


class TestRetroArchSyncBlobs:
    def test_creates_and_downloads_config_blob(self, client, admin_user: User):
        put_response = client.put(
            "/api/sync/retroarch/config/retroarch.cfg",
            content=b"data",
            auth=ADMIN_AUTH,
        )
        assert put_response.status_code == status.HTTP_201_CREATED

        get_response = client.get(
            "/api/sync/retroarch/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.content == b"data"

    def test_overwrites_existing_blob_in_place(self, client, admin_user: User):
        client.put(
            "/api/sync/retroarch/system/bios.bin", content=b"data", auth=ADMIN_AUTH
        )

        response = client.put(
            "/api/sync/retroarch/system/bios.bin",
            content=b"newdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = client.get(
            "/api/sync/retroarch/system/bios.bin", auth=ADMIN_AUTH
        )
        assert get_response.content == b"newdata"

    def test_accepts_nested_thumbnail_paths(self, client, admin_user: User):
        response = client.put(
            "/api/sync/retroarch/thumbnails/Nintendo - Game Boy/Named_Boxarts/Game.png",
            content=b"pngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_missing_blob_is_not_found(self, client, admin_user: User):
        response = client.get("/api/sync/retroarch/config/nope.cfg", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content == b""

    def test_delete_removes_the_blob(self, client, admin_user: User):
        client.put(
            "/api/sync/retroarch/config/retroarch.cfg",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.request(
            "DELETE", "/api/sync/retroarch/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = client.get(
            "/api/sync/retroarch/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_of_unknown_blob_is_not_found(self, client, admin_user: User):
        response = client.request(
            "DELETE", "/api/sync/retroarch/config/nope.cfg", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_of_a_nul_blob_path_is_not_found(self, client, admin_user: User):
        response = client.request(
            "DELETE", "/api/sync/retroarch/config/a%00b.cfg", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rejects_a_chunked_blob_over_the_upload_cap(self, client, admin_user: User):
        with _retroarch_upload_cap(client, 4):
            response = client.put(
                "/api/sync/retroarch/config/retroarch.cfg",
                content=iter([b"dat", b"a!"]),
                auth=ADMIN_AUTH,
            )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        get_response = client.get(
            "/api/sync/retroarch/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_manifest_includes_blobs_alongside_assets(self, client, admin_user: User):
        client.put(
            "/api/sync/retroarch/config/retroarch.cfg",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.get("/api/sync/retroarch/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "config/retroarch.cfg",
                "hash": "8d777f385d3dfec8815d20f7496026dc",
            }
        ]


class TestRetroArchSyncBrowsing:
    """Read-only WebDAV browsing (PROPFIND, LOCK, the `roms/` redirect) for generic clients."""

    def test_lock_succeeds(self, client, admin_user: User):
        response = client.request("LOCK", "/api/sync/retroarch/roms/", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["lock-token"].startswith("<opaquelocktoken:")

    def test_unlock_succeeds(self, client, admin_user: User):
        response = client.request(
            "UNLOCK", "/api/sync/retroarch/roms/", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_propfind_without_credentials_challenges(self, client):
        response = client.request("PROPFIND", "/api/sync/retroarch/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_propfind_root_lists_virtual_roots(self, client, admin_user: User):
        response = client.request("PROPFIND", "/api/sync/retroarch/", auth=ADMIN_AUTH)

        assert response.status_code == 207
        body = response.text
        assert "<D:href>/api/sync/retroarch/roms/</D:href>" in body
        assert "<D:href>/api/sync/retroarch/saves/</D:href>" in body
        assert "<D:href>/api/sync/retroarch/states/</D:href>" in body

    def test_propfind_roms_lists_platforms_with_roms(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/roms/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert (
            f"<D:href>/api/sync/retroarch/roms/{rom.platform.fs_slug}/</D:href>"
            in response.text
        )

    def test_propfind_platform_lists_rom_files(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.request(
            "PROPFIND",
            f"/api/sync/retroarch/roms/{rom.platform.fs_slug}/",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == 207
        assert (
            f"<D:href>/api/sync/retroarch/roms/{rom.platform.fs_slug}/{rom.fs_name}</D:href>"
            in response.text
        )

    def test_propfind_unknown_platform_is_not_found(self, client, admin_user: User):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/roms/nope/", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_rom_file_redirects_to_rest_content_endpoint(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.get(
            f"/api/sync/retroarch/roms/{rom.platform.fs_slug}/{rom.fs_name}",
            auth=ADMIN_AUTH,
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert (
            response.headers["location"] == f"/api/roms/{rom.id}/content/{rom.fs_name}"
        )

    def test_get_unknown_rom_file_is_not_found(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.get(
            f"/api/sync/retroarch/roms/{rom.platform.fs_slug}/nope.zip",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_propfind_saves_lists_the_emulator_subfolder(
        self, client, admin_user: User, synced_save: Save
    ):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/saves/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert "<D:href>/api/sync/retroarch/saves/Snes9x/</D:href>" in response.text

    def test_propfind_saves_subfolder_lists_the_file(
        self, client, admin_user: User, synced_save: Save
    ):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/saves/Snes9x/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert (
            "<D:href>/api/sync/retroarch/saves/Snes9x/test_rom.srm</D:href>"
            in response.text
        )

    @_mock_asset_md5()
    @mock.patch(
        "handler.sync.retroarch.sync_handler.fs_retroarch_sync_handler.list_blob_files",
        new_callable=mock.AsyncMock,
    )
    def test_propfind_lists_without_hashing_or_walking_blobs(
        self,
        list_blob_files: mock.AsyncMock,
        asset_md5s: mock.AsyncMock,
        client,
        admin_user: User,
        synced_save: Save,
        synced_state_screenshot: Screenshot,
    ):
        saves = client.request(
            "PROPFIND", "/api/sync/retroarch/saves/Snes9x/", auth=ADMIN_AUTH
        )
        states = client.request(
            "PROPFIND", "/api/sync/retroarch/states/Snes9x/", auth=ADMIN_AUTH
        )

        assert saves.status_code == 207
        assert "/api/sync/retroarch/saves/Snes9x/test_rom.srm<" in saves.text
        assert states.status_code == 207
        assert "/api/sync/retroarch/states/Snes9x/test_rom.state<" in states.text
        assert "/api/sync/retroarch/states/Snes9x/test_rom.state.png<" in states.text
        asset_md5s.assert_not_awaited()
        list_blob_files.assert_not_awaited()

    def test_propfind_builds_only_the_requested_tree(
        self, client, admin_user: User, synced_save: Save, synced_state: State
    ):
        with (
            mock.patch.object(
                db_save_handler,
                "get_saves",
                wraps=db_save_handler.get_saves,
            ) as get_saves,
            mock.patch.object(
                db_state_handler,
                "get_states",
                wraps=db_state_handler.get_states,
            ) as get_states,
        ):
            client.request(
                "PROPFIND", "/api/sync/retroarch/states/Snes9x/", auth=ADMIN_AUTH
            )
            get_saves.assert_not_called()
            get_states.reset_mock()

            client.request(
                "PROPFIND", "/api/sync/retroarch/saves/Snes9x/", auth=ADMIN_AUTH
            )
            get_states.assert_not_called()
