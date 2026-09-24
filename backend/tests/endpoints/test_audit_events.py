from datetime import datetime, timedelta, timezone

from fastapi import status

from handler.auth import oauth_handler
from handler.database import db_audit_event_handler, db_user_handler
from models.audit_event import AuditAction, AuditActorKind, AuditEvent
from models.user import User


def _add(
    actor: User | None,
    action: AuditAction = AuditAction.ROM_DOWNLOAD,
    minutes_ago: int = 0,
    **overrides,
) -> AuditEvent:
    fields = {
        "occurred_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        "actor_kind": AuditActorKind.USER if actor else AuditActorKind.SYSTEM,
        "actor_id": actor.id if actor else None,
        "actor_name": actor.username if actor else None,
        "action": action,
        "target_type": "rom",
        "target_id": "1",
        "target_name": "Super Mario Bros.",
        "data": {},
    }
    event = AuditEvent(**{**fields, **overrides})
    db_audit_event_handler.add_events([event])
    return event


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ids(response) -> list[int]:
    return [event["id"] for event in response.json()["items"]]


class TestAdminReadsEveryone:
    def test_lists_every_users_events_newest_first(
        self, client, access_token, admin_user, viewer_user
    ):
        older = _add(viewer_user, minutes_ago=5)
        newer = _add(admin_user, AuditAction.ROM_EDIT, minutes_ago=1)
        system = _add(None, AuditAction.SCAN_START, minutes_ago=3)

        response = client.get("/api/audit-events", headers=_auth(access_token))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 3
        assert _ids(response) == [newer.id, system.id, older.id]
        first = body["items"][0]
        assert first["action"] == "rom.edit"
        assert first["category"] == "library"
        assert first["actor"]["username"] == admin_user.username
        assert first["target_name"] == "Super Mario Bros."
        assert body["items"][1]["actor_kind"] == "system"
        assert body["items"][1]["actor"] is None

    def test_filters_by_actor(self, client, access_token, admin_user, viewer_user):
        _add(admin_user)
        theirs = _add(viewer_user)

        response = client.get(
            "/api/audit-events",
            params={"actor_id": viewer_user.id},
            headers=_auth(access_token),
        )

        assert _ids(response) == [theirs.id]

    def test_an_admin_token_without_users_read_sees_only_its_own(
        self, client, admin_user, viewer_user
    ):
        own = _add(admin_user)
        _add(viewer_user)
        token = oauth_handler.create_access_token(
            data={
                "sub": admin_user.username,
                "iss": "romm:oauth",
                "scopes": " ".join(
                    s for s in admin_user.oauth_scopes if s != "users.read"
                ),
            },
            expires_delta=timedelta(minutes=5),
        )

        response = client.get("/api/audit-events", headers=_auth(token))

        assert _ids(response) == [own.id]


class TestNonAdminReadsOwn:
    def test_is_held_to_their_own_events_whatever_they_ask_for(
        self, client, viewer_access_token, admin_user, viewer_user
    ):
        _add(admin_user)
        own = _add(viewer_user)

        response = client.get(
            "/api/audit-events",
            params={"actor_id": admin_user.id},
            headers=_auth(viewer_access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        assert _ids(response) == [own.id]

    def test_needs_a_login(self, client):
        response = client.get("/api/audit-events")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestFilters:
    def test_category_narrows_to_its_actions(self, client, access_token, admin_user):
        play = _add(admin_user, AuditAction.ROM_PLAY)
        _add(admin_user, AuditAction.ROM_EDIT)
        _add(admin_user, AuditAction.AUTH_LOGIN)

        response = client.get(
            "/api/audit-events",
            params={"category": "consumption"},
            headers=_auth(access_token),
        )

        assert _ids(response) == [play.id]

    def test_category_and_action_intersect(self, client, access_token, admin_user):
        _add(admin_user, AuditAction.ROM_PLAY)
        _add(admin_user, AuditAction.ROM_EDIT)

        response = client.get(
            "/api/audit-events",
            params={"category": "consumption", "action": "rom.edit"},
            headers=_auth(access_token),
        )

        assert _ids(response) == []

    def test_date_range_is_inclusive_then_exclusive(
        self, client, access_token, admin_user
    ):
        now = datetime.now(timezone.utc)
        _add(admin_user, minutes_ago=120)
        inside = _add(admin_user, minutes_ago=60)
        _add(admin_user, minutes_ago=0)

        response = client.get(
            "/api/audit-events",
            params={
                "since": (now - timedelta(minutes=90)).isoformat(),
                "until": (now - timedelta(minutes=30)).isoformat(),
            },
            headers=_auth(access_token),
        )

        assert _ids(response) == [inside.id]

    def test_search_matches_names_and_addresses(
        self, client, access_token, admin_user, viewer_user
    ):
        by_viewer = _add(viewer_user, target_name="Tetris")
        zelda = _add(admin_user, target_name="The Legend of Zelda")
        from_lan = _add(None, target_name="Doom", ip_address="192.168.1.20")

        viewer = client.get(
            "/api/audit-events",
            params={"search": "VIEWER"},
            headers=_auth(access_token),
        )
        target = client.get(
            "/api/audit-events",
            params={"search": "zelda"},
            headers=_auth(access_token),
        )

        address = client.get(
            "/api/audit-events",
            params={"search": "192.168.1"},
            headers=_auth(access_token),
        )

        assert _ids(viewer) == [by_viewer.id]
        assert _ids(target) == [zelda.id]
        assert _ids(address) == [from_lan.id]

    def test_pages_stay_pinned_to_max_id(self, client, access_token, admin_user):
        newest = _add(admin_user, minutes_ago=1)
        # Recorded after `newest` but happened before it, like a synced play.
        synced = _add(admin_user, AuditAction.ROM_PLAY, minutes_ago=30)

        first = client.get(
            "/api/audit-events",
            params={"limit": 1},
            headers=_auth(access_token),
        )
        _add(admin_user)
        second = client.get(
            "/api/audit-events",
            params={"limit": 1, "offset": 1, "max_id": first.json()["max_id"]},
            headers=_auth(access_token),
        )

        assert _ids(first) == [newest.id]
        assert first.json()["max_id"] == synced.id
        assert _ids(second) == [synced.id]
        assert second.json()["total"] == 2


def test_an_event_outlives_its_actor(client, access_token, viewer_user):
    event = _add(viewer_user)
    db_user_handler.delete_user(viewer_user.id)

    response = client.get("/api/audit-events", headers=_auth(access_token))

    [item] = response.json()["items"]
    assert item["id"] == event.id
    assert item["actor"] is None
    assert item["actor_name"] == "test_viewer"
