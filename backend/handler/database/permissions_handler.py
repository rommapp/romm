from collections.abc import Iterable, Sequence
from typing import Final, NamedTuple

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from handler.auth.rom_visibility import RomVisibilityFilter, VisibilityColumns
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    PermissionGroup,
    PermissionGroupGrant,
    SystemGroupKey,
    UserPermissionOverride,
)
from models.user import Role, User

from .base_handler import DBBaseHandler

# (entity, action, own_only)
GrantTuple = tuple[PermEntity, PermAction, bool]
# (entity, action, granted, own_only)
OverrideTuple = tuple[PermEntity, PermAction, bool, bool]


class GroupPolicy(NamedTuple):
    """What the resolver reads off a group, without loading it as an object."""

    age_limit: int | None
    hide_unrated_roms: bool
    grants: list[GrantTuple]


# The policy of a missing group: no grants and no age rule.
NO_GROUP_POLICY: Final = GroupPolicy(age_limit=None, hide_unrated_roms=False, grants=[])


class DBPermissionsHandler(DBBaseHandler):
    """Read and admin-write access to the granular permission model.

    The read helpers (`get_default_group_id`, `get_group_policy`,
    `get_user_overrides`, `get_hidden_entity_ids`) feed the per-request resolver;
    the rest is the admin CRUD surface for managing groups, memberships,
    overrides and hidden entities.
    """

    @begin_session
    def get_default_group_id(
        self,
        session: Session = INJECTED_SESSION,
    ) -> int | None:
        return session.scalar(
            select(PermissionGroup.id).filter_by(is_default=True).limit(1)
        )

    @begin_session
    def get_group_policy(
        self,
        group_id: int | None,
        session: Session = INJECTED_SESSION,
    ) -> GroupPolicy:
        """A group's grants and age settings in one query; empty when it's gone."""
        if group_id is None:
            return NO_GROUP_POLICY
        rows = session.execute(
            select(
                PermissionGroup.age_limit,
                PermissionGroup.hide_unrated_roms,
                PermissionGroupGrant.entity,
                PermissionGroupGrant.action,
                PermissionGroupGrant.own_only,
            )
            .outerjoin(
                PermissionGroupGrant,
                PermissionGroupGrant.group_id == PermissionGroup.id,
            )
            .where(PermissionGroup.id == group_id)
        ).all()
        if not rows:
            return NO_GROUP_POLICY
        return GroupPolicy(
            age_limit=rows[0].age_limit,
            hide_unrated_roms=rows[0].hide_unrated_roms,
            grants=[
                (row.entity, row.action, row.own_only)
                for row in rows
                if row.entity is not None
            ],
        )

    @begin_session
    def get_user_overrides(
        self,
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[UserPermissionOverride]:
        return session.scalars(
            select(UserPermissionOverride).filter_by(user_id=user_id)
        ).all()

    @begin_session
    def get_rom_audience(
        self,
        rom: VisibilityColumns,
        session: Session = INJECTED_SESSION,
    ) -> list[int]:
        """Ids of the enabled users who can see `rom`, in four queries."""
        users = session.execute(
            select(
                User.id,
                User.role,
                User.permission_group_id,
                User.age_limit,
                User.hide_unrated_roms,
            )
            .where(User.enabled.is_(True))
            .order_by(User.id)
        ).all()
        default_group_id = self.get_default_group_id(session=session)
        groups = {
            row.id: row
            for row in session.execute(
                select(
                    PermissionGroup.id,
                    PermissionGroup.age_limit,
                    PermissionGroup.hide_unrated_roms,
                )
            ).all()
        }
        hides = session.execute(
            select(
                HiddenEntity.entity, HiddenEntity.user_id, HiddenEntity.group_id
            ).where(
                or_(
                    and_(
                        HiddenEntity.entity == PermEntity.ROMS,
                        HiddenEntity.entity_id == rom.id,
                    ),
                    and_(
                        HiddenEntity.entity == PermEntity.PLATFORMS,
                        HiddenEntity.entity_id == rom.platform_id,
                    ),
                )
            )
        ).all()

        audience = []
        for user in users:
            if user.role == Role.ADMIN:
                audience.append(user.id)
                continue
            group_id = user.permission_group_id
            if group_id is None:
                group_id = default_group_id
            group = groups.get(group_id) if group_id is not None else None
            hidden = {
                hide.entity
                for hide in hides
                if hide.user_id == user.id
                or (group_id is not None and hide.group_id == group_id)
            }
            # The user's own age settings replace the group's; NULL inherits.
            visibility = RomVisibilityFilter(
                hidden_platform_ids=(
                    frozenset({rom.platform_id})
                    if PermEntity.PLATFORMS in hidden
                    else frozenset()
                ),
                hidden_rom_ids=(
                    frozenset({rom.id}) if PermEntity.ROMS in hidden else frozenset()
                ),
                age_limit=(
                    user.age_limit
                    if user.age_limit is not None
                    else (group.age_limit if group else None)
                ),
                hide_unrated_roms=(
                    user.hide_unrated_roms
                    if user.hide_unrated_roms is not None
                    else bool(group and group.hide_unrated_roms)
                ),
            )
            if visibility.allows(rom):
                audience.append(user.id)
        return audience

    @begin_session
    def get_hidden_entity_ids(
        self,
        entity: PermEntity,
        user_id: int | None,
        group_id: int | None,
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
    ) -> PermissionGroup | None:
        return session.get(PermissionGroup, group_id)

    @begin_session
    def get_group_by_name(
        self,
        name: str,
        session: Session = INJECTED_SESSION,
    ) -> PermissionGroup | None:
        return session.scalar(select(PermissionGroup).filter_by(name=name).limit(1))

    @begin_session
    def get_system_group(
        self,
        key: SystemGroupKey,
        session: Session = INJECTED_SESSION,
    ) -> PermissionGroup | None:
        return session.scalar(select(PermissionGroup).filter_by(system_key=key))

    @begin_session
    def create_group(
        self,
        name: str,
        description: str = "",
        is_default: bool = False,
        color: str | None = None,
        grants: Iterable[GrantTuple] = (),
        age_limit: int | None = None,
        hide_unrated_roms: bool = False,
        session: Session = INJECTED_SESSION,
    ) -> PermissionGroup:
        group = PermissionGroup(
            name=name,
            description=description,
            is_default=is_default,
            color=color,
            age_limit=age_limit,
            hide_unrated_roms=hide_unrated_roms,
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
        color: str | None = None,
        grants: Iterable[GrantTuple] | None = None,
        set_age_settings: bool = False,
        age_limit: int | None = None,
        hide_unrated_roms: bool = False,
        session: Session = INJECTED_SESSION,
    ) -> PermissionGroup | None:
        """Change the given fields; the age settings apply only with
        `set_age_settings`, since a None `age_limit` there clears the limit."""
        group = session.get(PermissionGroup, group_id)
        if group is None:
            return None
        if set_age_settings:
            group.age_limit = age_limit
            group.hide_unrated_roms = hide_unrated_roms
        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        if color is not None:
            group.color = color
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
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
    ) -> list[int]:
        return list(
            session.scalars(
                select(User.id).where(User.permission_group_id == group_id)
            ).all()
        )

    @begin_session
    def get_group_follower_ids(
        self,
        group_id: int,
        session: Session = INJECTED_SESSION,
    ) -> list[int]:
        """Users whose permissions come from the group: its members, plus every
        user without a group when it is the default."""
        is_default = (
            select(PermissionGroup.is_default)
            .where(PermissionGroup.id == group_id)
            .scalar_subquery()
        )
        return list(
            session.scalars(
                select(User.id).where(
                    or_(
                        User.permission_group_id == group_id,
                        and_(User.permission_group_id.is_(None), is_default.is_(True)),
                    )
                )
            ).all()
        )

    # --- Admin CRUD: user membership + overrides ------------------------------

    @begin_session
    def set_user_group(
        self,
        user_id: int,
        group_id: int | None,
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
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
        session: Session = INJECTED_SESSION,
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
