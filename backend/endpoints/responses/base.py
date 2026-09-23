from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated, Any, Self, cast

from fastapi_pagination.bases import AbstractParams
from fastapi_pagination.limit_offset import LimitOffsetPage
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


class TypedLimitOffsetPage[T: PydanticBaseModel](LimitOffsetPage[T]):
    """LimitOffsetPage whose `create` is typed to return the subclass it builds."""

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        params: AbstractParams,
        *,
        total: int | None = None,
        **kwargs: Any,
    ) -> Self:
        return cast(Self, super().create(items, params, total=total, **kwargs))
