import pytest
from sqlalchemy.orm import Session

from decorators.database import (
    INJECTED_SESSION,
    begin_isolated_session,
    begin_session,
    in_transaction,
    transaction,
)
from handler.database import db_deleted_asset_handler
from handler.database.base_handler import sync_session
from models.rom import Rom
from models.user import User


@begin_session
def _joined(session: Session = INJECTED_SESSION) -> Session:
    return session


@begin_isolated_session
def _isolated(session: Session = INJECTED_SESSION) -> Session:
    return session


@begin_session
def _outer(session: Session = INJECTED_SESSION) -> tuple[Session, Session, Session]:
    return session, _joined(), _isolated()


class TestBeginSession:
    def test_nested_call_joins_the_open_transaction(self):
        outer, joined, _ = _outer()

        assert joined is outer

    def test_isolated_call_begins_its_own(self):
        outer, _, isolated = _outer()

        assert isolated is not outer

    def test_separate_calls_get_separate_sessions(self):
        assert _joined() is not _joined()

    def test_explicit_session_is_joined_by_nested_calls(self):
        with sync_session.begin() as session:
            outer, joined, isolated = _outer(session=session)

        assert outer is session
        assert joined is session
        assert isolated is not session

    def test_isolated_call_honours_an_explicit_session(self):
        with sync_session.begin() as session:
            assert _isolated(session=session) is session


class TestTransaction:
    def test_nested_calls_join_it(self):
        with transaction() as session:
            assert _joined() is session

    def test_nested_transaction_joins_the_outer(self):
        with transaction() as outer, transaction() as inner:
            assert inner is outer

    def test_context_is_cleared_after_an_error(self):
        with pytest.raises(RuntimeError), transaction():
            assert in_transaction()
            raise RuntimeError

        assert not in_transaction()

    def test_isolated_work_survives_the_outer_rollback(
        self, rom: Rom, admin_user: User
    ):
        with pytest.raises(RuntimeError), transaction():
            db_deleted_asset_handler.ensure_record(admin_user.id, rom.id, "autosave")
            raise RuntimeError

        [record] = db_deleted_asset_handler.get_deletions(
            user_id=admin_user.id, rom_ids=[rom.id]
        )
        assert record.content_hashes == []
