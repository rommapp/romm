from collections.abc import Sequence

from decorators.database import begin_session
from models.smb import SmbPlatformPermission, SmbUser
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from .base_handler import DBBaseHandler


class DBSmbHandler(DBBaseHandler):
    @begin_session
    def list_users(
        self,
        session: Session = None,  # type: ignore
    ) -> Sequence[SmbUser]:
        return session.scalars(
            select(SmbUser)
            .options(
                selectinload(SmbUser.permissions).selectinload(
                    SmbPlatformPermission.platform
                )
            )
            .order_by(SmbUser.username.asc())
        ).all()

    @begin_session
    def get_user(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> SmbUser | None:
        return session.scalar(
            select(SmbUser)
            .where(SmbUser.id == user_id)
            .options(
                selectinload(SmbUser.permissions).selectinload(
                    SmbPlatformPermission.platform
                )
            )
        )

    @begin_session
    def get_user_by_username(
        self,
        username: str,
        session: Session = None,  # type: ignore
    ) -> SmbUser | None:
        return session.scalar(select(SmbUser).where(SmbUser.username == username))

    @begin_session
    def add_user(
        self,
        user: SmbUser,
        session: Session = None,  # type: ignore
    ) -> SmbUser:
        session.add(user)
        session.flush()
        return self.get_user(user.id, session=session)

    @begin_session
    def replace_permissions(
        self,
        user_id: int,
        permissions: list[SmbPlatformPermission],
        session: Session = None,  # type: ignore
    ) -> SmbUser | None:
        user = session.scalar(
            select(SmbUser)
            .where(SmbUser.id == user_id)
            .options(selectinload(SmbUser.permissions))
        )
        if user is None:
            return None

        # Flush the orphan removals before inserting replacements. This keeps
        # the per-user/platform uniqueness constraint valid when an access
        # mode is changed for an existing platform.
        user.permissions.clear()
        session.flush()
        for permission in permissions:
            user.permissions.append(permission)
        session.flush()
        return self.get_user(user_id, session=session)

    @begin_session
    def delete_user(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        result = session.execute(delete(SmbUser).where(SmbUser.id == user_id))
        return result.rowcount
