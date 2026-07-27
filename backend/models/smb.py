from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.platform import Platform


class SmbAccessMode(enum.StrEnum):
    READ = "read"
    WRITE = "write"


class SmbUser(BaseModel):
    __tablename__ = "smb_users"
    __table_args__ = ({"extend_existing": True},)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    permissions: Mapped[list[SmbPlatformPermission]] = relationship(
        back_populates="smb_user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SmbPlatformPermission(BaseModel):
    __tablename__ = "smb_platform_permissions"
    __table_args__ = (
        UniqueConstraint(
            "smb_user_id",
            "platform_id",
            name="uq_smb_user_platform",
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    smb_user_id: Mapped[int] = mapped_column(
        ForeignKey("smb_users.id", ondelete="CASCADE"), index=True
    )
    platform_id: Mapped[int] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    access: Mapped[SmbAccessMode] = mapped_column(
        Enum(
            SmbAccessMode,
            native_enum=False,
            length=10,
            values_callable=lambda values: [value.value for value in values],
        )
    )

    smb_user: Mapped[SmbUser] = relationship(back_populates="permissions")
    platform: Mapped[Platform] = relationship(lazy="joined")
