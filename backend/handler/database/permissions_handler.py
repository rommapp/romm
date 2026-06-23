from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.permission import (
    HiddenEntity,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
    UserPermissionOverride,
)

from .base_handler import DBBaseHandler


class DBPermissionsHandler(DBBaseHandler):
    """Read access to the granular permission model used by the resolver.

    Write/CRUD for the admin UI lands in a later PR; this handler only exposes
    what ``handler/auth/permissions.py`` needs to resolve a user's effective
    permissions per request.
    """

    @begin_session
    def get_default_group(
        self,
        session: Session = None,  # type: ignore
    ) -> PermissionGroup | None:
        return session.scalar(
            select(PermissionGroup).filter_by(is_default=True).limit(1)
        )

    @begin_session
    def get_group_grants(
        self,
        group_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[PermissionGroupGrant]:
        return session.scalars(
            select(PermissionGroupGrant).filter_by(group_id=group_id)
        ).all()

    @begin_session
    def get_user_overrides(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> Sequence[UserPermissionOverride]:
        return session.scalars(
            select(UserPermissionOverride).filter_by(user_id=user_id)
        ).all()

    @begin_session
    def get_hidden_entity_ids(
        self,
        entity: PermEntity,
        user_id: int | None,
        group_id: int | None,
        session: Session = None,  # type: ignore
    ) -> set[int]:
        """Ids of `entity` hidden from the given user OR their group.

        Cascade (a hidden platform hiding its roms/firmware) is applied at query
        time by the consuming handlers, not here.
        """
        principals = []
        if user_id is not None:
            principals.append(HiddenEntity.user_id == user_id)
        if group_id is not None:
            principals.append(HiddenEntity.group_id == group_id)
        if not principals:
            return set()

        rows = session.scalars(
            select(HiddenEntity.entity_id).where(
                HiddenEntity.entity == entity, or_(*principals)
            )
        ).all()
        return set(rows)
