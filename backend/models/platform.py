from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from models.base import BaseModel
from models.rom import Rom

if TYPE_CHECKING:
    from models.firmware import Firmware


DEFAULT_COVER_ASPECT_RATIO = "2 / 3"


class Platform(BaseModel):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    igdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    sgdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    moby_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    ss_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    ra_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    launchbox_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    hasheous_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    tgdb_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    flashpoint_id: Mapped[int | None] = mapped_column(Integer(), default=None)
    igdb_slug: Mapped[str | None] = mapped_column(String(length=100), default=None)
    moby_slug: Mapped[str | None] = mapped_column(String(length=100), default=None)
    hltb_slug: Mapped[str | None] = mapped_column(String(length=100), default=None)
    slug: Mapped[str] = mapped_column(String(length=100))
    fs_slug: Mapped[str] = mapped_column(String(length=100))
    name: Mapped[str] = mapped_column(String(length=400))
    custom_name: Mapped[str | None] = mapped_column(String(length=400), default="")
    category: Mapped[str | None] = mapped_column(String(length=100), default="")
    generation: Mapped[int | None]
    family_name: Mapped[str | None] = mapped_column(String(length=1000), default="")
    family_slug: Mapped[str | None] = mapped_column(String(length=1000), default="")
    url: Mapped[str | None] = mapped_column(String(length=1000), default="")
    url_logo: Mapped[str | None] = mapped_column(String(length=1000), default="")

    roms: Mapped[list[Rom]] = relationship(lazy="raise", back_populates="platform")
    firmware: Mapped[list[Firmware]] = relationship(
        lazy="raise", back_populates="platform"
    )

    aspect_ratio: Mapped[str] = mapped_column(
        String(length=10), server_default=DEFAULT_COVER_ASPECT_RATIO
    )

    # Temp column to store the old slug from the migration
    temp_old_slug: Mapped[str | None] = mapped_column(String(length=100), default=None)

    # This runs a subquery to get the count of roms for the platform
    rom_count = column_property(
        select(func.count(Rom.id))
        .where(Rom.platform_id == id)
        .correlate_except(Rom)
        .scalar_subquery()
    )

    fs_size_bytes: Mapped[int] = column_property(
        select(func.coalesce(func.sum(Rom.fs_size_bytes), 0))
        .where(Rom.platform_id == id)
        .correlate_except(Rom)
        .scalar_subquery()
    )

    missing_from_fs: Mapped[bool] = mapped_column(default=False, nullable=False)

    @property
    def is_unidentified(self) -> bool:
        return (
            not self.igdb_id
            and not self.moby_id
            and not self.ss_id
            and not self.launchbox_id
            and not self.ra_id
            and not self.hasheous_id
        )

    @property
    def is_identified(self) -> bool:
        return not self.is_unidentified

    def __repr__(self) -> str:
        return f"{self.name} ({self.slug}) ({self.id})"
