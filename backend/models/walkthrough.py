from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from handler.walkthrough_handler import WalkthroughFormat, WalkthroughSource
from models.base import BaseModel


class Walkthrough(BaseModel):
    __tablename__ = "walkthroughs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(length=1000))
    title: Mapped[str | None] = mapped_column(String(length=500), default=None)
    author: Mapped[str | None] = mapped_column(String(length=250), default=None)
    source: Mapped[WalkthroughSource] = mapped_column(
        Enum(WalkthroughSource, values_callable=lambda e: [item.value for item in e])
    )
    format: Mapped[WalkthroughFormat] = mapped_column(
        Enum(WalkthroughFormat, values_callable=lambda e: [item.value for item in e])
    )
    file_path: Mapped[str | None] = mapped_column(String(length=1000), default=None)
    content: Mapped[str] = mapped_column(Text().with_variant(mysql.LONGTEXT(), "mysql"))

    rom: Mapped["Rom"] = relationship(back_populates="walkthroughs")
