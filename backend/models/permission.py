from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class PermEntity(enum.StrEnum):
    """Entity-type vocabulary for granular permissions.

    Mirrors the coarse scope domains (see ``handler/auth/constants.py``) so the
    grant matrix can be projected back onto the legacy ``Scope`` set without
    drift (see ``handler/auth/permissions_map.py``).
    """

    PLATFORMS = "platforms"
    ROMS = "roms"
    COLLECTIONS = "collections"
    FIRMWARE = "firmware"
    ASSETS = "assets"
    DEVICES = "devices"
    USERS = "users"
    TASKS = "tasks"
    LOGS = "logs"


class PermAction(enum.StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


def _str_enum(enum_cls: type[enum.StrEnum], length: int) -> Enum:
    """A VARCHAR-backed enum that stores the member ``value`` (lowercase).

    ``native_enum=False`` keeps the column portable across SQLite/MariaDB/
    Postgres and free of destructive ``ALTER TYPE`` when the vocabulary grows.
    ``values_callable`` stores the lowercase ``.value`` rather than the
    uppercase member name, matching the API/permission vocabulary.
    """

    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class PermissionGroup(BaseModel):
    """A named permission template that users belong to.

    A group carries a read/write/delete matrix over entity types (its
    ``grants``). Exactly one group is the server-wide default (``is_default``)
    applied to new users. ``is_system`` marks the auto-created legacy groups so
    the admin UI can warn before editing/deleting them.
    """

    __tablename__ = "permission_groups"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # Optional hex color (e.g. "#7c5cff") used by the admin UI to render the
    # group as a colored pill/dot. NULL falls back to a neutral tone.
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)

    grants: Mapped[list[PermissionGroupGrant]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PermissionGroupGrant(BaseModel):
    """A single ``(entity, action)`` capability granted by a group.

    Absence of a row means "not granted". ``own_only`` restricts the grant to
    entities the user owns (e.g. manage OWN collections/saves) -- the actual
    ownership check happens in the resolver, this flag only widens the coarse
    surface enough for the action to appear.
    """

    __tablename__ = "permission_group_grants"
    __table_args__ = (
        UniqueConstraint("group_id", "entity", "action", name="uq_group_grant"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="CASCADE"), index=True
    )
    entity: Mapped[PermEntity] = mapped_column(_str_enum(PermEntity, 20))
    action: Mapped[PermAction] = mapped_column(_str_enum(PermAction, 10))
    own_only: Mapped[bool] = mapped_column(Boolean, default=False)

    group: Mapped[PermissionGroup] = relationship(back_populates="grants")


class UserPermissionOverride(BaseModel):
    """A per-user add/revoke applied on top of the user's group matrix.

    ``granted=True`` adds a capability the group lacks; ``granted=False``
    revokes one the group provides. Absence of a row defers to the group.
    """

    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "entity", "action", name="uq_user_override"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    entity: Mapped[PermEntity] = mapped_column(_str_enum(PermEntity, 20))
    action: Mapped[PermAction] = mapped_column(_str_enum(PermAction, 10))
    granted: Mapped[bool] = mapped_column(Boolean)
    own_only: Mapped[bool] = mapped_column(Boolean, default=False)


class HiddenEntity(BaseModel):
    """An opt-out visibility row: hide a specific entity from a user or group.

    Exactly one principal is set (``user_id`` XOR ``group_id``). Practically
    only platforms and roms are hidden; firmware is excluded via the platform
    cascade computed at query time, never materialized here.
    """

    __tablename__ = "hidden_entities"
    __table_args__ = (
        UniqueConstraint(
            "entity", "entity_id", "user_id", "group_id", name="uq_hidden_entity"
        ),
        CheckConstraint(
            "(user_id IS NULL) <> (group_id IS NULL)",
            name="ck_hidden_one_principal",
        ),
        Index("idx_hidden_user_lookup", "user_id", "entity"),
        Index("idx_hidden_group_lookup", "group_id", "entity"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity: Mapped[PermEntity] = mapped_column(_str_enum(PermEntity, 20))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
