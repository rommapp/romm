from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

FILE_NAME_MAX_LENGTH = 450
FILE_PATH_MAX_LENGTH = 1000
FILE_EXTENSION_MAX_LENGTH = 100


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseModel(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
