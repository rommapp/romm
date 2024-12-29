from __future__ import annotations

from typing import TYPE_CHECKING

from models.base import BaseModel
from models.rom import Rom
from sqlalchemy import String, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

if TYPE_CHECKING:
    from models.firmware import Firmware


DEFAULT_COVER_ASPECT_RATIO = "2 / 3"


class Platform(BaseModel):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    igdb_id: Mapped[int | None]
    sgdb_id: Mapped[int | None]
    moby_id: Mapped[int | None]
    slug: Mapped[str] = mapped_column(String(length=50))
    fs_slug: Mapped[str] = mapped_column(String(length=50))
    name: Mapped[str] = mapped_column(String(length=400))
    custom_name: Mapped[str | None] = mapped_column(String(length=400), default="")
    category: Mapped[str | None] = mapped_column(String(length=50), default="")
    generation: Mapped[int | None]
    family_name: Mapped[str | None] = mapped_column(String(length=1000), default="")
    family_slug: Mapped[str | None] = mapped_column(String(length=1000), default="")
    url: Mapped[str | None] = mapped_column(String(length=1000), default="")
    url_logo: Mapped[str | None] = mapped_column(String(length=1000), default="")
    logo_path: Mapped[str | None] = mapped_column(String(length=1000), default="")

    roms: Mapped[list[Rom]] = relationship(back_populates="platform")
    firmware: Mapped[list[Firmware]] = relationship(
        lazy="selectin", back_populates="platform"
    )

    aspect_ratio: Mapped[str] = mapped_column(
        String(length=10), server_default=DEFAULT_COVER_ASPECT_RATIO
    )

    # This runs a subquery to get the count of roms for the platform
    rom_count = column_property(
        select(func.count(Rom.id)).where(Rom.platform_id == id).scalar_subquery()
    )

    def __repr__(self) -> str:
        return self.name
