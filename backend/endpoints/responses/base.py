from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel as PydanticBaseModel
from pydantic import PlainSerializer


def _serialize_utc_datetime(dt: datetime) -> str:
    """Serialize datetime ensuring UTC timezone is always present."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


UTCDatetime = Annotated[datetime, PlainSerializer(_serialize_utc_datetime)]


class BaseModel(PydanticBaseModel):
    """Base response model for all API responses."""

    pass
