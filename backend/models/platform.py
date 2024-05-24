from sqlalchemy import Column, Integer, String, select, func
from sqlalchemy.orm import Mapped, relationship, column_property

from models.base import BaseModel
from models.rom import Rom
from models.firmware import Firmware


class Platform(BaseModel):
    __tablename__ = "platforms"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())
    moby_id: int = Column(Integer())
    slug: str = Column(String(length=50), nullable=False)
    fs_slug: str = Column(String(length=50), nullable=False)
    name: str = Column(String(length=400))
    logo_path: str = Column(String(length=1000), default="")

    roms: Mapped[set[Rom]] = relationship(
        "Rom", lazy="selectin", back_populates="platform"
    )
    firmware: Mapped[set[Firmware]] = relationship(
        "Firmware", lazy="selectin", back_populates="platform"
    )

    # This runs a subquery to get the count of roms for the platform
    rom_count = column_property(
        select(func.count(Rom.id)).where(Rom.platform_id == id).scalar_subquery()
    )

    def __repr__(self) -> str:
        return self.name
