from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship, Mapped

from config import DEFAULT_PATH_COVER_S
from .base import BaseModel


class Platform(BaseModel):
    from .rom import Rom
    from .assets import Save, State

    __tablename__ = "platforms"

    slug: str = Column(String(length=50), primary_key=True)
    fs_slug: str = Column(String(length=50), nullable=False)
    name: str = Column(String(length=400))
    igdb_id: int = Column(Integer())
    sgdb_id: int = Column(Integer())
    logo_path: str = Column(String(length=1000), default=DEFAULT_PATH_COVER_S)

    roms: Mapped[set[Rom]] = relationship(
        "Rom", lazy="selectin", back_populates="platform"
    )
    saves: Mapped[set[Save]] = relationship(
        "Save", lazy="selectin", back_populates="platform"
    )
    states: Mapped[set[State]] = relationship(
        "State", lazy="selectin", back_populates="platform"
    )

    ### DEPRECATED ###
    n_roms: int = Column(Integer, default=0)
    ### DEPRECATED ###

    @property
    def rom_count(self) -> int:
        from handler import dbh

        return dbh.get_rom_count(self.slug)

    def __repr__(self) -> str:
        return self.name
