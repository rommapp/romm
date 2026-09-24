from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated, Any, Self

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, PlainSerializer

from utils.router import as_query_dependency


def _serialize_utc_datetime(dt: datetime) -> str:
    """Serialize datetime ensuring UTC timezone is always present."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


UTCDatetime = Annotated[datetime, PlainSerializer(_serialize_utc_datetime)]


class BaseModel(PydanticBaseModel):
    """Base response model for all API responses."""

    pass


class PageParams(PydanticBaseModel):
    # Temporarily high until every app paginates
    limit: int = Field(50, ge=1, le=10_000, description="Page size limit")
    offset: int = Field(0, ge=0, description="Page offset")


PAGE_QUERY = as_query_dependency(PageParams)


class LimitOffsetPage[T: PydanticBaseModel](PydanticBaseModel):
    items: Sequence[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        params: PageParams,
        **kwargs: Any,
    ) -> Self:
        return cls(
            items=items,
            limit=params.limit,
            offset=params.offset,
            **kwargs,
        )
