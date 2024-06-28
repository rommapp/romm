from datetime import datetime

from models.base import BaseModel
from models.rom import Rom
from sqlalchemy import DateTime, String, Text, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship


class Collection(BaseModel):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)
    logo_path: Mapped[str | None] = mapped_column(String(length=1000), default="")

    roms: Mapped[list["Rom"]] = relationship(back_populates="platform")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # This runs a subquery to get the count of roms for the platform
    rom_count = column_property(
        select(func.count(Rom.id)).where(Rom.platform_id == id).scalar_subquery()
    )

    def __repr__(self) -> str:
        return self.name
