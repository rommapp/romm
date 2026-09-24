from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import (
    db_device_handler,
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.filesystem import fs_asset_handler
from handler.middleware.upload_size_middleware import UploadSizeLimitMiddleware
from handler.sync.retroarch import psp, sync_handler
from handler.sync.retroarch.device import CLIENT_DEVICE_IDENTIFIER
from handler.sync.retroarch.emulator_names import (
    to_retroarch_dir_name,
    to_romm_emulator,
)
from models.assets import Save, Screenshot, State
from models.device import SyncMode
from models.platform import Platform
from models.rom import Rom
from models.user import User

ADMIN_AUTH = ("test_admin", "test_admin_password")
EDITOR_AUTH = ("test_editor", "test_editor_password")
EMPTY_MD5 = "d41d8cd98f00b204e9800998ecf8427e"


def _mock_asset_md5():
    return mock.patch(
        "handler.sync.retroarch.sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value=EMPTY_MD5,
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
    return db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            emulator="snes9x",
            slot=None,
        )
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
        return db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )

    return make


@pytest.fixture
def synced_state(make_state):
    """A state with RetroArch's own `<rom>.state` name, unlike the shared fixture."""
    return make_state("test_rom.state")


@pytest.fixture
def synced_state_screenshot(admin_user: User, rom: Rom, synced_state: State):
    """The `<state file name>.png` screenshot RetroArch syncs next to a state."""
    return db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name=f"{synced_state.file_name}.png",
            file_path=sync_handler.state_screenshot_dir(admin_user, rom, "snes9x"),
            file_size_bytes=8,
        )
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

    def test_kiosk_guest_is_challenged(self, client):
        with mock.patch("handler.auth.hybrid_auth.KIOSK_MODE", True):
            options = client.options("/api/sync/retroarch/")
            manifest = client.get("/api/sync/retroarch/manifest.server")

        assert options.status_code == status.HTTP_401_UNAUTHORIZED
        assert manifest.status_code == status.HTTP_401_UNAUTHORIZED


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
    def test_excludes_slotted_saves(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, save: Save
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
        shadowed_rom = db_rom_handler.add_rom(
            Rom(
                platform_id=other_platform.id,
                name="test_rom",
                slug="test_rom_slug_other",
                fs_name="test_rom.zip",
                fs_name_no_tags="test_rom",
                fs_name_no_ext="test_rom",
                fs_extension="zip",
                fs_path=f"{other_platform.slug}/roms",
            )
        )
        db_save_handler.add_save(
            Save(
                rom_id=shadowed_rom.id,
                user_id=admin_user.id,
                file_name="test_rom.srm",
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
        db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=synced_state.file_name,
                file_path=fs_asset_handler.build_states_file_path(
                    user=admin_user,
                    platform_fs_slug=rom.platform.fs_slug,
                    rom_id=rom.id,
                    emulator="bsnes",
                ),
                file_size_bytes=4,
                emulator="bsnes",
            )
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
    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_save", new_callable=mock.AsyncMock)
    def test_creates_save_for_matching_rom(
        self,
        mock_scan_save: mock.AsyncMock,
        mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        saves_path: str,
    ):
        mock_scan_save.return_value = Save(
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            content_hash="8d777f385d3dfec8815d20f7496026dc",
        )

        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_write_file.assert_awaited_once()

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert len(saves) == 1
        assert saves[0].file_name == "test_rom.srm"
        assert saves[0].emulator == "snes9x"
        assert saves[0].slot is None

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_save", new_callable=mock.AsyncMock)
    def test_overwrites_existing_save_in_place(
        self,
        mock_scan_save: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        saves_path: str,
    ):
        mock_scan_save.return_value = Save(
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            content_hash="8d777f385d3dfec8815d20f7496026dc",
        )
        client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        mock_scan_save.return_value = Save(
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=7,
            content_hash="9a0364b9e99bb480dd25e1f0284c8555",
        )
        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            content=b"newdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_ids=[rom.id])
        assert len(saves) == 1
        assert saves[0].file_size_bytes == 7

    @mock.patch(
        "endpoints.sync.retroarch.fs_asset_handler.write_file",
        new_callable=mock.AsyncMock,
    )
    @mock.patch("endpoints.sync.retroarch.scan_save", new_callable=mock.AsyncMock)
    def test_overwrite_clears_missing_from_fs(
        self,
        mock_scan_save: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        synced_save: Save,
        saves_path: str,
    ):
        db_save_handler.update_save(synced_save.id, {"missing_from_fs": True})
        mock_scan_save.return_value = Save(
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            content_hash="8d777f385d3dfec8815d20f7496026dc",
        )

        response = client.put(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        save = db_save_handler.get_save(user_id=admin_user.id, id=synced_save.id)
        assert save is not None
        assert not save.missing_from_fs

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
        legacy_state = db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom.state",
                file_path="legacy/states/snes9x",
                file_size_bytes=4,
                emulator="snes9x",
            )
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


class TestRetroArchSyncDownload:
    def test_missing_file_is_not_found(self, client, admin_user: User, rom: Rom):
        response = client.get(
            "/api/sync/retroarch/saves/Snes9x/test_rom.srm", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content == b""


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
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=tagged_name,
                file_path=tagged_path,
                file_size_bytes=len(zip_bytes),
                emulator="ppsspp",
                slot=None,
            )
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
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=slotted_name,
                file_path=slotted_path,
                file_size_bytes=len(zip_bytes),
                emulator="ppsspp",
                slot="Slot 1",
            )
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

    def test_unresolved_folder_is_buffered_and_conflicts(
        self, client, admin_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(psp, "SYNC_RETROARCH_PSP_SERIAL_MAP", {})

        response = client.put(
            "/api/sync/retroarch/saves/PPSSPP/PSP/SAVEDATA/UNKNOWN99999DATA0/SAVE.BIN",
            content=b"orphaned save data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

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

    @_mock_asset_md5()
    def test_propfind_saves_lists_the_emulator_subfolder(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/saves/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert "<D:href>/api/sync/retroarch/saves/Snes9x/</D:href>" in response.text

    @_mock_asset_md5()
    def test_propfind_saves_subfolder_lists_the_file(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        response = client.request(
            "PROPFIND", "/api/sync/retroarch/saves/Snes9x/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert (
            "<D:href>/api/sync/retroarch/saves/Snes9x/test_rom.srm</D:href>"
            in response.text
        )
