from decorators.database import begin_session
from handler.db_handler import DBHandler
from models.user import Role, User
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session


class DBUsersHandler(DBHandler):
    @begin_session
    def add_user(self, user: User, session: Session = None):
        return session.merge(user)

    @begin_session
    def get_user_by_username(self, username: str, session: Session = None):
        return session.scalars(
            select(User).filter_by(username=username).limit(1)
        ).first()

    @begin_session
    def get_user(self, id: int, session: Session = None):
        return session.get(User, id)

    @begin_session
    def update_user(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(User)
            .where(User.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_user(self, id: int, session: Session = None):
        return session.execute(
            delete(User)
            .where(User.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_users(self, session: Session = None):
        return session.scalars(select(User)).all()

    @begin_session
    def get_admin_users(self, session: Session = None):
        return session.scalars(select(User).filter_by(role=Role.ADMIN)).all()
