from contextlib import contextmanager
from unittest import mock

import pytest
from fastapi import status

from handler.database import db_screenshot_handler, db_state_handler
from handler.database.base_handler import sync_session
from models.assets import Screenshot, State
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils import uploads


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
    "endpoints.states.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
)
@mock.patch("endpoints.states.fs_asset_handler.write_file", new_callable=mock.AsyncMock)
@mock.patch("endpoints.states.scan_state", new_callable=mock.AsyncMock)
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


@mock.patch("endpoints.states.scan_state")
@mock.patch("endpoints.states.fs_asset_handler.write_file")
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
