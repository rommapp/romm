import os
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock

import pytest
from fastapi import status

from handler.database import (
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.database.base_handler import sync_session
from models.assets import (
    ASSET_LABEL_MAX_LENGTH,
    ASSET_LABELS_MAX,
    Save,
    Screenshot,
    State,
)
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils import uploads
from utils.validation import MAX_ROM_IDS_PER_QUERY


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


@mock.patch("endpoints.states.fs_asset_handler.validate_path")
def test_owner_downloads_own_state(
    mock_validate_path, client, access_token: str, state: State, tmp_path
):
    test_file = tmp_path / "test.state"
    test_file.write_bytes(b"STATE_DATA")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/states/{state.id}/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"STATE_DATA"


def test_other_user_cannot_download_private_state(
    client, viewer_access_token: str, state: State
):
    response = client.get(
        f"/api/states/{state.id}/content", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@mock.patch("endpoints.states.fs_asset_handler.validate_path")
def test_other_user_downloads_public_state(
    mock_validate_path, client, viewer_access_token: str, state: State, tmp_path
):
    db_state_handler.update_state(state.id, {"is_public": True})
    test_file = tmp_path / "test.state"
    test_file.write_bytes(b"SHARED_STATE")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/states/{state.id}/content", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"SHARED_STATE"


def test_hidden_rom_masks_public_state_download(
    client, viewer_access_token: str, viewer_user: User, state: State, rom: Rom
):
    # A public state on a ROM hidden from the caller must stay 404-masked;
    # sharing cannot override the hidden-resource boundary.
    db_state_handler.update_state(state.id, {"is_public": True})
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)

    response = client.get(
        f"/api/states/{state.id}/content", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_platform_masks_public_state_download(
    client,
    viewer_access_token: str,
    viewer_user: User,
    state: State,
    platform: Platform,
):
    # Hiding the parent platform cascades to its states as well.
    db_state_handler.update_state(state.id, {"is_public": True})
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)

    response = client.get(
        f"/api/states/{state.id}/content", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_state_not_found(client, access_token: str):
    response = client.get("/api/states/99999/content", headers=_auth(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_sharing_state_syncs_thumbnail_visibility(
    client,
    access_token: str,
    state: State,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    # Thumbnail whose filename stem matches the state (how State.screenshot links).
    thumb = db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_state.png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=1,
            is_public=False,
        )
    )

    response = client.put(
        f"/api/states/{state.id}/visibility",
        json={"is_public": True},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_public"] is True

    refreshed = db_screenshot_handler.get_screenshot_by_id(thumb.id)
    assert refreshed is not None and refreshed.is_public is True


@pytest.mark.parametrize(
    "files",
    [
        {"stateFile": ("game.state", b"x" * 64, "application/octet-stream")},
        {
            "stateFile": ("game.state", b"small", "application/octet-stream"),
            "screenshotFile": ("shot.png", b"x" * 64, "image/png"),
        },
    ],
    ids=["state-file", "screenshot-file"],
)
def test_add_state_rejects_oversized_uploads(
    client, access_token: str, rom: Rom, files: dict
):
    with mock.patch.object(uploads, "MAX_ASSET_UPLOAD_SIZE_BYTES", 32):
        response = client.post(
            f"/api/states?rom_id={rom.id}",
            files=files,
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE


@mock.patch(
    "handler.asset_store.fs_asset_handler.write_file", new_callable=mock.AsyncMock
)
@mock.patch("handler.asset_store.scan_state", new_callable=mock.AsyncMock)
def test_hidden_rom_masks_state_upload(
    _mock_scan,
    mock_write,
    client,
    viewer_access_token: str,
    viewer_user: User,
    rom: Rom,
):
    # Uploading onto a ROM hidden from the caller is 404-masked the same way
    # downloading from one is, and nothing reaches disk.
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)

    response = client.post(
        f"/api/states?rom_id={rom.id}",
        files={"stateFile": ("game.state", b"STATE!", "application/octet-stream")},
        headers=_auth(viewer_access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_write.assert_not_awaited()


@mock.patch(
    "handler.asset_store.fs_asset_handler.write_file", new_callable=mock.AsyncMock
)
@mock.patch("handler.asset_store.scan_state", new_callable=mock.AsyncMock)
def test_hidden_platform_masks_state_upload(
    _mock_scan,
    mock_write,
    client,
    viewer_access_token: str,
    viewer_user: User,
    rom: Rom,
    platform: Platform,
):
    # Hiding the parent platform cascades to uploads against its ROMs.
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)

    response = client.post(
        f"/api/states?rom_id={rom.id}",
        files={"stateFile": ("game.state", b"STATE!", "application/octet-stream")},
        headers=_auth(viewer_access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_write.assert_not_awaited()


@mock.patch(
    "handler.asset_store.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
)
@mock.patch(
    "handler.asset_store.fs_asset_handler.write_file", new_callable=mock.AsyncMock
)
@mock.patch("handler.asset_store.scan_state", new_callable=mock.AsyncMock)
def test_reupload_updates_file_path_and_emulator(
    mock_scan,
    _mock_write,
    mock_remove,
    client,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    """Re-uploading the same filename under a different emulator must move the
    row's file_path/emulator to where the new bytes landed, so the row never
    serves the previous emulator's state."""
    existing = db_state_handler.add_state(
        State(
            file_name="game.state",
            file_name_no_tags="game",
            file_name_no_ext="game",
            file_extension="state",
            file_path=f"{platform.slug}/states/old_emu",
            file_size_bytes=100,
            emulator="old_emu",
            rom_id=rom.id,
            user_id=admin_user.id,
        )
    )

    new_path = f"{platform.slug}/states/new_emu"
    mock_scan.return_value = State(
        file_name="game.state",
        file_name_no_tags="game",
        file_name_no_ext="game",
        file_extension="state",
        file_path=new_path,
        file_size_bytes=200,
        rom_id=rom.id,
        user_id=admin_user.id,
    )

    response = client.post(
        f"/api/states?rom_id={rom.id}&emulator=new_emu",
        files={"stateFile": ("game.state", b"NEW STATE", "application/octet-stream")},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK

    updated = db_state_handler.get_state(user_id=admin_user.id, id=existing.id)
    assert updated is not None
    assert updated.file_path == new_path
    assert updated.emulator == "new_emu"
    assert updated.file_size_bytes == 200
    # full_path now points at the freshly written bytes, not the stale ones.
    assert updated.full_path == f"{new_path}/game.state"
    # The orphaned bytes at the old location are cleaned up.
    mock_remove.assert_awaited_once_with(f"{platform.slug}/states/old_emu/game.state")


@contextmanager
def _kiosk_mode():
    """Both call sites of the setting, as a real KIOSK_MODE=true deploy sees it."""
    with (
        mock.patch("handler.auth.hybrid_auth.KIOSK_MODE", True),
        mock.patch("handler.auth.permissions.KIOSK_MODE", True),
    ):
        yield


@mock.patch("handler.asset_store.scan_state")
@mock.patch("handler.asset_store.fs_asset_handler.write_file")
def test_kiosk_mode_lets_logged_in_user_upload_state(
    mock_write_file,
    mock_scan_state,
    client,
    viewer_access_token: str,
    rom: Rom,
    platform: Platform,
):
    mock_scan_state.return_value = State(
        file_name="game.state",
        file_name_no_tags="game",
        file_name_no_ext="game",
        file_extension="state",
        file_path=f"{platform.slug}/states",
        file_size_bytes=6.0,
    )

    with _kiosk_mode():
        response = client.post(
            f"/api/states?rom_id={rom.id}",
            files={"stateFile": ("game.state", b"STATE!", "application/octet-stream")},
            headers=_auth(viewer_access_token),
        )

    assert response.status_code == status.HTTP_200_OK
    assert mock_write_file.await_count == 1
    assert response.json()["file_name"] == "game.state"


def test_kiosk_mode_anonymous_visitor_cannot_upload_state(client, rom: Rom):
    with _kiosk_mode():
        response = client.post(
            f"/api/states?rom_id={rom.id}",
            files={"stateFile": ("game.state", b"STATE!", "application/octet-stream")},
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRomIdsScope:
    def test_scopes_results_to_listed_roms(
        self, client, access_token: str, rom: Rom, state: State, second_state: State
    ):
        response = client.get(
            f"/api/states?rom_ids={rom.id}", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.json()] == [state.id]

    def test_accepts_repeated_ids(
        self,
        client,
        access_token: str,
        rom: Rom,
        second_rom: Rom,
        state: State,
        second_state: State,
    ):
        response = client.get(
            f"/api/states?rom_ids={rom.id}&rom_ids={second_rom.id}",
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert {item["id"] for item in response.json()} == {state.id, second_state.id}

    def test_tolerates_duplicates(
        self, client, access_token: str, rom: Rom, state: State
    ):
        response = client.get(
            f"/api/states?rom_ids={rom.id}&rom_ids={rom.id}",
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.json()] == [state.id]

    def test_omitted_returns_all_states(
        self, client, access_token: str, state: State, second_state: State
    ):
        response = client.get("/api/states", headers=_auth(access_token))

        assert response.status_code == status.HTTP_200_OK
        assert {item["id"] for item in response.json()} == {state.id, second_state.id}

    def test_narrows_to_the_intersection_with_rom_id(
        self,
        client,
        access_token: str,
        rom: Rom,
        second_rom: Rom,
        state: State,
        second_state: State,
    ):
        response = client.get(
            f"/api/states?rom_id={rom.id}&rom_ids={second_rom.id}",
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_rejects_non_integer_ids(self, client, access_token: str):
        response = client.get(
            "/api/states?rom_ids=1&rom_ids=abc", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_non_positive_ids(self, client, access_token: str):
        response = client.get(
            "/api/states?rom_ids=1&rom_ids=0", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_scope_over_the_limit(self, client, access_token: str):
        rom_ids = "&".join(f"rom_ids={i}" for i in range(1, MAX_ROM_IDS_PER_QUERY + 2))

        response = client.get(f"/api/states?{rom_ids}", headers=_auth(access_token))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@mock.patch(
    "handler.asset_store.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
)
def test_delete_state_removes_file_and_screenshot(
    mock_remove,
    client,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
    state: State,
):
    db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_state.png",
            file_name_no_tags="test_state",
            file_name_no_ext="test_state",
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=3,
        )
    )

    response = client.post(
        "/api/states/delete",
        json={"states": [state.id]},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_state_handler.get_state(user_id=admin_user.id, id=state.id) is None
    assert (
        db_screenshot_handler.get_screenshot(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_state.state",
            file_name_no_ext="test_state",
        )
        is None
    )
    assert mock_remove.call_count == 2


class TestStateFavoritesAndLabels:
    """Owner-only annotations on a state: the star and the free-text labels."""

    def test_starring_and_unstarring_a_state_persists(
        self, client, access_token: str, state: State
    ):
        response = client.put(
            f"/api/states/{state.id}/favorite",
            json={"is_favorite": True},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] is True

        response = client.put(
            f"/api/states/{state.id}/favorite",
            json={"is_favorite": False},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] is False

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.is_favorite is False

    def test_setting_state_labels_persists(
        self, client, access_token: str, state: State
    ):
        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["100% run", "before the boss"]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labels"] == ["100% run", "before the boss"]

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None
        assert refreshed.labels == ["100% run", "before the boss"]

    def test_setting_state_labels_replaces_the_previous_set(
        self, client, access_token: str, state: State
    ):
        client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["100% run", "seed 42"]},
            headers=_auth(access_token),
        )

        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["speedrun"]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labels"] == ["speedrun"]

        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": []},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labels"] == []

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == []

    def test_state_labels_are_trimmed_and_blanks_dropped(
        self, client, access_token: str, state: State
    ):
        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["  100% run  ", "   ", "", "seed 42"]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labels"] == ["100% run", "seed 42"]

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == ["100% run", "seed 42"]

    def test_state_labels_are_deduplicated_case_insensitively(
        self, client, access_token: str, state: State
    ):
        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["Run", "run", "RUN", "Seed"]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_200_OK
        # The first spelling wins, and the order the client sent survives.
        assert response.json()["labels"] == ["Run", "Seed"]

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == ["Run", "Seed"]

    def test_overlong_state_label_is_rejected(
        self, client, access_token: str, state: State
    ):
        client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["seed 42"]},
            headers=_auth(access_token),
        )

        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["ok", "x" * (ASSET_LABEL_MAX_LENGTH + 1)]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # The request is rejected whole, so not even the valid label lands.
        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == ["seed 42"]

    def test_too_many_state_labels_are_rejected(
        self, client, access_token: str, state: State
    ):
        client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["seed 42"]},
            headers=_auth(access_token),
        )

        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": [f"run {i}" for i in range(ASSET_LABELS_MAX + 1)]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == ["seed 42"]

    def test_annotating_a_state_leaves_updated_at_untouched(
        self, client, access_token: str, state: State
    ):
        # Backdate the row: the column has second precision, so a stray touch
        # would otherwise be invisible within the same second.
        db_state_handler.update_state(
            state.id, {"updated_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}
        )
        before = db_state_handler.get_state_by_id(state.id)
        assert before is not None
        stamp = before.updated_at

        client.put(
            f"/api/states/{state.id}/favorite",
            json={"is_favorite": True},
            headers=_auth(access_token),
        )
        client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["seed 42"]},
            headers=_auth(access_token),
        )
        client.put(
            f"/api/states/{state.id}/visibility",
            json={"is_public": True},
            headers=_auth(access_token),
        )

        # Annotating is not a write to the state's bytes, and the lists order
        # on `updated_at`.
        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None
        assert refreshed.updated_at == stamp
        assert refreshed.is_favorite is True
        assert refreshed.labels == ["seed 42"]
        assert refreshed.is_public is True

    def test_non_owner_cannot_star_a_state(
        self, client, viewer_access_token: str, state: State
    ):
        response = client.put(
            f"/api/states/{state.id}/favorite",
            json={"is_favorite": True},
            headers=_auth(viewer_access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.is_favorite is False

    def test_non_owner_cannot_label_a_state(
        self, client, access_token: str, viewer_access_token: str, state: State
    ):
        client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["mine"]},
            headers=_auth(access_token),
        )

        response = client.put(
            f"/api/states/{state.id}/labels",
            json={"labels": ["not mine"]},
            headers=_auth(viewer_access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.labels == ["mine"]

    def test_starring_a_missing_state_returns_not_found(
        self, client, access_token: str
    ):
        response = client.put(
            "/api/states/99999/favorite",
            json={"is_favorite": True},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_labelling_a_missing_state_returns_not_found(
        self, client, access_token: str
    ):
        response = client.put(
            "/api/states/99999/labels",
            json={"labels": ["ghost"]},
            headers=_auth(access_token),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestStateRename:
    """Renaming a state moves its file and keeps its screenshot bound."""

    @pytest.fixture
    def state_file(self, _isolated_assets_dir, state: State):
        path = _isolated_assets_dir / state.full_path
        path.parent.mkdir(parents=True)
        path.write_bytes(b"STATE_DATA")
        return path

    @pytest.fixture
    def thumbnail(
        self, _isolated_assets_dir, rom: Rom, platform: Platform, admin_user: User
    ):
        screenshot = db_screenshot_handler.add_screenshot(
            Screenshot(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_state.png",
                file_path=f"{platform.slug}/screenshots",
                file_size_bytes=3,
            )
        )
        path = _isolated_assets_dir / screenshot.file_path / screenshot.file_name
        path.parent.mkdir(parents=True)
        path.write_bytes(b"PNG")
        return screenshot

    def _rename(self, client, token: str, state_id: int, file_name: str):
        return client.put(
            f"/api/states/{state_id}/file-name",
            json={"file_name": file_name},
            headers=_auth(token),
        )

    def test_renaming_moves_the_file_and_its_screenshot(
        self, client, access_token: str, state: State, state_file, thumbnail
    ):
        response = self._rename(client, access_token, state.id, "Before boss.state")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["file_name"] == "Before boss.state"
        assert body["file_name_no_ext"] == "Before boss"
        assert body["file_extension"] == "state"
        assert body["screenshot"]["file_name"] == "Before boss.png"

        assert not state_file.exists()
        assert (state_file.parent / "Before boss.state").read_bytes() == b"STATE_DATA"
        screenshots_dir = state_file.parents[2] / "screenshots"
        assert not (screenshots_dir / "test_state.png").exists()
        assert (screenshots_dir / "Before boss.png").read_bytes() == b"PNG"

        renamed = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert renamed is not None and renamed.file_name_no_ext == "Before boss"

    def test_renaming_leaves_updated_at_untouched(
        self, client, access_token: str, state: State, state_file
    ):
        db_state_handler.update_state(
            state.id, {"updated_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}
        )
        before = db_state_handler.get_state_by_id(state.id)
        assert before is not None

        response = self._rename(client, access_token, state.id, "renamed.state")
        assert response.status_code == status.HTTP_200_OK

        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None
        assert refreshed.updated_at == before.updated_at

    def test_name_is_sanitized(
        self, client, access_token: str, state: State, state_file
    ):
        response = self._rename(
            client, access_token, state.id, "../boss: phase 2.state"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["file_name"] == "boss- phase 2.state"
        assert (state_file.parent / "boss- phase 2.state").exists()

    def test_name_another_state_holds_is_a_conflict(
        self,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        state: State,
        state_file,
    ):
        # A different emulator's folder, so only the row makes the name taken.
        db_state_handler.add_state(
            State(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="Taken.state",
                emulator="other_emulator",
                file_path=f"{platform.slug}/states/other_emulator",
                file_size_bytes=2,
            )
        )

        response = self._rename(client, access_token, state.id, "taken.state")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert state_file.exists()
        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.file_name == "test_state.state"

    def test_name_binding_another_screenshot_is_a_conflict(
        self,
        client,
        access_token: str,
        state: State,
        state_file,
        screenshot: Screenshot,
    ):
        # Taking the stem would show that screenshot, and delete it with the state.
        response = self._rename(client, access_token, state.id, "test_screenshot.state")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert state_file.exists()

    def test_gallery_screenshot_sharing_the_stem_stays_put(
        self, client, access_token: str, state: State, state_file, thumbnail
    ):
        db_screenshot_handler.update_screenshot(thumbnail.id, {"is_gallery": True})

        response = self._rename(client, access_token, state.id, "renamed.state")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["screenshot"] is None
        gallery = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert gallery is not None and gallery.file_name == "test_state.png"

    def test_file_missing_from_disk_returns_not_found(
        self, client, access_token: str, state: State, _isolated_assets_dir
    ):
        response = self._rename(client, access_token, state.id, "renamed.state")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        refreshed = db_state_handler.get_state_by_id(state.id)
        assert refreshed is not None and refreshed.file_name == "test_state.state"

    def test_name_with_nothing_before_the_extension_is_rejected(
        self, client, access_token: str, state: State, state_file, thumbnail
    ):
        response = self._rename(client, access_token, state.id, ".state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert state_file.exists()
        kept = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert kept is not None and kept.file_name == "test_state.png"

    def test_blank_name_is_rejected(
        self, client, access_token: str, state: State, state_file
    ):
        response = self._rename(client, access_token, state.id, "   ")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert state_file.exists()

    def test_a_thumbnail_shared_with_a_save_is_copied_not_moved(
        self,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        state: State,
        state_file,
        thumbnail,
    ):
        # Same stem as the state, so both resolve `test_state.png`.
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_state.srm",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=1,
            )
        )

        response = self._rename(client, access_token, state.id, "renamed.state")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["screenshot"]["file_name"] == "renamed.png"
        kept = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert kept is not None and kept.file_name == "test_state.png"
        screenshots_dir = state_file.parents[2] / "screenshots"
        assert (screenshots_dir / "test_state.png").read_bytes() == b"PNG"
        assert (screenshots_dir / "renamed.png").read_bytes() == b"PNG"

    def test_a_shared_thumbnail_stays_when_the_stem_does(
        self,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        state: State,
        state_file,
        thumbnail,
    ):
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_state.srm",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=1,
            )
        )

        response = self._rename(client, access_token, state.id, "test_state.st2")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["screenshot"]["id"] == thumbnail.id
        screenshots_dir = state_file.parents[2] / "screenshots"
        assert sorted(p.name for p in screenshots_dir.iterdir()) == ["test_state.png"]

    def test_a_case_only_rename_copies_a_shared_thumbnail(
        self,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        state: State,
        state_file,
        thumbnail,
    ):
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_state.srm",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=1,
            )
        )

        response = self._rename(client, access_token, state.id, "Test_state.state")

        # Lookups compare names exactly on PostgreSQL, so the new case needs
        # its own copy for the state to keep a preview there.
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["screenshot"]["file_name"] in (
            "Test_state.png",
            "test_state.png",
        )
        screenshots_dir = state_file.parents[2] / "screenshots"
        assert (screenshots_dir / "Test_state.png").read_bytes() == b"PNG"
        kept = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert kept is not None and kept.file_name == "test_state.png"

    def test_a_case_only_rename_keeps_a_shared_thumbnail_the_filesystem_folds(
        self,
        client,
        access_token: str,
        rom: Rom,
        platform: Platform,
        admin_user: User,
        state: State,
        state_file,
        thumbnail,
    ):
        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name="test_state.srm",
                file_path=f"{platform.slug}/saves",
                file_size_bytes=1,
            )
        )
        screenshots_dir = state_file.parents[2] / "screenshots"
        # A second link stands in for a case-insensitive filesystem's alias.
        os.link(screenshots_dir / "test_state.png", screenshots_dir / "Test_state.png")

        with mock.patch(
            "handler.asset_store.db_screenshot_handler.add_screenshot"
        ) as add:
            response = self._rename(client, access_token, state.id, "Test_state.state")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["file_name"] == "Test_state.state"
        add.assert_not_called()
        kept = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert kept is not None and kept.file_name == "test_state.png"

    def test_a_failed_row_update_puts_the_files_back(
        self, client, access_token: str, state: State, state_file, thumbnail
    ):
        with (
            mock.patch(
                "handler.asset_store.db_state_handler.update_state",
                side_effect=RuntimeError("database gone"),
            ),
            pytest.raises(RuntimeError),
        ):
            self._rename(client, access_token, state.id, "renamed.state")

        assert state_file.read_bytes() == b"STATE_DATA"
        assert not (state_file.parent / "renamed.state").exists()
        screenshots_dir = state_file.parents[2] / "screenshots"
        assert (screenshots_dir / "test_state.png").exists()
        assert not (screenshots_dir / "renamed.png").exists()
        # The thumbnail's row change rolled back with the state's.
        kept = db_screenshot_handler.get_screenshot_by_id(thumbnail.id)
        assert kept is not None and kept.file_name == "test_state.png"

    def test_non_owner_cannot_rename_a_state(
        self, client, viewer_access_token: str, state: State, state_file
    ):
        db_state_handler.update_state(state.id, {"is_public": True})

        response = self._rename(client, viewer_access_token, state.id, "mine.state")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert state_file.exists()
