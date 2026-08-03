from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import FILE_NAME_MAX_LENGTH, BaseModel, utc_now

if TYPE_CHECKING:
    from models.platform import Platform
    from models.rom import Rom
    from models.user import User

USERNAME_SNAPSHOT_LENGTH = 255
PLATFORM_NAME_SNAPSHOT_LENGTH = 400
USER_AGENT_MAX_LENGTH = 512
# Long enough for an IPv6 address, including an IPv4-mapped suffix.
CLIENT_IP_MAX_LENGTH = 45

ANONYMOUS_USERNAME = "anonymous"


class DownloadSource(enum.StrEnum):
    """Where a download came from, derived from how the request authenticated."""

    WEBUI = "webui"
    BASIC_AUTH = "basic_auth"
    # Names a download source, not a credential.
    CLIENT_TOKEN = "client_token"  # nosec B105
    OAUTH = "oauth"
    ANONYMOUS = "anonymous"


class DownloadKind(enum.StrEnum):
    """Which download endpoint served the request."""

    # A whole rom: a single file, or a generated zip for multi-part roms.
    ROM = "rom"
    # One individual file of a rom (manual, soundtrack track, single disc...).
    FILE = "file"


def _portable_enum(enum_cls: type[enum.StrEnum], length: int) -> Enum:
    """VARCHAR-backed enum so the vocabulary stays portable across dialects."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class DownloadEvent(BaseModel):
    """One row per served download request.

    Feeds the admin download log and the aggregate counters used to find
    content nobody downloads.
    """

    __tablename__ = "download_events"
    __table_args__ = (
        Index("ix_download_events_rom_time", "rom_id", "downloaded_at"),
        Index("ix_download_events_user_time", "user_id", "downloaded_at"),
        Index("ix_download_events_time", "downloaded_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # All three FKs null out rather than cascade: the log has to outlive the
    # very deletions it exists to inform.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    rom_id: Mapped[int | None] = mapped_column(
        ForeignKey("roms.id", ondelete="SET NULL"), default=None
    )
    platform_id: Mapped[int | None] = mapped_column(
        ForeignKey("platforms.id", ondelete="SET NULL"), default=None
    )

    # Snapshots so a row still reads correctly once its FKs are gone.
    username: Mapped[str] = mapped_column(
        String(length=USERNAME_SNAPSHOT_LENGTH), default=ANONYMOUS_USERNAME
    )
    rom_name: Mapped[str] = mapped_column(
        String(length=FILE_NAME_MAX_LENGTH), default=""
    )
    platform_name: Mapped[str] = mapped_column(
        String(length=PLATFORM_NAME_SNAPSHOT_LENGTH), default=""
    )

    source: Mapped[DownloadSource] = mapped_column(
        _portable_enum(DownloadSource, 20), default=DownloadSource.ANONYMOUS
    )
    kind: Mapped[DownloadKind] = mapped_column(
        _portable_enum(DownloadKind, 10), default=DownloadKind.ROM
    )

    file_count: Mapped[int] = mapped_column(Integer(), default=1)
    size_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)

    client_ip: Mapped[str | None] = mapped_column(
        String(length=CLIENT_IP_MAX_LENGTH), default=None
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(length=USER_AGENT_MAX_LENGTH), default=None
    )

    downloaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utc_now
    )

    user: Mapped[User | None] = relationship(lazy="raise")
    rom: Mapped[Rom | None] = relationship(lazy="raise")
    platform: Mapped[Platform | None] = relationship(lazy="raise")
