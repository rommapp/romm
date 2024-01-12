from config import DEFAULT_PATH_COVER_S
from models.base import BaseModel
from models.rom import Rom
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, relationship


class Platform(BaseModel):
    __tablename__ = "platforms"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())
    slug: str = Column(String(length=50))
    fs_slug: str = Column(String(length=50), nullable=False)
    name: str = Column(String(length=400))
    logo_path: str = Column(String(length=1000), default=DEFAULT_PATH_COVER_S)

    roms: Mapped[set[Rom]] = relationship(
        "Rom", lazy="selectin", back_populates="platform"
    )

    @property
    def rom_count(self) -> int:
        from handler import dbh

        return dbh.get_rom_count(self.id)

    def __repr__(self) -> str:
        return self.name
