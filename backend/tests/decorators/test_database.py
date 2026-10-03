from collections.abc import Iterator

from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from handler.database.base_handler import sync_session


@begin_session
def _yield_session(session: Session = INJECTED_SESSION) -> Iterator[Session]:
    yield session


def test_generator_holds_its_session_until_exhausted():
    sessions = _yield_session()
    session = next(sessions)
    assert session.in_transaction()

    assert next(sessions, None) is None
    assert not session.in_transaction()


def test_generator_reuses_a_caller_session():
    with sync_session.begin() as session:
        assert next(_yield_session(session=session)) is session
