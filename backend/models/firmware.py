from functools import cached_property
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    BigInteger,
)

from models.base import BaseModel


class Firmware(BaseModel):
    __tablename__ = "firmware"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    platform_id = Column(
        Integer(), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False
    )

    file_name = Column(String(length=450), nullable=False)
    file_name_no_tags = Column(String(length=450), nullable=False)
    file_name_no_ext = Column(String(length=450), nullable=False)
    file_extension = Column(String(length=100), nullable=False)
    file_path = Column(String(length=1000), nullable=False)
    file_size_bytes = Column(BigInteger(), default=0, nullable=False)

    platform = relationship("Platform", lazy="selectin", back_populates="firmware")

    @property
    def platform_slug(self) -> str:
        return self.platform.slug

    @property
    def platform_fs_slug(self) -> str:
        return self.platform.fs_slug

    @property
    def platform_name(self) -> str:
        return self.platform.name

    @cached_property
    def full_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"

    def __repr__(self) -> str:
        return self.file_name
