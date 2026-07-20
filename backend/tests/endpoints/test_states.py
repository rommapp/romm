from unittest import mock

from fastapi import status

from handler.database import db_screenshot_handler, db_state_handler
from handler.database.base_handler import sync_session
from models.assets import Screenshot, State
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


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
