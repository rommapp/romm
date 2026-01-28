from collections.abc import Sequence

from sqlalchemy import and_, delete, func, not_, select, update
from sqlalchemy.orm import QueryableAttribute, Session, load_only
from sqlalchemy.sql import Delete, Select, Update

from decorators.database import begin_session
from models.user import Role, User

from .base_handler import DBBaseHandler


class DBUsersHandler(DBBaseHandler):
    def filter[QueryT: Select[tuple[User]] | Update | Delete](
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
        session: Session = None,  # type: ignore
    ) -> User:
        return session.merge(user)

    @begin_session
    def get_user_by_username(
        self,
        username: str,
        session: Session = None,  # type: ignore
    ) -> User | None:
        query = self.filter(select(User), usernames=[username])
        return session.scalar(query.limit(1))

    @begin_session
    def get_user_by_email(
        self,
        email: str,
        session: Session = None,  # type: ignore
    ) -> User | None:
        query = self.filter(select(User), emails=[email])
        return session.scalar(query.limit(1))

    @begin_session
    def get_user(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> User | None:
        return session.get(User, id)

    @begin_session
    def update_user(
        self,
        id: int,
        data: dict,
        session: Session = None,  # type: ignore
    ) -> User:
        session.execute(
            update(User)
            .where(User.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(User).filter_by(id=id).one()

    @begin_session
    def get_users(
        self,
        *,
        usernames: Sequence[str] = (),
        emails: Sequence[str] = (),
        roles: Sequence[Role] = (),
        has_ra_username: bool | None = None,
        only_fields: Sequence[QueryableAttribute] | None = None,
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
    ):
        return session.execute(
            delete(User)
            .where(User.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_admin_users(
        self,
        session: Session = None,  # type: ignore
    ) -> Sequence[User]:
        query = self.filter(select(User), roles=[Role.ADMIN])
        return session.scalars(query).all()
