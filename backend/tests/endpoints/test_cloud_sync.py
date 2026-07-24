from unittest import mock

import pytest
from fastapi import status

from handler import cloud_sync_handler
from handler.database import db_save_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from models.assets import Save, State
from models.rom import Rom
from models.user import User

ADMIN_AUTH = ("test_admin", "test_admin_password")


@pytest.fixture
def saves_path(admin_user: User, rom: Rom):
    return fs_asset_handler.build_saves_file_path(
        user=admin_user,
        platform_fs_slug="test_platform_slug",
        rom_id=rom.id,
        emulator="Snes9x",
    )


@pytest.fixture
def synced_save(admin_user: User, rom: Rom, saves_path: str):
    """A save stored where the cloud-sync path `saves/Snes9x/test_rom.srm`
    resolves to, unlike the shared fixtures' legacy layout."""
    return db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_rom.srm",
            file_path=saves_path,
            file_size_bytes=4,
            emulator="Snes9x",
            slot=None,
        )
    )


class TestCloudSyncPathParsing:
    @pytest.mark.parametrize(
        ("path", "kind", "emulator", "file_name"),
        [
            ("saves/test_rom.srm", "saves", None, "test_rom.srm"),
            ("saves/Snes9x/test_rom.srm", "saves", "Snes9x", "test_rom.srm"),
            ("states/Snes9x/test_rom.state", "states", "Snes9x", "test_rom.state"),
            ("/states/test_rom.state.auto", "states", None, "test_rom.state.auto"),
        ],
    )
    def test_parses_supported_paths(self, path, kind, emulator, file_name):
        parsed = cloud_sync_handler.parse_cloud_sync_path(path)

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
        ],
    )
    def test_rejects_unsupported_paths(self, path):
        assert cloud_sync_handler.parse_cloud_sync_path(path) is None

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
        assert cloud_sync_handler.game_name_from_file_name(kind, file_name) == game_name


class TestCloudSyncAuth:
    def test_options_without_credentials_challenges(self, client):
        response = client.options("/api/cloud-sync/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["www-authenticate"].startswith("Basic")
        assert response.content == b""

    def test_options_with_basic_auth_advertises_dav(self, client, admin_user: User):
        response = client.options("/api/cloud-sync/", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["dav"] == "1"
        assert "MKCOL" in response.headers["allow"]

    def test_get_without_credentials_challenges(self, client):
        response = client.get("/api/cloud-sync/manifest.server")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_without_credentials_challenges(self, client):
        response = client.put("/api/cloud-sync/saves/test_rom.srm", content=b"data")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCloudSyncManifest:
    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_lists_saves_and_states(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        archival_save: Save,
        state: State,
    ):
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/test_emulator/archival.sav",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
            {
                "path": "states/test_emulator/test_state.state",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
        ]

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_excludes_slotted_saves(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, save: Save
    ):
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_empty_library_returns_empty_manifest(self, client, admin_user: User):
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestCloudSyncUpload:
    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_save", new_callable=mock.AsyncMock)
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
            "/api/cloud-sync/saves/Snes9x/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_write_file.assert_awaited_once()

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
        assert len(saves) == 1
        assert saves[0].file_name == "test_rom.srm"
        assert saves[0].emulator == "Snes9x"
        assert saves[0].slot is None

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_save", new_callable=mock.AsyncMock)
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
            "/api/cloud-sync/saves/Snes9x/test_rom.srm",
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
            "/api/cloud-sync/saves/Snes9x/test_rom.srm",
            content=b"newdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
        assert len(saves) == 1
        assert saves[0].file_size_bytes == 7

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_state", new_callable=mock.AsyncMock)
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
            emulator="Snes9x",
        )
        mock_scan_state.return_value = State(
            file_name="test_rom.state.auto",
            file_path=states_path,
            file_size_bytes=8,
        )

        response = client.put(
            "/api/cloud-sync/states/Snes9x/test_rom.state.auto",
            content=b"statedat",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED

        states = db_state_handler.get_states(user_id=admin_user.id, rom_id=rom.id)
        assert len(states) == 1
        assert states[0].file_name == "test_rom.state.auto"

    def test_rejects_upload_with_no_matching_rom(self, client, admin_user: User):
        response = client.put(
            "/api/cloud-sync/saves/Snes9x/not_in_library.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        # A conflict rather than a fake success: the client keeps its copy and
        # retries, instead of recording a file the server never stored.
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.content == b""

    def test_rejects_unsupported_sync_root(self, client, admin_user: User, rom: Rom):
        response = client.put(
            "/api/cloud-sync/deleted/saves/test_rom.srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_accepts_and_drops_client_manifest(self, client, admin_user: User):
        response = client.put(
            "/api/cloud-sync/manifest.server", content=b"[]", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestCloudSyncDownload:
    def test_missing_file_is_not_found(self, client, admin_user: User, rom: Rom):
        response = client.get(
            "/api/cloud-sync/saves/Snes9x/test_rom.srm", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content == b""


class TestCloudSyncDelete:
    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
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
            "/api/cloud-sync/saves/Snes9x/test_rom.srm",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_remove_file.assert_awaited_once()
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id) == []

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
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
            "/api/cloud-sync/saves/Snes9x/test_rom.srm",
            headers={"Destination": "/api/cloud-sync/deleted/saves/test_rom.srm"},
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id) == []

    def test_delete_of_unknown_file_is_not_found(self, client, admin_user: User):
        response = client.request(
            "DELETE", "/api/cloud-sync/saves/Snes9x/nope.srm", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCloudSyncMkcol:
    def test_mkcol_succeeds_without_creating_anything(self, client, admin_user: User):
        response = client.request(
            "MKCOL", "/api/cloud-sync/saves/Snes9x", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_201_CREATED


class TestCloudSyncBlobPathParsing:
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
        assert cloud_sync_handler.parse_cloud_sync_blob_path(path) == expected

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
        assert cloud_sync_handler.parse_cloud_sync_blob_path(path) is None


class TestCloudSyncBlobs:
    def test_creates_and_downloads_config_blob(self, client, admin_user: User):
        put_response = client.put(
            "/api/cloud-sync/config/retroarch.cfg",
            content=b"data",
            auth=ADMIN_AUTH,
        )
        assert put_response.status_code == status.HTTP_201_CREATED

        get_response = client.get(
            "/api/cloud-sync/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.content == b"data"

    def test_overwrites_existing_blob_in_place(self, client, admin_user: User):
        client.put("/api/cloud-sync/system/bios.bin", content=b"data", auth=ADMIN_AUTH)

        response = client.put(
            "/api/cloud-sync/system/bios.bin", content=b"newdata", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = client.get("/api/cloud-sync/system/bios.bin", auth=ADMIN_AUTH)
        assert get_response.content == b"newdata"

    def test_accepts_nested_thumbnail_paths(self, client, admin_user: User):
        response = client.put(
            "/api/cloud-sync/thumbnails/Nintendo - Game Boy/Named_Boxarts/Game.png",
            content=b"pngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_missing_blob_is_not_found(self, client, admin_user: User):
        response = client.get("/api/cloud-sync/config/nope.cfg", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content == b""

    def test_delete_removes_the_blob(self, client, admin_user: User):
        client.put(
            "/api/cloud-sync/config/retroarch.cfg", content=b"data", auth=ADMIN_AUTH
        )

        response = client.request(
            "DELETE", "/api/cloud-sync/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = client.get(
            "/api/cloud-sync/config/retroarch.cfg", auth=ADMIN_AUTH
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_of_unknown_blob_is_not_found(self, client, admin_user: User):
        response = client.request(
            "DELETE", "/api/cloud-sync/config/nope.cfg", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_manifest_includes_blobs_alongside_assets(self, client, admin_user: User):
        client.put(
            "/api/cloud-sync/config/retroarch.cfg", content=b"data", auth=ADMIN_AUTH
        )

        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "config/retroarch.cfg",
                "hash": "8d777f385d3dfec8815d20f7496026dc",
            }
        ]
