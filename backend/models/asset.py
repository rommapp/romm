from sqlalchemy import Integer, Column, ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, backref
from functools import cached_property

from config import FRONT_LIBRARY_PATH
from .base import BaseModel


class BaseAsset(BaseModel):
    __abstract__ = True

    id = Column(Integer(), primary_key=True, autoincrement=True)

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

    rom_id = Column(Integer(), ForeignKey("roms.id", ondelete='CASCADE'), nullable=False)
    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True, backref=backref('saves', passive_deletes=True))

    platform_slug = Column(String(length=50), ForeignKey("platforms.slug", ondelete='CASCADE'), nullable=False)
    platform = relationship("Platform", lazy="joined", innerjoin=True, backref=backref('saves', passive_deletes=True))

class State(BaseAsset):
    from .rom import Rom

    __tablename__ = "states"

    rom_id = Column(Integer(), ForeignKey("roms.id", ondelete='CASCADE'), nullable=False)
    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True, backref=backref('states', passive_deletes=True))

    platform_slug = Column(String(length=50), ForeignKey("platforms.slug", ondelete='CASCADE'), nullable=False)
    platform = relationship("Platform", lazy="joined", innerjoin=True, backref=backref('states', passive_deletes=True))


class Screenshot(BaseAsset):
    from .rom import Rom

    __tablename__ = "screenshots"

    rom_id = Column(Integer(), ForeignKey("roms.id", ondelete='CASCADE'), nullable=False)
    rom: Mapped[Rom] = relationship("Rom", lazy="joined", innerjoin=True, backref=backref('screenshots', passive_deletes=True))


class Bios(BaseAsset):
    from .platform import Platform

    __tablename__ = "bios"

    platform_slug = Column(String(length=50), ForeignKey("platforms.slug", ondelete='CASCADE'), nullable=False)
    platform: Mapped[Platform] = relationship("Platform", lazy="joined", innerjoin=True, backref=backref('bios', passive_deletes=True))
