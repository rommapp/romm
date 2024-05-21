from models.base import BaseModel
from models.firmware import Firmware
from models.rom import Rom
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, relationship


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

    @property
    def rom_count(self) -> int:
        from handler.database import db_platform_handler

        return db_platform_handler.get_rom_count(self.id)

    def __repr__(self) -> str:
        return self.name
