"""`/permissions/me` returns backend-enforced grants in the UI action vocabulary."""

from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity

VIEWER_ACTIONS = {
    "rom.view",
    "rom.play",
    "rom.download",
    "rom.favorite",
    "platform.view",
    "collection.view",
    "collection.create",
    "collection.edit",
    "collection.delete",
}


def _actions(payload):
    return {g["action"] for g in payload["grants"]}


def test_requires_auth(client):
    assert client.get("/api/permissions/me").status_code == 403


def test_admin_is_admin_and_all_actions(client, access_token):
    resp = client.get(
        "/api/permissions/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_admin"] is True
    # Admin unlocks the full vocabulary, incl. user.* and app.admin.
    assert {"user.delete", "app.admin", "rom.delete"} <= _actions(body)
    assert body["hidden"] == {"platforms": [], "roms": []}


def test_viewer_matches_read_only_action_set(client, viewer_access_token):
    body = client.get(
        "/api/permissions/me",
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    ).json()
    assert body["is_admin"] is False
    assert _actions(body) == VIEWER_ACTIONS


def test_editor_adds_write_actions(client, editor_access_token):
    body = client.get(
        "/api/permissions/me",
        headers={"Authorization": f"Bearer {editor_access_token}"},
    ).json()
    assert body["is_admin"] is False
    actions = _actions(body)
    assert VIEWER_ACTIONS <= actions
    # Editor gains library-wide write (and the backend-true delete/create it
    # always had, which the legacy role-map under-reported).
    assert {
        "rom.upload",
        "rom.edit",
        "rom.delete",
        "platform.edit",
        "platform.create",
        "platform.delete",
        "library.scan",
    } <= actions
    # Still no user management.
    assert not {a for a in actions if a.startswith("user.")}


def test_hidden_entities_reported(client, viewer_user, viewer_access_token):
    with sync_session.begin() as s:
        s.add(
            HiddenEntity(
                entity=PermEntity.PLATFORMS, entity_id=5, user_id=viewer_user.id
            )
        )
        s.add(
            HiddenEntity(entity=PermEntity.ROMS, entity_id=42, user_id=viewer_user.id)
        )

    body = client.get(
        "/api/permissions/me",
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    ).json()
    assert body["hidden"]["platforms"] == [5]
    assert body["hidden"]["roms"] == [42]


def test_grant_scopes_are_global(client, viewer_access_token):
    body = client.get(
        "/api/permissions/me",
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    ).json()
    assert all(g["scope"]["kind"] == "global" for g in body["grants"])
