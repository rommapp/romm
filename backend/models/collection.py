from __future__ import annotations

from functools import cached_property

from models.base import BaseModel
from models.user import User
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.database import CustomJSON


class Collection(BaseModel):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)

    path_cover_l: Mapped[str | None] = mapped_column(Text, default="")
    path_cover_s: Mapped[str | None] = mapped_column(Text, default="")

    url_cover: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL to cover image stored in IGDB"
    )

    roms: Mapped[set[int]] = mapped_column(
        CustomJSON(), default=[], doc="Rom id's that belong to this collection"
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_public: Mapped[bool] = mapped_column(default=False)
    user: Mapped[User] = relationship(lazy="joined", back_populates="collections")

    @property
    def user__username(self) -> str:
        return self.user.username

    @property
    def rom_count(self) -> int:
        return len(self.roms)

    @cached_property
    def has_cover(self) -> bool:
        return bool(self.path_cover_s or self.path_cover_l)

    @property
    def fs_resources_path(self) -> str:
        return f"collections/{str(self.id)}"

    def __repr__(self) -> str:
        return self.name
