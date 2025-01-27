from __future__ import annotations

import base64
import json
from functools import cached_property

from models.base import BaseModel
from models.user import User
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.database import CustomJSON


class Collection(BaseModel):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)
    path_cover_l: Mapped[str | None] = mapped_column(Text, default="")
    path_cover_s: Mapped[str | None] = mapped_column(Text, default="")
    url_cover: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL to cover image stored in IGDB"
    )

    roms: Mapped[set[int]] = mapped_column(
        CustomJSON(), default=[], doc="Rom IDs that belong to this collection"
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
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


class VirtualCollection(BaseModel):
    __tablename__ = "virtual_collections"

    name: Mapped[str] = mapped_column(String(length=400), primary_key=True)
    type: Mapped[str] = mapped_column(String(length=50), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)

    roms: Mapped[set[int]] = mapped_column(
        CustomJSON(), default=[], doc="Rom IDs that belong to this collection"
    )

    @property
    def id(self) -> str:
        # Create a reversible encoded ID
        data = json.dumps({"name": self.name, "type": self.type})
        return base64.urlsafe_b64encode(data.encode()).decode()

    @classmethod
    def from_id(cls, id_: str):
        data = json.loads(base64.urlsafe_b64decode(id_).decode())
        return data["name"], data["type"]

    @property
    def rom_count(self) -> int:
        return len(self.roms)

    __table_args__ = (
        UniqueConstraint(
            "name",
            "type",
            name="unique_virtual_collection_name_type",
        ),
    )
