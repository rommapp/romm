"""Admin CRUD for groups, memberships, overrides and hidden entities, and the
end-to-end effect on a member's /permissions/me."""

from datetime import timedelta

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_user_handler
from handler.database.base_handler import sync_session
from models.permission import PermissionGroup


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _fresh_user_auth(user_id):
    # Mint a token from the user's CURRENT (post-change) projected scopes.
    user = db_user_handler.get_user(user_id)
    return _bearer(
        oauth_handler.create_access_token(
            data={
                "sub": user.username,
                "iss": "romm:oauth",
                "scopes": " ".join(user.oauth_scopes),
            },
            expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
        )
    )


def _me_actions(client, user_id):
    body = client.get("/api/permissions/me", headers=_fresh_user_auth(user_id)).json()
    return {g["action"] for g in body["grants"]}, body


def _cleanup():
    with sync_session.begin() as s:
        s.query(PermissionGroup).filter(PermissionGroup.is_system.is_(False)).delete(
            synchronize_session="evaluate"
        )


def test_non_admin_forbidden(client, viewer_access_token):
    h = _bearer(viewer_access_token)
    assert client.get("/api/permissions/groups", headers=h).status_code == 403
    assert client.get("/api/permissions/catalog", headers=h).status_code == 403
    assert (
        client.post(
            "/api/permissions/groups", headers=h, json={"name": "x"}
        ).status_code
        == 403
    )


def test_catalog_lists_vocabulary(client, access_token):
    body = client.get("/api/permissions/catalog", headers=_bearer(access_token)).json()
    assert "roms" in body["entities"] and "platforms" in body["entities"]
    assert set(body["actions"]) == {"read", "write", "delete"}


def test_group_create_assign_and_effective_permissions(
    client, access_token, viewer_user
):
    try:
        created = client.post(
            "/api/permissions/groups",
            headers=_bearer(access_token),
            json={
                "name": "Curators",
                "description": "roms + platform read",
                "grants": [
                    {"entity": "roms", "action": "read"},
                    {"entity": "roms", "action": "write"},
                    {"entity": "platforms", "action": "read"},
                ],
            },
        )
        assert created.status_code == 201
        group = created.json()
        assert group["member_count"] == 0
        assert {(g["entity"], g["action"]) for g in group["grants"]} == {
            ("roms", "read"),
            ("roms", "write"),
            ("platforms", "read"),
        }
        gid = group["id"]

        assigned = client.put(
            f"/api/permissions/users/{viewer_user.id}",
            headers=_bearer(access_token),
            json={"set_group": True, "permission_group_id": gid},
        )
        assert assigned.status_code == 200
        assert assigned.json()["permission_group_id"] == gid

        actions, _ = _me_actions(client, viewer_user.id)
        # Group grants -> these actions; nothing from the default viewer matrix.
        assert {"rom.view", "rom.upload", "platform.view"} <= actions
        assert "collection.create" not in actions  # group grants no collections
    finally:
        _cleanup()


def test_user_override_adds_capability(client, access_token, viewer_user):
    try:
        gid = client.post(
            "/api/permissions/groups",
            headers=_bearer(access_token),
            json={"name": "RO", "grants": [{"entity": "roms", "action": "read"}]},
        ).json()["id"]
        client.put(
            f"/api/permissions/users/{viewer_user.id}",
            headers=_bearer(access_token),
            json={
                "set_group": True,
                "permission_group_id": gid,
                "overrides": [{"entity": "roms", "action": "delete", "granted": True}],
            },
        )
        actions, _ = _me_actions(client, viewer_user.id)
        assert "rom.delete" in actions  # granted by override on top of read-only group
    finally:
        _cleanup()


def test_hide_entity_for_user(client, access_token, viewer_user):
    resp = client.post(
        "/api/permissions/hidden",
        headers=_bearer(access_token),
        json={"entity": "platforms", "entity_id": 11, "user_id": viewer_user.id},
    )
    assert resp.status_code == 200

    _, body = _me_actions(client, viewer_user.id)
    assert body["hidden"]["platforms"] == [11]

    # Idempotent + removable.
    client.post(
        "/api/permissions/hidden",
        headers=_bearer(access_token),
        json={"entity": "platforms", "entity_id": 11, "user_id": viewer_user.id},
    )
    removed = client.request(
        "DELETE",
        "/api/permissions/hidden",
        headers=_bearer(access_token),
        json={"entity": "platforms", "entity_id": 11, "user_id": viewer_user.id},
    )
    assert removed.status_code == 204
    _, body = _me_actions(client, viewer_user.id)
    assert body["hidden"]["platforms"] == []


def test_hidden_requires_exactly_one_principal(client, access_token):
    resp = client.post(
        "/api/permissions/hidden",
        headers=_bearer(access_token),
        json={"entity": "roms", "entity_id": 1, "user_id": 1, "group_id": 1},
    )
    assert resp.status_code == 400


def test_cannot_delete_default_group(client, access_token):
    groups = client.get("/api/permissions/groups", headers=_bearer(access_token)).json()
    default = next(g for g in groups if g["is_default"])
    resp = client.delete(
        f"/api/permissions/groups/{default['id']}", headers=_bearer(access_token)
    )
    assert resp.status_code == 400


def test_delete_group_falls_members_back(client, access_token, viewer_user):
    gid = client.post(
        "/api/permissions/groups",
        headers=_bearer(access_token),
        json={"name": "Temp", "grants": [{"entity": "roms", "action": "read"}]},
    ).json()["id"]
    client.put(
        f"/api/permissions/users/{viewer_user.id}",
        headers=_bearer(access_token),
        json={"set_group": True, "permission_group_id": gid},
    )

    resp = client.delete(
        f"/api/permissions/groups/{gid}", headers=_bearer(access_token)
    )
    assert resp.status_code == 200

    # FK SET NULL -> user falls back to the default (viewer) matrix.
    user = db_user_handler.get_user(viewer_user.id)
    assert user.permission_group_id is None
    actions, _ = _me_actions(client, viewer_user.id)
    assert "collection.create" in actions  # default viewer behaviour restored
