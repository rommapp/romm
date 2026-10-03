"""Age limits end to end: the admin API that sets them and the routes they hide ROMs from."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_esrb_rated_rom, make_rom

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.base_handler import oauth_handler
from handler.auth.permissions import resolve_permissions
from handler.database import db_permission_handler, db_user_handler
from handler.database.base_handler import sync_session
from models.permission import PermissionGroup
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _auth(user: User) -> dict[str, str]:
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


@pytest.fixture(autouse=True)
def _cleanup_non_system_groups():
    yield
    with sync_session.begin() as s:
        s.query(PermissionGroup).filter(PermissionGroup.system_key.is_(None)).delete(
            synchronize_session="evaluate"
        )


def _make_kids_group(
    client: TestClient, access_token: str, **fields: Any
) -> dict[str, Any]:
    created = client.post(
        "/api/permissions/groups",
        headers=_bearer(access_token),
        json={
            "name": "Kids",
            "grants": [
                {"entity": "roms", "action": "read"},
                {"entity": "platforms", "action": "read"},
            ],
            **fields,
        },
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    group: dict[str, Any] = created.json()
    return group


def _join(client: TestClient, access_token: str, user: User, group_id: int) -> None:
    resp = client.put(
        f"/api/permissions/users/{user.id}",
        headers=_bearer(access_token),
        json={"set_group": True, "permission_group_id": group_id},
    )
    assert resp.status_code == status.HTTP_200_OK


def _listed_ids(client: TestClient, user: User) -> list[int]:
    listing = client.get("/api/roms", headers=_auth(user))
    assert listing.status_code == status.HTTP_200_OK
    ids: list[int] = listing.json()["rom_id_index"]
    return ids


class TestAdminApi:
    def test_a_group_carries_its_age_settings(self, client, access_token, rom: Rom):
        group = _make_kids_group(
            client,
            access_token,
            age_limit=12,
            hide_unrated_roms=True,
            age_exempt_rom_ids=[rom.id, 999_999],
        )

        assert group["age_limit"] == 12
        assert group["hide_unrated_roms"] is True
        # An id without a ROM is dropped rather than stored.
        assert group["age_exempt_rom_ids"] == [rom.id]

    def test_a_group_update_sets_clears_and_leaves_the_limit(
        self, client, access_token
    ):
        gid = _make_kids_group(client, access_token, age_limit=12)["id"]
        url = f"/api/permissions/groups/{gid}"

        renamed = client.put(url, headers=_bearer(access_token), json={"name": "Teens"})
        assert renamed.json()["age_limit"] == 12

        raised = client.put(
            url,
            headers=_bearer(access_token),
            json={"set_age_limit": True, "age_limit": 16},
        )
        assert raised.json()["age_limit"] == 16

        cleared = client.put(
            url,
            headers=_bearer(access_token),
            json={"set_age_limit": True, "age_limit": None},
        )
        assert cleared.json()["age_limit"] is None

    def test_an_age_limit_outside_the_range_is_rejected(self, client, access_token):
        resp = client.post(
            "/api/permissions/groups",
            headers=_bearer(access_token),
            json={"name": "Kids", "age_limit": 99},
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_a_user_carries_its_own_age_settings(
        self, client, access_token, viewer_user: User, rom: Rom
    ):
        url = f"/api/permissions/users/{viewer_user.id}"
        updated = client.put(
            url,
            headers=_bearer(access_token),
            json={
                "set_age_settings": True,
                "age_limit": 10,
                "hide_unrated_roms": False,
                "age_exempt_rom_ids": [rom.id],
            },
        )
        assert updated.status_code == status.HTTP_200_OK

        body = client.get(url, headers=_bearer(access_token)).json()
        assert body["age_limit"] == 10
        assert body["hide_unrated_roms"] is False
        assert body["age_exempt_rom_ids"] == [rom.id]

        # Without the flag the settings are left alone.
        client.put(url, headers=_bearer(access_token), json={"age_limit": None})
        assert client.get(url, headers=_bearer(access_token)).json()["age_limit"] == 10


class TestResolution:
    def test_a_user_setting_replaces_the_groups(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        group_exempt = make_esrb_rated_rom(platform, "Group exempt", "M")
        user_exempt = make_esrb_rated_rom(platform, "User exempt", "M")
        gid = _make_kids_group(
            client,
            access_token,
            age_limit=12,
            hide_unrated_roms=True,
            age_exempt_rom_ids=[group_exempt.id],
        )["id"]
        _join(client, access_token, viewer_user, gid)
        client.put(
            f"/api/permissions/users/{viewer_user.id}",
            headers=_bearer(access_token),
            json={
                "set_age_settings": True,
                "age_limit": 16,
                "age_exempt_rom_ids": [user_exempt.id],
            },
        )

        user = db_user_handler.get_user(viewer_user.id)
        assert user is not None
        perms = resolve_permissions(user)

        assert perms.age_limit == 16
        # Not overridden, so inherited from the group.
        assert perms.hide_unrated_roms is True
        assert perms.age_exempt_rom_ids == {group_exempt.id, user_exempt.id}

    def test_admins_ignore_age_limits(self, admin_user: User):
        db_user_handler.update_user(admin_user.id, {"age_limit": 3})
        user = db_user_handler.get_user(admin_user.id)
        assert user is not None

        assert resolve_permissions(user).rom_visibility.is_unrestricted


class TestEnforcement:
    def test_a_limited_user_cannot_list_or_open_roms_above_it(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        mature = make_esrb_rated_rom(platform, "Mature", "M")
        everyone = make_esrb_rated_rom(platform, "Everyone", "E")
        gid = _make_kids_group(client, access_token, age_limit=12)["id"]
        _join(client, access_token, viewer_user, gid)

        ids = _listed_ids(client, viewer_user)
        assert everyone.id in ids
        assert mature.id not in ids

        detail = client.get(f"/api/roms/{mature.id}", headers=_auth(viewer_user))
        assert detail.status_code == status.HTTP_404_NOT_FOUND

    def test_an_exemption_lets_a_rom_through(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        mature = make_esrb_rated_rom(platform, "Mature", "M")
        gid = _make_kids_group(
            client, access_token, age_limit=12, age_exempt_rom_ids=[mature.id]
        )["id"]
        _join(client, access_token, viewer_user, gid)

        assert mature.id in _listed_ids(client, viewer_user)
        detail = client.get(f"/api/roms/{mature.id}", headers=_auth(viewer_user))
        assert detail.status_code == status.HTTP_200_OK

    def test_a_limit_change_reaches_the_cached_gallery(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        mature = make_esrb_rated_rom(platform, "Mature", "M")
        gid = _make_kids_group(client, access_token)["id"]
        _join(client, access_token, viewer_user, gid)
        # The unscoped listing caches the user's id index.
        assert mature.id in _listed_ids(client, viewer_user)

        client.put(
            f"/api/permissions/groups/{gid}",
            headers=_bearer(access_token),
            json={"set_age_limit": True, "age_limit": 12},
        )

        assert mature.id not in _listed_ids(client, viewer_user)

    def test_a_new_default_group_reaches_the_cached_gallery(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        mature = make_esrb_rated_rom(platform, "Mature", "M")
        previous_default = db_permission_handler.get_default_group_id()
        assert previous_default is not None
        client.put(
            f"/api/permissions/users/{viewer_user.id}",
            headers=_bearer(access_token),
            json={"set_group": True, "permission_group_id": None},
        )
        assert mature.id in _listed_ids(client, viewer_user)

        try:
            _make_kids_group(client, access_token, is_default=True, age_limit=12)

            assert mature.id not in _listed_ids(client, viewer_user)
        finally:
            db_permission_handler.update_group(previous_default, is_default=True)

    def test_hide_unrated_hides_roms_without_a_rating(
        self, client, access_token, viewer_user: User, platform: Platform
    ):
        unrated = make_rom(platform, "Unrated")
        rated = make_esrb_rated_rom(platform, "Rated", "E")
        gid = _make_kids_group(client, access_token, hide_unrated_roms=True)["id"]
        _join(client, access_token, viewer_user, gid)

        ids = _listed_ids(client, viewer_user)
        assert rated.id in ids
        assert unrated.id not in ids
