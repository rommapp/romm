from datetime import datetime, timedelta, timezone

from sqlalchemy import event
from tests.factories import make_device_token

from handler.database import db_client_token_handler
from handler.database.base_handler import sync_engine
from models.user import User
from utils.datetime import to_utc


def _last_used_at(hashed_token: str) -> datetime | None:
    token = db_client_token_handler.get_token_by_hash(hashed_token)
    assert token is not None
    return token.last_used_at


class TestUpdateLastUsed:
    def test_bumps_when_never_used(self, admin_user: User):
        token, _ = make_device_token(admin_user, None)

        db_client_token_handler.update_last_used(token.id)

        assert _last_used_at(token.hashed_token) is not None

    def test_bumps_when_last_used_is_old(self, admin_user: User):
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        token, _ = make_device_token(admin_user, None, last_used_at=old)

        db_client_token_handler.update_last_used(token.id)

        refreshed = _last_used_at(token.hashed_token)
        assert refreshed is not None
        # MariaDB returns naive datetimes; normalize to UTC for comparison
        assert to_utc(refreshed) > old

    def test_skips_when_last_used_within_debounce_window(self, admin_user: User):
        recent = datetime.now(timezone.utc) - timedelta(minutes=1)
        token, _ = make_device_token(admin_user, None, last_used_at=recent)

        db_client_token_handler.update_last_used(token.id)

        refreshed = _last_used_at(token.hashed_token)
        assert refreshed is not None
        assert abs((to_utc(refreshed) - recent).total_seconds()) < 1

    def test_unknown_token_is_a_no_op(self):
        db_client_token_handler.update_last_used(999_999)

    def test_does_not_read_the_token_before_updating_it(
        self, admin_user: User, executed_statements: list[str]
    ):
        """A read in the same transaction makes a concurrent commit fail the UPDATE with
        "Record has changed since last read" (MariaDB error 1020)."""
        token, _ = make_device_token(admin_user, None)
        executed_statements.clear()

        db_client_token_handler.update_last_used(token.id)

        statements = [s.lstrip().lower() for s in executed_statements]
        assert [s for s in statements if s.startswith("select")] == []
        assert any(s.startswith("update client_tokens") for s in statements)

    def test_survives_a_concurrent_request_committing_the_same_update(
        self, admin_user: User
    ):
        """Another request bumping the same token between this one's snapshot and its UPDATE
        must not fail this request (MariaDB error 1020, "Record has changed since last read").
        """
        token, _ = make_device_token(admin_user, None)
        raced = False

        def commit_the_other_request_first(
            conn, cursor, statement, parameters, context, executemany
        ):
            nonlocal raced
            if raced or not statement.lstrip().lower().startswith(
                "update client_tokens"
            ):
                return
            raced = True
            db_client_token_handler.update_last_used(token.id)

        event.listen(
            sync_engine, "before_cursor_execute", commit_the_other_request_first
        )
        try:
            db_client_token_handler.update_last_used(token.id)
        finally:
            event.remove(
                sync_engine, "before_cursor_execute", commit_the_other_request_first
            )

        assert raced
        assert _last_used_at(token.hashed_token) is not None
