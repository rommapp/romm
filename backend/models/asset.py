from sqlalchemy import Integer, Column, ForeignKey, String
from sqlalchemy.orm import relationship, Mapped
from functools import cached_property

from config import FRONT_LIBRARY_PATH
from .base import BaseModel


class BaseAsset(BaseModel):
    from .rom import Rom

    __abstract__ = True

    id = Column(Integer(), primary_key=True, autoincrement=True)
    rom_id = Column(Integer(), ForeignKey("roms.id"), nullable=True)

    file_name = Column(String(length=450), nullable=False)
    file_name_no_tags = Column(String(length=450), nullable=False)
    file_extension = Column(String(length=10), nullable=False)
    file_path = Column(String(length=1000), nullable=False)
    file_size_bytes = Column(Integer(), default=0, nullable=False)

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    @cached_property
    def download_path(self) -> str:
        return f"{FRONT_LIBRARY_PATH}/{self.full_path}"


class Save(BaseAsset):
    from .rom import Rom

    __tablename__ = "saves"

    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True)


class State(BaseAsset):
    from .rom import Rom

    __tablename__ = "states"

    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True)


class Screenshot(BaseAsset):
    from .rom import Rom

    __tablename__ = "screenshots"

    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True)
