from collections.abc import Iterable, Sequence

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
    UserPermissionOverride,
)
from models.user import User

from .base_handler import DBBaseHandler

# (entity, action, own_only)
GrantTuple = tuple[PermEntity, PermAction, bool]
# (entity, action, granted, own_only)
OverrideTuple = tuple[PermEntity, PermAction, bool, bool]


class DBPermissionsHandler(DBBaseHandler):
    """Read and admin-write access to the granular permission model.

    The read helpers (`get_default_group`, `get_group_grants`,
    `get_user_overrides`, `get_hidden_entity_ids`) feed the per-request resolver;
    the rest is the admin CRUD surface for managing groups, memberships,
    overrides and hidden entities.
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

    # --- Admin CRUD: groups ---------------------------------------------------

    @begin_session
    def get_groups(
        self,
        session: Session = None,  # type: ignore
    ) -> Sequence[PermissionGroup]:
        return (
            session.scalars(select(PermissionGroup).order_by(PermissionGroup.name))
            .unique()
            .all()
        )

    @begin_session
    def get_group(
        self,
        group_id: int,
        session: Session = None,  # type: ignore
    ) -> PermissionGroup | None:
        return session.get(PermissionGroup, group_id)

    @begin_session
    def get_group_by_name(
        self,
        name: str,
        session: Session = None,  # type: ignore
    ) -> PermissionGroup | None:
        return session.scalar(select(PermissionGroup).filter_by(name=name).limit(1))

    @begin_session
    def create_group(
        self,
        name: str,
        description: str = "",
        is_default: bool = False,
        grants: Iterable[GrantTuple] = (),
        session: Session = None,  # type: ignore
    ) -> PermissionGroup:
        group = PermissionGroup(
            name=name, description=description, is_default=is_default, is_system=False
        )
        session.add(group)
        session.flush()
        self._replace_group_grants(group.id, grants, session=session)
        if is_default:
            self._clear_other_defaults(group.id, session=session)
        session.refresh(group)
        return group

    @begin_session
    def update_group(
        self,
        group_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        is_default: bool | None = None,
        grants: Iterable[GrantTuple] | None = None,
        session: Session = None,  # type: ignore
    ) -> PermissionGroup | None:
        group = session.get(PermissionGroup, group_id)
        if group is None:
            return None
        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        if is_default is not None:
            group.is_default = is_default
            if is_default:
                self._clear_other_defaults(group_id, session=session)
        if grants is not None:
            self._replace_group_grants(group_id, grants, session=session)
        session.flush()
        session.refresh(group)
        return group

    @begin_session
    def delete_group(
        self,
        group_id: int,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(delete(PermissionGroup).where(PermissionGroup.id == group_id))

    def _replace_group_grants(
        self, group_id: int, grants: Iterable[GrantTuple], *, session: Session
    ) -> None:
        session.execute(
            delete(PermissionGroupGrant).where(
                PermissionGroupGrant.group_id == group_id
            )
        )
        for entity, action, own_only in grants:
            session.add(
                PermissionGroupGrant(
                    group_id=group_id, entity=entity, action=action, own_only=own_only
                )
            )
        session.flush()

    def _clear_other_defaults(self, keep_id: int, *, session: Session) -> None:
        session.execute(
            update(PermissionGroup)
            .where(PermissionGroup.id != keep_id, PermissionGroup.is_default.is_(True))
            .values(is_default=False)
        )

    @begin_session
    def get_group_member_ids(
        self,
        group_id: int,
        session: Session = None,  # type: ignore
    ) -> list[int]:
        return list(
            session.scalars(
                select(User.id).where(User.permission_group_id == group_id)
            ).all()
        )

    # --- Admin CRUD: user membership + overrides ------------------------------

    @begin_session
    def set_user_group(
        self,
        user_id: int,
        group_id: int | None,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            update(User)
            .where(User.id == user_id)
            .values(permission_group_id=group_id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def replace_user_overrides(
        self,
        user_id: int,
        overrides: Iterable[OverrideTuple],
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(UserPermissionOverride).where(
                UserPermissionOverride.user_id == user_id
            )
        )
        for entity, action, granted, own_only in overrides:
            session.add(
                UserPermissionOverride(
                    user_id=user_id,
                    entity=entity,
                    action=action,
                    granted=granted,
                    own_only=own_only,
                )
            )

    # --- Admin CRUD: hidden entities ------------------------------------------

    @begin_session
    def get_hidden_entities(
        self,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> Sequence[HiddenEntity]:
        query = select(HiddenEntity)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        if group_id is not None:
            query = query.filter_by(group_id=group_id)
        return session.scalars(query).all()

    @begin_session
    def add_hidden_entity(
        self,
        entity: PermEntity,
        entity_id: int,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> None:
        # Idempotent: a repeated hide is a no-op rather than a unique violation.
        existing = session.scalar(
            select(HiddenEntity)
            .filter_by(
                entity=entity,
                entity_id=entity_id,
                user_id=user_id,
                group_id=group_id,
            )
            .limit(1)
        )
        if existing is None:
            session.add(
                HiddenEntity(
                    entity=entity,
                    entity_id=entity_id,
                    user_id=user_id,
                    group_id=group_id,
                )
            )

    @begin_session
    def remove_hidden_entity(
        self,
        entity: PermEntity,
        entity_id: int,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
        session: Session = None,  # type: ignore
    ) -> None:
        session.execute(
            delete(HiddenEntity).where(
                and_(
                    HiddenEntity.entity == entity,
                    HiddenEntity.entity_id == entity_id,
                    HiddenEntity.user_id == user_id,
                    HiddenEntity.group_id == group_id,
                )
            )
        )
