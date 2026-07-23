from io import BytesIO
from unittest import mock

from fastapi import status

from handler.database import db_screenshot_handler
from handler.database.base_handler import sync_session
from models.assets import Screenshot
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


# ---------- POST /api/screenshots ----------


@mock.patch(
    "endpoints.screenshots.fs_asset_handler.write_file", new_callable=mock.AsyncMock
)
@mock.patch("endpoints.screenshots.scan_screenshot", new_callable=mock.AsyncMock)
def test_upload_gallery_screenshot_sets_flags(
    mock_scan,
    _mock_write,
    client,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    mock_scan.return_value = Screenshot(
        file_name="shot1.png",
        file_name_no_tags="shot1",
        file_name_no_ext="shot1",
        file_extension="png",
        file_path=f"{platform.slug}/screenshots",
        file_size_bytes=100,
    )

    response = client.post(
        f"/api/screenshots?rom_id={rom.id}",
        files={"screenshotFile": ("shot1.png", BytesIO(b"img"), "image/png")},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_gallery"] is True
    assert data["is_public"] is False


@mock.patch(
    "endpoints.screenshots.fs_asset_handler.write_file", new_callable=mock.AsyncMock
)
@mock.patch("endpoints.screenshots.scan_screenshot", new_callable=mock.AsyncMock)
def test_upload_rejects_invalid_extension(
    _mock_scan,
    _mock_write,
    client,
    access_token: str,
    rom: Rom,
):
    response = client.post(
        f"/api/screenshots?rom_id={rom.id}",
        files={"screenshotFile": ("notes.txt", BytesIO(b"nope"), "text/plain")},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported image file type" in response.json()["detail"]


# ---------- PUT /api/screenshots/{id} (visibility) ----------


def test_update_visibility_owner(client, access_token: str, screenshot: Screenshot):
    response = client.put(
        f"/api/screenshots/{screenshot.id}",
        json={"is_public": True},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_public"] is True

    refreshed = db_screenshot_handler.get_screenshot_by_id(screenshot.id)
    assert refreshed is not None and refreshed.is_public is True


def test_update_visibility_other_user_returns_404(
    client,
    access_token: str,
    rom: Rom,
    platform: Platform,
    editor_user: User,
):
    others = db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=editor_user.id,
            file_name="other.png",
            file_name_no_tags="other",
            file_name_no_ext="other",
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=10,
        )
    )

    response = client.put(
        f"/api/screenshots/{others.id}",
        json={"is_public": True},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------- DELETE /api/screenshots/{id} ----------


@mock.patch(
    "endpoints.screenshots.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
)
def test_delete_screenshot_owner(
    _mock_remove,
    client,
    access_token: str,
    screenshot: Screenshot,
):
    response = client.delete(
        f"/api/screenshots/{screenshot.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert db_screenshot_handler.get_screenshot_by_id(screenshot.id) is None


@mock.patch(
    "endpoints.screenshots.fs_asset_handler.remove_file", new_callable=mock.AsyncMock
)
def test_delete_screenshot_other_user_returns_404(
    _mock_remove,
    client,
    access_token: str,
    rom: Rom,
    platform: Platform,
    editor_user: User,
):
    others = db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=editor_user.id,
            file_name="other.png",
            file_name_no_tags="other",
            file_name_no_ext="other",
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=10,
        )
    )

    response = client.delete(
        f"/api/screenshots/{others.id}",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert db_screenshot_handler.get_screenshot_by_id(others.id) is not None


# ---------- Gallery visibility query ----------


def _add_screenshot(rom, platform, user_id, name, *, is_gallery, is_public):
    return db_screenshot_handler.add_screenshot(
        Screenshot(
            rom_id=rom.id,
            user_id=user_id,
            file_name=f"{name}.png",
            file_name_no_tags=name,
            file_name_no_ext=name,
            file_extension="png",
            file_path=f"{platform.slug}/screenshots",
            file_size_bytes=10,
            is_gallery=is_gallery,
            is_public=is_public,
        )
    )


def test_gallery_query_excludes_thumbnails_and_others_private(
    rom: Rom,
    platform: Platform,
    admin_user: User,
    editor_user: User,
):
    # Own save/state thumbnail — not a gallery upload.
    _add_screenshot(
        rom, platform, admin_user.id, "thumb", is_gallery=False, is_public=False
    )
    # Own private gallery screenshot — visible to self.
    mine = _add_screenshot(
        rom, platform, admin_user.id, "mine", is_gallery=True, is_public=False
    )
    # Another user's public gallery screenshot — visible (community).
    others_public = _add_screenshot(
        rom, platform, editor_user.id, "pub", is_gallery=True, is_public=True
    )
    # Another user's private gallery screenshot — hidden.
    _add_screenshot(
        rom, platform, editor_user.id, "priv", is_gallery=True, is_public=False
    )

    visible = {
        s.id
        for s in db_screenshot_handler.get_rom_gallery_screenshots(
            rom_id=rom.id, user_id=admin_user.id
        )
    }

    assert mine.id in visible
    assert others_public.id in visible
    assert len(visible) == 2


# ---------- GET /api/screenshots/{id}/content ----------


@mock.patch("endpoints.screenshots.fs_asset_handler.validate_path")
def test_owner_downloads_own_screenshot(
    mock_validate_path,
    client,
    access_token: str,
    admin_user: User,
    rom: Rom,
    platform: Platform,
    tmp_path,
):
    screenshot = _add_screenshot(
        rom, platform, admin_user.id, "shot", is_gallery=True, is_public=False
    )
    test_file = tmp_path / "shot.png"
    test_file.write_bytes(b"SHOT_DATA")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/screenshots/{screenshot.id}/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"SHOT_DATA"


def test_other_user_cannot_download_private_screenshot(
    client,
    viewer_access_token: str,
    admin_user: User,
    rom: Rom,
    platform: Platform,
):
    screenshot = _add_screenshot(
        rom, platform, admin_user.id, "shot", is_gallery=True, is_public=False
    )
    response = client.get(
        f"/api/screenshots/{screenshot.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@mock.patch("endpoints.screenshots.fs_asset_handler.validate_path")
def test_other_user_downloads_public_screenshot(
    mock_validate_path,
    client,
    viewer_access_token: str,
    admin_user: User,
    rom: Rom,
    platform: Platform,
    tmp_path,
):
    screenshot = _add_screenshot(
        rom, platform, admin_user.id, "shot", is_gallery=True, is_public=True
    )
    test_file = tmp_path / "shot.png"
    test_file.write_bytes(b"SHARED_SHOT")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/screenshots/{screenshot.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"SHARED_SHOT"


def test_hidden_rom_masks_public_screenshot_download(
    client,
    viewer_access_token: str,
    viewer_user: User,
    admin_user: User,
    rom: Rom,
    platform: Platform,
):
    # A public screenshot on a ROM hidden from the caller must stay 404-masked;
    # sharing cannot override the hidden-resource boundary.
    screenshot = _add_screenshot(
        rom, platform, admin_user.id, "shot", is_gallery=True, is_public=True
    )
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)

    response = client.get(
        f"/api/screenshots/{screenshot.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_platform_masks_public_screenshot_download(
    client,
    viewer_access_token: str,
    viewer_user: User,
    admin_user: User,
    rom: Rom,
    platform: Platform,
):
    # Hiding the parent platform cascades to its screenshots as well.
    screenshot = _add_screenshot(
        rom, platform, admin_user.id, "shot", is_gallery=True, is_public=True
    )
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)

    response = client.get(
        f"/api/screenshots/{screenshot.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_screenshot_not_found(client, access_token: str):
    response = client.get("/api/screenshots/99999/content", headers=_auth(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND
