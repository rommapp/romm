from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import FRONTEND_RESOURCES_PATH
from models.base import BaseModel
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.rom import Rom
    from models.user import User


class Collection(BaseModel):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    path_cover_l: Mapped[str | None] = mapped_column(Text, default="")
    path_cover_s: Mapped[str | None] = mapped_column(Text, default="")
    url_cover: Mapped[str | None] = mapped_column(
        Text, default="", doc="URL of cover pulled from metadata providers"
    )

    roms: Mapped[list["Rom"]] = relationship(
        "Rom",
        secondary="collections_roms",
        collection_class=set,
        back_populates="collections",
        lazy="raise",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship(lazy="joined", back_populates="collections")

    @property
    def user__username(self) -> str:
        return self.user.username

    @property
    def rom_ids(self) -> list[int]:
        return [r.id for r in self.roms]

    @property
    def rom_count(self) -> int:
        return len(self.roms)

    @property
    def fs_resources_path(self) -> str:
        return f"collections/{str(self.id)}"

    @property
    def path_cover_small(self) -> str | None:
        return (
            f"{FRONTEND_RESOURCES_PATH}/{self.path_cover_s}?ts={self.updated_at}"
            if self.path_cover_s
            else None
        )

    @property
    def path_cover_large(self) -> str | None:
        return (
            f"{FRONTEND_RESOURCES_PATH}/{self.path_cover_l}?ts={self.updated_at}"
            if self.path_cover_l
            else None
        )

    @property
    def path_covers_small(self) -> list[str]:
        return [
            f"{FRONTEND_RESOURCES_PATH}/{r.path_cover_s}?ts={self.updated_at}"
            for r in self.roms
            if r.path_cover_s
        ]

    @property
    def path_covers_large(self) -> list[str]:
        return [
            f"{FRONTEND_RESOURCES_PATH}/{r.path_cover_l}?ts={self.updated_at}"
            for r in self.roms
            if r.path_cover_l
        ]

    def __repr__(self) -> str:
        return self.name


class CollectionRom(BaseModel):
    __tablename__ = "collections_roms"

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        UniqueConstraint("collection_id", "rom_id", name="unique_collection_rom"),
    )


class VirtualCollection(BaseModel):
    __tablename__ = "virtual_collections"

    name: Mapped[str] = mapped_column(String(length=400), primary_key=True)
    type: Mapped[str] = mapped_column(String(length=50), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    path_covers_s: Mapped[list[str]] = mapped_column(CustomJSON(), default=[])
    path_covers_l: Mapped[list[str]] = mapped_column(CustomJSON(), default=[])

    rom_ids: Mapped[set[int]] = mapped_column(
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
        return len(self.rom_ids)

    @property
    def path_cover_small(self) -> str | None:
        return None

    @property
    def path_cover_large(self) -> str | None:
        return None

    @property
    def path_covers_small(self) -> list[str]:
        return [
            f"{FRONTEND_RESOURCES_PATH}/{cover}?ts={self.updated_at}"
            for cover in self.path_covers_s
            if cover
        ]

    @property
    def path_covers_large(self) -> list[str]:
        return [
            f"{FRONTEND_RESOURCES_PATH}/{cover}?ts={self.updated_at}"
            for cover in self.path_covers_l
            if cover
        ]

    __table_args__ = (
        UniqueConstraint(
            "name",
            "type",
            name="unique_virtual_collection_name_type",
        ),
    )


SMART_COLLECTION_MAX_COVERS = 5


class SmartCollection(BaseModel):
    __tablename__ = "smart_collections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)
    rom_count: Mapped[int] = mapped_column(default=0)
    rom_ids: Mapped[list[int]] = mapped_column(
        CustomJSON(), default=[], doc="Rom IDs that belong to this smart collection"
    )
    path_covers_small: Mapped[list[str]] = mapped_column(CustomJSON(), default=[])
    path_covers_large: Mapped[list[str]] = mapped_column(CustomJSON(), default=[])

    filter_criteria: Mapped[dict[str, Any]] = mapped_column(
        CustomJSON(),
        default=dict,
        doc="JSON object containing all filter criteria for the smart collection",
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship(
        lazy="joined", back_populates="smart_collections"
    )

    def update_properties(self, user_id: int) -> "SmartCollection":
        from handler.database import db_collection_handler

        roms = db_collection_handler.get_smart_collection_roms(self, user_id)

        roms_with_small_covers = [r for r in roms if r.path_cover_s][
            :SMART_COLLECTION_MAX_COVERS
        ]
        roms_with_large_covers = [r for r in roms if r.path_cover_l][
            :SMART_COLLECTION_MAX_COVERS
        ]

        return db_collection_handler.update_smart_collection(
            self.id,
            {
                "rom_count": len(roms),
                "rom_ids": [rom.id for rom in roms],
                "path_covers_small": [
                    f"{FRONTEND_RESOURCES_PATH}/{r.path_cover_s}?ts={self.updated_at}"
                    for r in roms_with_small_covers
                ],
                "path_covers_large": [
                    f"{FRONTEND_RESOURCES_PATH}/{r.path_cover_l}?ts={self.updated_at}"
                    for r in roms_with_large_covers
                ],
            },
        )

    @property
    def user__username(self) -> str:
        return self.user.username

    @property
    def path_cover_small(self) -> str | None:
        return None

    @property
    def path_cover_large(self) -> str | None:
        return None

    @property
    def filter_summary(self) -> str:
        return json.dumps(self.filter_criteria)

    def __repr__(self) -> str:
        return self.name
