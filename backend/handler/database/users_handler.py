from collections.abc import Sequence
from typing import Any

from sqlalchemy import Result, and_, delete, func, not_, or_, select, update
from sqlalchemy.orm import QueryableAttribute, Session, load_only
from sqlalchemy.sql import Delete, Select, Update

from decorators.database import INJECTED_SESSION, begin_session
from models.user import Role, User

from .base_handler import DBBaseHandler, affected_rows


class DBUsersHandler(DBBaseHandler):
    def filter[QueryT: (Select[User], Update, Delete)](
        self,
        query: QueryT,
        *,
        usernames: Sequence[str] = (),
        emails: Sequence[str] = (),
        roles: Sequence[Role] = (),
        has_ra_username: bool | None = None,
    ) -> QueryT:
        if usernames:
            query = query.filter(
                func.lower(User.username).in_([u.lower() for u in usernames])
            )
        if emails:
            query = query.filter(
                func.lower(User.email).in_([e.lower() for e in emails])
            )
        if roles:
            query = query.filter(User.role.in_(roles))
        if has_ra_username is not None:
            predicate = and_(User.ra_username != "", User.ra_username.isnot(None))
            if not has_ra_username:
                predicate = not_(predicate)
            query = query.filter(predicate)
        return query

    @begin_session
    def add_user(
        self,
        user: User,
        session: Session = INJECTED_SESSION,
    ) -> User:
        return session.merge(user)

    @begin_session
    def get_user_by_username(
        self,
        username: str,
        session: Session = INJECTED_SESSION,
    ) -> User | None:
        query = self.filter(select(User), usernames=[username])
        return session.scalar(query.limit(1))

    @begin_session
    def get_user_by_email(
        self,
        email: str,
        session: Session = INJECTED_SESSION,
    ) -> User | None:
        query = self.filter(select(User), emails=[email])
        return session.scalar(query.limit(1))

    @begin_session
    def get_user_by_oidc_identity(
        self,
        oidc_issuer: str,
        oidc_sub: str,
        session: Session = INJECTED_SESSION,
    ) -> User | None:
        return session.scalar(
            select(User).filter_by(oidc_issuer=oidc_issuer, oidc_sub=oidc_sub).limit(1)
        )

    @begin_session
    def get_user(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> User | None:
        return session.get(User, id)

    @begin_session
    def update_user(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> User:
        session.execute(
            update(User)
            .where(User.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.scalars(select(User).filter_by(id=id)).one()

    @begin_session
    def fill_empty_ra_username(
        self,
        id: int,
        ra_username: str,
        session: Session = INJECTED_SESSION,
    ) -> bool:
        """Set `ra_username` only while it is still empty; whether it was set."""
        result = session.execute(
            update(User)
            .where(
                User.id == id, or_(User.ra_username.is_(None), User.ra_username == "")
            )
            .values(ra_username=ra_username)
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result) > 0

    @begin_session
    def clear_ra_login_sealed(
        self,
        id: int,
        sealed: str,
        session: Session = INJECTED_SESSION,
    ) -> bool:
        """Null `ra_login_sealed` only while it still holds `sealed`; whether it did."""
        result = session.execute(
            update(User)
            .where(User.id == id, User.ra_login_sealed == sealed)
            .values(ra_login_sealed=None)
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result) > 0

    @begin_session
    def get_users(
        self,
        *,
        usernames: Sequence[str] = (),
        emails: Sequence[str] = (),
        roles: Sequence[Role] = (),
        has_ra_username: bool | None = None,
        only_fields: Sequence[QueryableAttribute[Any]] | None = None,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[User]:
        query = self.filter(
            select(User),
            usernames=usernames,
            emails=emails,
            roles=roles,
            has_ra_username=has_ra_username,
        )

        if only_fields:
            query = query.options(load_only(*only_fields))

        return session.scalars(query).all()

    @begin_session
    def delete_user(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> Result[*tuple[Any, ...]]:
        return session.execute(
            delete(User)
            .where(User.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_admin_users(
        self,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[User]:
        query = self.filter(select(User), roles=[Role.ADMIN])
        return session.scalars(query).all()
