from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload

from decorators.database import begin_session
from models.client_token import ClientToken
from utils.datetime import to_utc

from .base_handler import DBBaseHandler

LAST_USED_DEBOUNCE = timedelta(minutes=5)


class DBClientTokensHandler(DBBaseHandler):
    @begin_session
    def add_token(
        self,
        token: ClientToken,
        session: Session = None,  # type: ignore
    ) -> ClientToken:
        return session.merge(token)

    @begin_session
    def get_token_by_hash(
        self,
        hashed_token: str,
        session: Session = None,  # type: ignore
    ) -> ClientToken | None:
        return session.scalar(
            select(ClientToken).where(ClientToken.hashed_token == hashed_token)
        )

    @begin_session
    def get_tokens_by_user(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[ClientToken]:
        return session.scalars(
            select(ClientToken)
            .where(ClientToken.user_id == user_id)
            .order_by(ClientToken.created_at.desc())
        ).all()

    @begin_session
    def get_all_tokens(
        self,
        session: Session = None,  # type: ignore
    ) -> Sequence[ClientToken]:
        return (
            session.scalars(
                select(ClientToken)
                .options(joinedload(ClientToken.user))
                .order_by(ClientToken.created_at.desc())
            )
            .unique()
            .all()
        )

    @begin_session
    def delete_token(
        self,
        token_id: int,
        user_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> int:
        stmt = delete(ClientToken).where(ClientToken.id == token_id)
        if user_id is not None:
            stmt = stmt.where(ClientToken.user_id == user_id)
        result = session.execute(stmt.execution_options(synchronize_session="evaluate"))
        return result.rowcount

    @begin_session
    def update_last_used(
        self,
        token_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        now = datetime.now(timezone.utc)
        token = session.get(ClientToken, token_id)
        if token is None:
            return
        if (
            token.last_used_at
            and (now - to_utc(token.last_used_at)) < LAST_USED_DEBOUNCE
        ):
            return
        session.execute(
            update(ClientToken)
            .where(ClientToken.id == token_id)
            .values(last_used_at=now)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def update_hashed_token(
        self,
        token_id: int,
        new_hash: str,
        user_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> ClientToken | None:
        stmt = (
            update(ClientToken)
            .where(ClientToken.id == token_id)
            .values(hashed_token=new_hash, last_used_at=None)
            .execution_options(synchronize_session="evaluate")
        )
        if user_id is not None:
            stmt = stmt.where(ClientToken.user_id == user_id)
        result = session.execute(stmt)
        if result.rowcount == 0:
            return None
        return session.get(ClientToken, token_id)

    @begin_session
    def count_tokens_by_user(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(ClientToken)
                .where(ClientToken.user_id == user_id)
            )
            or 0
        )

    @begin_session
    def get_token(
        self,
        token_id: int,
        user_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> ClientToken | None:
        stmt = select(ClientToken).where(ClientToken.id == token_id)
        if user_id is not None:
            stmt = stmt.where(ClientToken.user_id == user_id)
        return session.scalar(stmt)
