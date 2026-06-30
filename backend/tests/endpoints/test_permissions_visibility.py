"""End-to-end checks for admin-driven visibility (hiding) and delete enforcement.

Proves the fine permission layer is actually wired into the endpoints: hidden
platforms/roms disappear from lists and 404 on detail, the platform hide cascades
to its roms, admins are unaffected, and delete requires a delete grant even when
the coarse write scope is present.
"""

from datetime import timedelta

import pytest
from fastapi import status

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_user_handler
from handler.database.base_handler import sync_session
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
)


def _auth(user):
    # Re-reads the user's current (projected) scopes each call.
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return {"Authorization": f"Bearer {token}"}


def _hide(entity, entity_id, user_id):
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


def _make_group(name, grants):
    with sync_session.begin() as s:
        group = PermissionGroup(name=name, is_system=False)
        s.add(group)
        s.flush()
        gid = group.id
        for entity, action, own_only in grants:
            s.add(
                PermissionGroupGrant(
                    group_id=gid, entity=entity, action=action, own_only=own_only
                )
            )
    return gid


@pytest.fixture(autouse=True)
def _cleanup_non_system_groups():
    # HiddenEntity user rows cascade when clear_database deletes users; only the
    # non-system groups created here need explicit cleanup.
    yield
    with sync_session.begin() as s:
        s.query(PermissionGroup).filter(PermissionGroup.is_system.is_(False)).delete(
            synchronize_session="evaluate"
        )


def test_hidden_platform_excluded_from_list_but_visible_to_admin(
    client, viewer_user, admin_user, platform
):
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)

    viewer_ids = [
        p["id"] for p in client.get("/api/platforms", headers=_auth(viewer_user)).json()
    ]
    assert platform.id not in viewer_ids

    admin_ids = [
        p["id"] for p in client.get("/api/platforms", headers=_auth(admin_user)).json()
    ]
    assert platform.id in admin_ids


def test_hidden_platform_detail_is_404_masked(client, viewer_user, platform):
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    resp = client.get(f"/api/platforms/{platform.id}", headers=_auth(viewer_user))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_excluded_and_detail_404(client, viewer_user, rom):
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)

    listing = client.get("/api/roms", headers=_auth(viewer_user)).json()
    assert rom.id not in listing["rom_id_index"]

    detail = client.get(f"/api/roms/{rom.id}", headers=_auth(viewer_user))
    assert detail.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_platform_cascades_to_its_roms(client, viewer_user, rom, platform):
    _hide(PermEntity.PLATFORMS, platform.id, viewer_user.id)
    listing = client.get("/api/roms", headers=_auth(viewer_user)).json()
    assert rom.id not in listing["rom_id_index"]


def test_hidden_rom_cannot_be_downloaded_by_id(client, viewer_user, rom):
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    # Zip download of a hidden rom is masked as not-found.
    zip_resp = client.get(
        f"/api/roms/download?rom_ids={rom.id}", headers=_auth(viewer_user)
    )
    assert zip_resp.status_code == status.HTTP_404_NOT_FOUND
    # Direct content stream is masked too (before any file lookup).
    content_resp = client.get(
        f"/api/roms/{rom.id}/content/whatever", headers=_auth(viewer_user)
    )
    assert content_resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_update_is_404_masked(client, editor_user, rom):
    # Editor holds library-wide roms write (passes the coarse gate), so the
    # hidden rom must be 404-masked instead of being editable.
    _hide(PermEntity.ROMS, rom.id, editor_user.id)
    resp = client.put(
        f"/api/roms/{rom.id}", headers=_auth(editor_user), data={"name": "x"}
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_props_update_is_404_masked(client, viewer_user, rom):
    # ROMS_USER_WRITE is a self-service scope every user holds, so the coarse
    # gate passes; the hidden rom must still be masked, not confirmed.
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    resp = client.put(
        f"/api/roms/{rom.id}/props", headers=_auth(viewer_user), json={"rating": 5}
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_patch_is_404_masked(client, viewer_user, rom, rom_file):
    # patch_rom streams file bytes back; a hidden rom's bytes must not leak.
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    resp = client.post(
        f"/api/roms/{rom_file.id}/patch",
        headers=_auth(viewer_user),
        json={"patch_file_id": rom_file.id},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_requires_delete_grant_even_with_write_scope(
    client, viewer_user, platform
):
    # Group can read+write platforms but NOT delete them.
    gid = _make_group(
        "platform-writers",
        [
            (PermEntity.PLATFORMS, PermAction.READ, False),
            (PermEntity.PLATFORMS, PermAction.WRITE, False),
        ],
    )
    db_user_handler.update_user(viewer_user.id, {"permission_group_id": gid})
    user = db_user_handler.get_user(viewer_user.id)

    # Coarse PLATFORMS_WRITE is present (projected from the write grant), so the
    # request passes the scope gate and is rejected by the fine delete check.
    assert "platforms.write" in {s.value for s in user.oauth_scopes}
    resp = client.delete(f"/api/platforms/{platform.id}", headers=_auth(user))
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_delete_platform(client, admin_user, platform):
    resp = client.delete(f"/api/platforms/{platform.id}", headers=_auth(admin_user))
    assert resp.status_code == status.HTTP_200_OK
