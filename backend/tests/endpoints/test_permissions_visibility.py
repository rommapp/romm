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
from endpoints import roms as rom_endpoints
from endpoints.roms import walkthrough as walkthrough_endpoints
from handler.auth import oauth_handler
from handler.database import db_rom_handler, db_user_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_resource_handler
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
)
from models.rom import Rom, RomFile, RomFileCategory


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


def test_physical_game_create_on_hidden_platform_is_404_masked(
    client, editor_user, platform, monkeypatch
):
    # Editor holds library-wide roms write, so the coarse gate passes. The
    # platform hide must mask the write before it reaches any side effect.
    _hide(PermEntity.PLATFORMS, platform.id, editor_user.id)

    def _unreachable(*args, **kwargs):
        raise AssertionError("scanned a rom onto a hidden platform")

    monkeypatch.setattr(rom_endpoints, "scan_rom", _unreachable)

    resp = client.post(
        "/api/roms/physical",
        headers=_auth(editor_user),
        json={"platform_id": platform.id, "name": "Sonic"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert db_rom_handler.get_roms_scalar(platform_ids=[platform.id]) == []


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
        data={"patch_file_id": rom_file.id},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/screenshots", {"x-upload-filename": "shot.png"}),
        ("/soundtracks", {"x-upload-filename": "track.mp3"}),
        ("/manuals", {"x-upload-filename": "manual.pdf"}),
        ("/manuals/files", {"x-upload-filename": "manual.pdf"}),
        ("/manuals/redownload", {}),
        ("/walkthroughs/files", {"x-upload-filename": "guide.txt"}),
    ],
)
def test_hidden_rom_child_upload_routes_are_404_masked(
    client, editor_user, rom, path, headers
):
    # Editor holds library-wide roms write, so the coarse scope gate passes; the
    # child media routes must still mask the hidden rom instead of writing to it.
    _hide(PermEntity.ROMS, rom.id, editor_user.id)
    resp = client.post(
        f"/api/roms/{rom.id}{path}", headers={**_auth(editor_user), **headers}
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("/screenshots/{file_id}", RomFileCategory.SCREENSHOT),
        ("/soundtracks/{file_id}", RomFileCategory.SOUNDTRACK),
        ("/manuals/files/{file_id}", RomFileCategory.MANUAL),
        ("/walkthroughs/files/{file_id}", RomFileCategory.WALKTHROUGH),
    ],
)
def test_hidden_rom_child_delete_routes_are_404_masked(
    client, editor_user, rom, path, category
):
    # The child file must match the route's category, otherwise the route 404s
    # on the category check and the visibility gate is never exercised.
    child = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=f"child.{category}",
            file_path=f"{rom.fs_path}/{category}",
            file_size_bytes=10,
            category=category,
        )
    )
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    resp = client.delete(
        f"/api/roms/{rom.id}{path.format(file_id=child.id)}",
        headers=_auth(editor_user),
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    # The row must survive: masking is worthless if the sink already ran.
    assert db_rom_handler.get_rom_file_by_id(child.id) is not None


def test_hidden_rom_gamefaqs_walkthrough_is_404_masked(
    client, editor_user, rom, monkeypatch
):
    # The visibility gate must run before the outbound fetch, so a hidden rom
    # can't be used to make the server reach GameFAQs.
    def _unreachable(*_args, **_kwargs):
        raise AssertionError("fetched a guide for a hidden rom")

    monkeypatch.setattr(walkthrough_endpoints, "fetch_gamefaqs_guide", _unreachable)
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    resp = client.post(
        f"/api/roms/{rom.id}/walkthroughs/gamefaqs",
        headers=_auth(editor_user),
        json={"url": "https://gamefaqs.gamespot.com/snes/1234-game/faqs/5678"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_manual_delete_is_404_masked(client, editor_user, rom, monkeypatch):
    # Without a manual on disk the route 404s before the visibility gate, so
    # force the existence check to pass.
    monkeypatch.setattr(fs_resource_handler, "manual_exists", lambda _rom: True)
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    resp = client.delete(f"/api/roms/{rom.id}/manuals", headers=_auth(editor_user))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "path", ["/soundtracks/metadata", "/notes", "/notes/identifiers"]
)
def test_hidden_rom_child_read_routes_are_404_masked(client, viewer_user, rom, path):
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    resp = client.get(f"/api/roms/{rom.id}{path}", headers=_auth(viewer_user))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_hidden_rom_note_write_routes_are_404_masked(client, viewer_user, rom):
    # ROMS_USER_WRITE is self-service, so only the entity check can mask these.
    _hide(PermEntity.ROMS, rom.id, viewer_user.id)
    headers = _auth(viewer_user)

    create = client.post(
        f"/api/roms/{rom.id}/notes", headers=headers, json={"title": "x"}
    )
    assert create.status_code == status.HTTP_404_NOT_FOUND

    update = client.put(
        f"/api/roms/{rom.id}/notes/1", headers=headers, json={"title": "x"}
    )
    assert update.status_code == status.HTTP_404_NOT_FOUND

    delete = client.delete(f"/api/roms/{rom.id}/notes/1", headers=headers)
    assert delete.status_code == status.HTTP_404_NOT_FOUND


def test_note_on_hidden_rom_not_reachable_via_visible_rom_path(
    client, viewer_user, rom, platform
):
    # The path rom only authorizes itself: a note belonging to a hidden rom must
    # not be reachable by pairing its id with a visible rom in the path.
    hidden = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="hidden_rom",
            slug="hidden_rom_slug",
            fs_name="hidden_rom.zip",
            fs_name_no_tags="hidden_rom",
            fs_name_no_ext="hidden_rom",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    note = db_rom_handler.create_rom_note(
        rom_id=hidden.id, user_id=viewer_user.id, title="secret"
    )
    _hide(PermEntity.ROMS, hidden.id, viewer_user.id)
    headers = _auth(viewer_user)

    update = client.put(
        f"/api/roms/{rom.id}/notes/{note['id']}", headers=headers, json={"title": "x"}
    )
    assert update.status_code == status.HTTP_404_NOT_FOUND

    delete = client.delete(f"/api/roms/{rom.id}/notes/{note['id']}", headers=headers)
    assert delete.status_code == status.HTTP_404_NOT_FOUND

    surviving = db_rom_handler.get_rom_notes(rom_id=hidden.id, user_id=viewer_user.id)
    assert [n.title for n in surviving] == ["secret"]


def test_visible_rom_child_route_is_not_masked(client, viewer_user, rom):
    # Control: the same route reaches its handler when the rom isn't hidden.
    resp = client.get(f"/api/roms/{rom.id}/notes", headers=_auth(viewer_user))
    assert resp.status_code == status.HTTP_200_OK


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
