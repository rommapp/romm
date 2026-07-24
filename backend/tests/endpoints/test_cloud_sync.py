from unittest import mock

import pytest
from fastapi import status

from handler import cloud_sync_handler, cloud_sync_psp
from handler.cloud_sync_emulator_names import to_retroarch_dir_name, to_romm_emulator
from handler.database import (
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.filesystem import fs_asset_handler
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom
from models.user import User

ADMIN_AUTH = ("test_admin", "test_admin_password")


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
    """A save stored where the cloud-sync path `saves/Snes9x/test_rom.srm`
    resolves to, unlike the shared fixtures' legacy layout. `emulator` is
    RomM's own convention (lowercase), not RetroArch's directory casing --
    see `parse_cloud_sync_path`."""
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
def synced_state(admin_user: User, rom: Rom, states_path: str):
    """A state named the way RetroArch itself would name one -- `<rom>.state`
    -- unlike the shared `state` fixture, whose file name is a test-only
    placeholder unrelated to `rom.fs_name_no_ext`."""
    return db_state_handler.add_state(
        State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_rom.state",
            file_path=states_path,
            file_size_bytes=4,
            emulator="snes9x",
        )
    )


@pytest.fixture
def synced_state_screenshot(admin_user: User, rom: Rom, synced_state: State):
    """The screenshot RetroArch captures and syncs alongside a state, under
    `<state file name>.png` -- attached to the ROM, not the state row
    itself (there's no `screenshot_id` column on `State`; `state.screenshot`
    finds it by matching file name stems)."""
    return db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name=f"{synced_state.file_name}.png",
            file_path=synced_state.file_path,
            file_size_bytes=8,
        )
    )


@pytest.fixture
def web_state(admin_user: User, rom: Rom, states_path: str):
    """A state named the way RomM's own web player names one: a display
    label plus a timestamp, with no relation to RetroArch's `<rom>.state[N]`
    numbered-slot convention -- see `is_retroarch_loadable_state`."""
    return db_state_handler.add_state(
        State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_rom [2026-07-24 12-04-52-733].state",
            file_path=states_path,
            file_size_bytes=4,
            emulator="snes9x",
        )
    )


class TestCloudSyncEmulatorNames:
    @pytest.mark.parametrize(
        ("retroarch_dir_name", "romm_emulator"),
        [
            ("Snes9x", "snes9x"),
            ("Genesis Plus GX", "genesis_plus_gx"),
            ("PCSX-ReARMed", "pcsx_rearmed"),
            ("RetroArduous", "retroarduous"),
        ],
    )
    def test_to_romm_emulator(self, retroarch_dir_name, romm_emulator):
        assert to_romm_emulator(retroarch_dir_name) == romm_emulator

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


class TestCloudSyncPathParsing:
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
                "retroarduous",
                "test_rom.srm",
            ),
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
        assert response.headers["dav"] == "1, 2"
        assert "MKCOL" in response.headers["allow"]
        assert "PROPFIND" in response.headers["allow"]

    def test_get_without_credentials_challenges(self, client):
        response = client.get("/api/cloud-sync/manifest.server")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_without_credentials_challenges(self, client):
        response = client.put("/api/cloud-sync/saves/test_rom.srm", content=b"data")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCloudSyncStateSlotResolution:
    def test_resolves_canonical_name_to_the_web_created_row(
        self, admin_user: User, rom: Rom, web_state: State
    ):
        """A GET/DELETE for the canonical slot name the manifest advertised
        must resolve back to the real row even though its actual `file_name`
        (a web-player timestamp label) never matches that canonical name."""
        resolved = cloud_sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is not None
        assert resolved.id == web_state.id

    def test_resolves_to_the_newer_of_two_competing_states(
        self, admin_user: User, rom: Rom, states_path: str
    ):
        older = db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom.state",
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )
        newer = db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom [2026-07-24 12-04-52-733].state",
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )
        assert newer.id > older.id

        resolved = cloud_sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is not None
        assert resolved.id == newer.id

    def test_does_not_cross_slots(self, admin_user: User, rom: Rom, states_path: str):
        """A slot-1 state must never resolve for a slot-0 request, even
        though both belong to the same rom/emulator."""
        db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom.state1",
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )

        resolved = cloud_sync_handler.resolve_state_by_slot(
            admin_user, rom, "snes9x", "test_rom.state"
        )

        assert resolved is None


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
        synced_state: State,
    ):
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/test_emulator/archival.sav",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
        ]

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_remaps_web_player_state_to_canonical_slot(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, web_state: State
    ):
        """A state uploaded through RomM's own web player carries a display
        label and timestamp in its file name, not a RetroArch slot number --
        RetroArch's Load State menu only ever offers numbered slots 0-999
        (verified live: RetroArch fetched such a file during a real sync,
        and it never appeared as a loadable slot because its raw file name
        was surfaced as-is). It still belongs to slot 0 like any other
        untagged state, so the manifest advertises it under RetroArch's own
        canonical name for that slot instead of its raw file name."""
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            }
        ]

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_newest_state_in_a_slot_wins_regardless_of_origin(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        rom: Rom,
        states_path: str,
    ):
        """Two states competing for the same (rom, emulator, slot) bucket --
        an older RetroArch-native one and a newer web-player one -- resolve
        to whichever is actually newest, same as the shim's `sortByRecency`
        picking "the" state for a slot regardless of who created it."""
        older = db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom.state",
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )
        newer = db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_rom [2026-07-24 12-04-52-733].state",
                file_path=states_path,
                file_size_bytes=4,
                emulator="snes9x",
            )
        )
        assert newer.id > older.id

        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            }
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

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_round_trips_emulator_casing_through_the_manifest(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        """`synced_save` is stored with RomM's own convention (`snes9x`,
        lowercase). The manifest must hand RetroArch back its own directory
        casing (`Snes9x`), not RomM's -- see `to_retroarch_dir_name`."""
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "saves/Snes9x/test_rom.srm",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            }
        ]


class TestCloudSyncStateScreenshots:
    def test_game_name_strips_png_before_state_suffix(self):
        """RetroArch syncs a state's screenshot as `<state file name>.png`
        (e.g. `test_rom.state.png`) -- the ROM name must resolve the same
        way it would for the state itself, not stop at the `.state` segment
        (verified live: RetroArch's upload of this file 409'd because the
        naive last-dot split reported the game name as `test_rom.state`)."""
        assert (
            cloud_sync_handler.game_name_from_file_name(
                "states", "test_rom.state.png"
            )
            == "test_rom"
        )
        assert (
            cloud_sync_handler.game_name_from_file_name(
                "states", "test_rom.state3.png"
            )
            == "test_rom"
        )
        assert (
            cloud_sync_handler.game_name_from_file_name(
                "states", "test_rom.state.auto.png"
            )
            == "test_rom"
        )

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_manifest_includes_the_state_screenshot(
        self,
        _asset_md5: mock.AsyncMock,
        client,
        admin_user: User,
        synced_state: State,
        synced_state_screenshot: Screenshot,
    ):
        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "path": "states/Snes9x/test_rom.state",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
            {
                "path": "states/Snes9x/test_rom.state.png",
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
            },
        ]

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_screenshot", new_callable=mock.AsyncMock)
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
            "/api/cloud-sync/states/Snes9x/test_rom.state.png",
            content=b"pngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED
        screenshots = db_screenshot_handler.get_screenshot(
            rom_id=rom.id, user_id=admin_user.id, file_name="test_rom.state.png"
        )
        assert screenshots is not None

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_screenshot", new_callable=mock.AsyncMock)
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
            "/api/cloud-sync/states/Snes9x/test_rom.state.png",
            content=b"newpngdata",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT


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
        assert saves[0].emulator == "snes9x"
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
            emulator="snes9x",
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

    @mock.patch(
        "endpoints.cloud_sync.fs_asset_handler.write_file", new_callable=mock.AsyncMock
    )
    @mock.patch("endpoints.cloud_sync.scan_save", new_callable=mock.AsyncMock)
    def test_matches_rom_with_plus_in_name(
        self,
        mock_scan_save: mock.AsyncMock,
        _mock_write_file: mock.AsyncMock,
        client,
        admin_user: User,
        platform: Platform,
    ):
        """"+" is not invalid on any real filesystem -- RomM itself stores
        combo-cart ROMs with it in `fs_name` untouched, so stripping it
        before resolving the ROM (as `sanitize_filename` used to) broke
        matching for exactly those titles."""
        combo_rom = Rom(
            platform_id=platform.id,
            name="Super Mario All-Stars + Super Mario World",
            slug="combo-rom-slug",
            fs_name="Super Mario All-Stars + Super Mario World (USA).sfc",
            fs_name_no_tags="Super Mario All-Stars + Super Mario World",
            fs_name_no_ext="Super Mario All-Stars + Super Mario World (USA)",
            fs_extension="sfc",
            fs_path=f"{platform.slug}/roms",
        )
        combo_rom = db_rom_handler.add_rom(combo_rom)
        db_rom_handler.add_rom_user(rom_id=combo_rom.id, user_id=admin_user.id)

        saves_path = fs_asset_handler.build_saves_file_path(
            user=admin_user,
            platform_fs_slug="test_platform_slug",
            rom_id=combo_rom.id,
            emulator="snes9x",
        )
        mock_scan_save.return_value = Save(
            file_name="Super Mario All-Stars + Super Mario World (USA).srm",
            file_path=saves_path,
            file_size_bytes=4,
            content_hash="8d777f385d3dfec8815d20f7496026dc",
        )

        response = client.put(
            "/api/cloud-sync/saves/Snes9x/Super Mario All-Stars + Super Mario World (USA).srm",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_201_CREATED

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=combo_rom.id)
        assert len(saves) == 1
        assert saves[0].file_name == "Super Mario All-Stars + Super Mario World (USA).srm"

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


class TestCloudSyncPsp:
    """End-to-end coverage of the PPSSPP save-folder bundling wired into the
    GET/PUT/DELETE endpoints and the manifest -- unit coverage for the pure
    parsing/matching logic lives in tests/handler/test_cloud_sync_psp.py.

    Uses PSP_SERIAL_MAP to resolve the rom deterministically instead of a
    real PARAM.SFO capture + fulltext title search, which would make this
    test depend on the DB driver's fulltext support.
    """

    @pytest.fixture(autouse=True)
    def _serial_map(self, monkeypatch: pytest.MonkeyPatch, rom: Rom):
        monkeypatch.setattr(
            cloud_sync_psp, "PSP_SERIAL_MAP", {"TEST12345": rom.fs_name_no_ext}
        )

    def test_ignores_system_cache_files(self, client, admin_user: User):
        response = client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SYSTEM/CACHE/shader.bin",
            content=b"cache data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_bundles_multiple_files_into_one_save(
        self, client, admin_user: User, rom: Rom
    ):
        put_sfo = client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"not real sfo bytes, resolved via PSP_SERIAL_MAP instead",
            auth=ADMIN_AUTH,
        )
        assert put_sfo.status_code == status.HTTP_201_CREATED

        put_data = client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"the actual save data",
            auth=ADMIN_AUTH,
        )
        assert put_data.status_code == status.HTTP_201_CREATED

        saves = db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id)
        assert len(saves) == 1
        assert saves[0].file_name == "PSP-TEST12345DATA0.zip"

        get_sfo = client.get(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_sfo.status_code == status.HTTP_200_OK
        assert get_sfo.content == b"not real sfo bytes, resolved via PSP_SERIAL_MAP instead"

        get_data = client.get(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert get_data.status_code == status.HTTP_200_OK
        assert get_data.content == b"the actual save data"

    def test_manifest_lists_each_bundle_member_separately(
        self, client, admin_user: User
    ):
        client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.get("/api/cloud-sync/manifest.server", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        paths = {entry["path"] for entry in response.json()}
        assert paths == {
            "saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            "saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
        }

    def test_unresolved_folder_is_buffered_and_conflicts(
        self, client, admin_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(cloud_sync_psp, "PSP_SERIAL_MAP", {})

        response = client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/UNKNOWN99999DATA0/SAVE.BIN",
            content=b"orphaned save data",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_delete_removes_the_whole_bundle(self, client, admin_user: User, rom: Rom):
        client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            content=b"sfo",
            auth=ADMIN_AUTH,
        )
        client.put(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            content=b"data",
            auth=ADMIN_AUTH,
        )

        response = client.request(
            "DELETE",
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/SAVE.BIN",
            auth=ADMIN_AUTH,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert db_save_handler.get_saves(user_id=admin_user.id, rom_id=rom.id) == []

        get_response = client.get(
            "/api/cloud-sync/saves/PPSSPP/PSP/SAVEDATA/TEST12345DATA0/PARAM.SFO",
            auth=ADMIN_AUTH,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


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


class TestCloudSyncWebdavBrowsing:
    """PROPFIND/LOCK/UNLOCK + the `roms/` GET redirect -- read-only WebDAV
    browsing layered onto the same surface, for real WebDAV clients (iOS
    Files, Cyberduck, ...) rather than RetroArch itself (which never issues
    PROPFIND)."""

    def test_lock_succeeds(self, client, admin_user: User):
        response = client.request("LOCK", "/api/cloud-sync/roms/", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["lock-token"].startswith("<opaquelocktoken:")

    def test_unlock_succeeds(self, client, admin_user: User):
        response = client.request("UNLOCK", "/api/cloud-sync/roms/", auth=ADMIN_AUTH)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_propfind_without_credentials_challenges(self, client):
        response = client.request("PROPFIND", "/api/cloud-sync/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_propfind_root_lists_virtual_roots(self, client, admin_user: User):
        response = client.request("PROPFIND", "/api/cloud-sync/", auth=ADMIN_AUTH)

        assert response.status_code == 207
        body = response.text
        assert "<D:href>/api/cloud-sync/roms/</D:href>" in body
        assert "<D:href>/api/cloud-sync/saves/</D:href>" in body
        assert "<D:href>/api/cloud-sync/states/</D:href>" in body

    def test_propfind_roms_lists_platforms_with_roms(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.request(
            "PROPFIND", "/api/cloud-sync/roms/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert f"<D:href>/api/cloud-sync/roms/{rom.platform.fs_slug}/</D:href>" in response.text

    def test_propfind_platform_lists_rom_files(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.request(
            "PROPFIND",
            f"/api/cloud-sync/roms/{rom.platform.fs_slug}/",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == 207
        assert f"<D:href>/api/cloud-sync/roms/{rom.platform.fs_slug}/{rom.fs_name}</D:href>" in response.text

    def test_propfind_unknown_platform_is_not_found(self, client, admin_user: User):
        response = client.request(
            "PROPFIND", "/api/cloud-sync/roms/nope/", auth=ADMIN_AUTH
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_rom_file_redirects_to_rest_content_endpoint(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.get(
            f"/api/cloud-sync/roms/{rom.platform.fs_slug}/{rom.fs_name}",
            auth=ADMIN_AUTH,
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"] == f"/api/roms/{rom.id}/content/{rom.fs_name}"

    def test_get_unknown_rom_file_is_not_found(
        self, client, admin_user: User, rom: Rom
    ):
        response = client.get(
            f"/api/cloud-sync/roms/{rom.platform.fs_slug}/nope.zip",
            auth=ADMIN_AUTH,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_propfind_saves_lists_the_emulator_subfolder(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        response = client.request("PROPFIND", "/api/cloud-sync/saves/", auth=ADMIN_AUTH)

        assert response.status_code == 207
        assert "<D:href>/api/cloud-sync/saves/Snes9x/</D:href>" in response.text

    @mock.patch(
        "handler.cloud_sync_handler.asset_md5",
        new_callable=mock.AsyncMock,
        return_value="d41d8cd98f00b204e9800998ecf8427e",
    )
    def test_propfind_saves_subfolder_lists_the_file(
        self, _asset_md5: mock.AsyncMock, client, admin_user: User, synced_save: Save
    ):
        response = client.request(
            "PROPFIND", "/api/cloud-sync/saves/Snes9x/", auth=ADMIN_AUTH
        )

        assert response.status_code == 207
        assert "<D:href>/api/cloud-sync/saves/Snes9x/test_rom.srm</D:href>" in response.text
