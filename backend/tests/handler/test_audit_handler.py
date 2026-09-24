from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from starlette.authentication import UnauthenticatedUser
from starlette.requests import Request
from tests.audit_events import recorded_events

from handler import audit_handler
from handler.audit_handler import (
    AuditActor,
    AuditDraft,
    AuditTarget,
    claim_once,
    record,
    record_download,
    record_many,
)
from handler.database import db_audit_event_handler
from handler.redis_handler import sync_cache
from models.audit_event import AuditAction, AuditActorKind, AuditTargetType
from models.user import User
from utils.datetime import to_utc

ROM = AuditTarget(AuditTargetType.ROM, 12, "Metroid")


@pytest.fixture(autouse=True)
def clear_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


def _request(
    user: Any = None,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    state: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/",
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
            ],
            "client": ("203.0.113.9", 4242),
            "user": user if user is not None else UnauthenticatedUser(),
            "state": state or {},
            "session": session or {},
        }
    )


class TestActorFromRequest:
    def test_a_signed_in_user_with_their_session_device(self, admin_user: User):
        actor = AuditActor.from_request(
            _request(admin_user, session={"device_id": "web-1"})
        )

        assert actor == AuditActor(
            AuditActorKind.USER,
            user_id=admin_user.id,
            name="test_admin",
            ip_address="203.0.113.9",
            device_id="web-1",
        )

    def test_a_client_tokens_device_wins_over_the_session(self, admin_user: User):
        actor = AuditActor.from_request(
            _request(
                admin_user,
                state={"device_id": "deck"},
                session={"device_id": "web-1"},
            )
        )

        assert actor.device_id == "deck"

    def test_nobody_signed_in_is_anonymous(self):
        actor = AuditActor.from_request(_request())

        assert actor == AuditActor(AuditActorKind.ANONYMOUS, ip_address="203.0.113.9")

    def test_a_kiosk_visitor_is_anonymous(self):
        actor = AuditActor.from_request(_request(User.kiosk_mode_user()))

        assert actor.kind == AuditActorKind.ANONYMOUS
        assert actor.user_id is None


class TestRecord:
    def test_stores_the_actor_and_target_snapshots(self, admin_user: User):
        record(
            AuditAction.ROM_EDIT,
            AuditActor.for_user(admin_user),
            ROM,
            {"changed": ["name"]},
        )

        [event] = recorded_events()
        assert event.action == "rom.edit"
        assert event.actor_id == admin_user.id
        assert event.actor_name == "test_admin"
        assert (event.target_type, event.target_id, event.target_name) == (
            "rom",
            "12",
            "Metroid",
        )
        assert event.data == {"changed": ["name"]}

    def test_a_storage_failure_never_reaches_the_caller(self, mocker):
        mocker.patch.object(
            db_audit_event_handler, "add_events", side_effect=RuntimeError("down")
        )

        record(AuditAction.SCAN_START, audit_handler.SYSTEM_ACTOR)

    def test_clips_long_lists_and_drops_nul(self):
        record(
            AuditAction.COLLECTION_ADD_ROMS,
            audit_handler.SYSTEM_ACTOR,
            data={"rom_ids": list(range(80)), "name": "a\x00b"},
        )

        [event] = recorded_events()
        assert event.data["rom_ids"] == list(range(50))
        assert event.data["truncated"] is True
        assert event.data["name"] == "ab"

    def test_drops_events_older_than_the_retention(self, mocker):
        mocker.patch.object(audit_handler, "AUDIT_LOG_RETENTION_DAYS", 90)
        now = datetime.now(timezone.utc)

        record_many(
            [
                AuditDraft(
                    AuditAction.ROM_PLAY,
                    audit_handler.SYSTEM_ACTOR,
                    occurred_at=now - timedelta(days=91),
                ),
                AuditDraft(
                    AuditAction.ROM_PLAY,
                    audit_handler.SYSTEM_ACTOR,
                    occurred_at=now - timedelta(days=1),
                ),
            ]
        )

        [event] = recorded_events()
        assert to_utc(event.occurred_at) > now - timedelta(days=2)

    def test_for_user_id_without_a_user_is_the_system(self):
        assert AuditActor.for_user_id(None) == audit_handler.SYSTEM_ACTOR


def test_claim_once_holds_within_its_window():
    assert claim_once("k", 60) is True
    assert claim_once("k", 60) is False
    assert claim_once("other", 60) is True


class TestRecordDownload:
    @pytest.mark.parametrize(
        "range_header,counted",
        [
            (None, True),
            ("bytes=0-", True),
            ("bytes=0-1023", True),
            ("bytes=100-", False),
            ("bytes=-500", False),
            ("not a range", True),
            ("bytes=" + "9" * 5000 + "-", False),
        ],
    )
    def test_only_a_transfer_from_the_first_byte_counts(
        self, admin_user: User, range_header: str | None, counted: bool
    ):
        headers = {"range": range_header} if range_header else {}

        record_download(_request(admin_user, headers=headers), ROM, "12")

        assert len(recorded_events()) == (1 if counted else 0)

    def test_a_head_request_never_counts(self, admin_user: User):
        record_download(_request(admin_user, method="HEAD"), ROM, "12")

        assert recorded_events() == []

    def test_a_repeat_within_the_window_counts_once(self, admin_user: User):
        record_download(_request(admin_user), ROM, "12")
        record_download(_request(admin_user), ROM, "12")
        record_download(_request(admin_user), ROM, "13")

        assert len(recorded_events()) == 2

    def test_an_anonymous_download_is_kept_by_ip(self):
        record_download(_request(headers={"user-agent": "Tinfoil/19.0"}), ROM, "12")

        [event] = recorded_events()
        assert event.actor_kind == "anonymous"
        assert event.actor_id is None
        assert event.ip_address == "203.0.113.9"
        assert event.data["user_agent"] == "Tinfoil/19.0"
