from datetime import datetime, timedelta, timezone

from tests.db_race_stubs import run_before_first
from tests.factories import make_device_token

from handler.database import db_client_token_handler
from models.user import User
from utils.datetime import to_utc


def _last_used_at(token_id: int) -> datetime | None:
    token = db_client_token_handler.get_token(token_id)
    assert token is not None
    return token.last_used_at


class TestUpdateLastUsed:
    def test_bumps_when_never_used(self, admin_user: User):
        token, _ = make_device_token(admin_user, None)

        db_client_token_handler.update_last_used(token.id)

        assert _last_used_at(token.id) is not None

    def test_bumps_when_last_used_is_old(self, admin_user: User):
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        token, _ = make_device_token(admin_user, None, last_used_at=old)

        db_client_token_handler.update_last_used(token.id)

        refreshed = _last_used_at(token.id)
        assert refreshed is not None
        # MariaDB returns naive datetimes; normalize to UTC for comparison
        assert to_utc(refreshed) > old

    def test_skips_when_last_used_within_debounce_window(self, admin_user: User):
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        token, _ = make_device_token(admin_user, None, last_used_at=recent)

        db_client_token_handler.update_last_used(token.id)

        refreshed = _last_used_at(token.id)
        assert refreshed is not None
        assert abs((to_utc(refreshed) - recent).total_seconds()) < 1

    def test_unknown_token_is_a_no_op(self):
        db_client_token_handler.update_last_used(999_999)

    def test_does_not_read_the_token_before_updating_it(
        self, admin_user: User, executed_statements: list[str]
    ):
        token, _ = make_device_token(admin_user, None)
        executed_statements.clear()

        db_client_token_handler.update_last_used(token.id)

        statements = [s.lstrip().lower() for s in executed_statements]
        assert [s for s in statements if s.startswith("select")] == []
        assert any(s.startswith("update client_tokens") for s in statements)

    def test_survives_a_concurrent_request_committing_the_same_update(
        self, admin_user: User
    ):
        """Guards against MariaDB error 1020, "Record has changed since last read"."""
        token, _ = make_device_token(admin_user, None)

        with run_before_first(
            "update client_tokens",
            lambda: db_client_token_handler.update_last_used(token.id),
        ) as raced:
            db_client_token_handler.update_last_used(token.id)

        assert raced
        assert _last_used_at(token.id) is not None
