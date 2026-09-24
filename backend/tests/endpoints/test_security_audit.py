import base64
import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints import auth as auth_endpoints
from handler.auth import auth_handler
from handler.database import db_audit_event_handler
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditEvent
from models.user import User
from tasks.tasks import Task, TaskType


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _basic(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _events() -> list[AuditEvent]:
    rows, _, _ = db_audit_event_handler.get_events(
        AuditEventFilters(), limit=50, offset=0
    )
    return [event for event, _ in rows]


class TestLogin:
    def test_a_session_login_names_its_device(
        self, client: TestClient, admin_user: User
    ):
        response = client.post(
            "/api/login", headers=_basic("test_admin", "test_admin_password")
        )

        assert response.status_code == status.HTTP_200_OK
        [event] = _events()
        assert event.action == "auth.login"
        assert event.actor_id == admin_user.id
        assert event.device_id is not None
        assert event.data == {"method": "password"}

    def test_repeated_failures_from_one_address_are_one_attempt(
        self, client: TestClient, admin_user: User
    ):
        for _ in range(3):
            response = client.post("/api/login", headers=_basic("test_admin", "wrong"))
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        [event] = _events()
        assert event.action == "auth.login_failed"
        assert event.actor_id == admin_user.id
        assert event.data["reason"] == "credentials"

    def test_a_failure_for_an_unknown_name_is_anonymous(self, client: TestClient):
        client.post("/api/login", headers=_basic("nobody", "wrong"))

        [event] = _events()
        assert event.actor_kind == "anonymous"
        assert event.data["username"] == "nobody"

    def test_one_address_cycling_usernames_is_capped(self, client: TestClient, mocker):
        mocker.patch.object(auth_endpoints, "LOGIN_FAILURES_PER_ADDRESS", 3)

        for i in range(6):
            client.post("/api/login", headers=_basic(f"guess{i}", "wrong"))

        assert len(_events()) == 3

    def test_repeated_reset_requests_are_one(
        self, client: TestClient, admin_user: User, mocker
    ):
        mocker.patch.object(auth_handler, "send_password_reset_link")

        for _ in range(2):
            client.post("/api/forgot-password", json={"username": "test_admin"})

        [event] = _events()
        assert event.action == "auth.password_reset_request"
        assert (event.actor_kind, event.target_name) == ("anonymous", "test_admin")

    def test_a_token_grant_is_a_login(self, client: TestClient, admin_user: User):
        response = client.post(
            "/api/token",
            data={
                "grant_type": "password",
                "username": "test_admin",
                "password": "test_admin_password",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        [event] = _events()
        assert (event.action, event.data["method"]) == ("auth.login", "token")


class TestUsers:
    def test_a_role_change_records_both_roles(
        self, client: TestClient, access_token: str, viewer_user: User
    ):
        client.put(
            f"/api/users/{viewer_user.id}",
            data={"role": "admin"},
            headers=_auth(access_token),
        )

        [event] = _events()
        assert event.action == "user.edit"
        assert event.target_name == "test_viewer"
        assert event.data["changed"] == ["role"]
        assert event.data["role"] == {"from": "user", "to": "admin"}

    def test_saving_ui_settings_is_not_an_edit(
        self, client: TestClient, access_token: str, admin_user: User
    ):
        client.put(
            f"/api/users/{admin_user.id}",
            data={"ui_settings": '{"theme": "dark"}'},
            headers=_auth(access_token),
        )

        assert _events() == []

    def test_a_deleted_user_keeps_their_name(
        self, client: TestClient, access_token: str, viewer_user: User
    ):
        client.delete(f"/api/users/{viewer_user.id}", headers=_auth(access_token))

        [event] = _events()
        assert (event.action, event.target_name) == ("user.delete", "test_viewer")


@patch("endpoints.tasks.has_live_worker", return_value=True)
@patch(
    "endpoints.tasks.enqueue_task",
    return_value=Mock(
        id="job-1",
        created_at=None,
        enqueued_at=None,
        **{"get_status.return_value": "queued"},
    ),
)
def test_a_manual_task_run_is_recorded(
    _enqueue, _worker, client: TestClient, access_token: str
):
    task = Mock(spec=Task)
    task.title = "Cleanup"
    task.task_type = TaskType.CLEANUP
    task.can_run_manually = True
    with patch("endpoints.tasks.RUNNABLE_TASKS", {"cleanup": task}):
        client.post("/api/tasks/run/cleanup", headers=_auth(access_token))

    [event] = _events()
    assert event.action == "task.run"
    assert (event.target_id, event.target_name) == ("cleanup", "Cleanup")
    assert event.data["job_id"] == "job-1"


class TestClientTokens:
    @pytest.fixture
    def token_id(self, client: TestClient, access_token: str) -> int:
        response = client.post(
            "/api/client-tokens",
            json={"name": "Argosy", "scopes": ["roms.read"]},
            headers=_auth(access_token),
        )
        return response.json()["id"]

    def test_creating_and_revoking_are_recorded(
        self, client: TestClient, access_token: str, token_id: int
    ):
        client.delete(f"/api/client-tokens/{token_id}", headers=_auth(access_token))

        revoke, create = _events()
        assert create.action == "client_token.create"
        assert revoke.action == "client_token.revoke"
        assert revoke.target_name == "Argosy"
        assert revoke.data["scopes"] == ["roms.read"]


def test_a_new_permission_group_is_recorded(client: TestClient, access_token: str):
    # Groups outlive a test, so the name has to be one no earlier run left behind.
    name = f"Kids {uuid.uuid4().hex[:8]}"
    client.post(
        "/api/permissions/groups",
        json={"name": name, "grants": []},
        headers=_auth(access_token),
    )

    [event] = _events()
    assert (event.action, event.target_name) == ("permission_group.create", name)
