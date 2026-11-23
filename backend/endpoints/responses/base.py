from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated, Final, Self

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, PlainSerializer

from utils.router import as_query_dependency


def _serialize_utc_datetime(dt: datetime) -> str:
    """Serialize datetime ensuring UTC timezone is always present."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


UTCDatetime = Annotated[datetime, PlainSerializer(_serialize_utc_datetime)]


# A string right after a field becomes its description in the OpenAPI schema.
API_SCHEMA_CONFIG: Final = ConfigDict(use_attribute_docstrings=True)


class BaseModel(PydanticBaseModel):
    """Base model for API request and response schemas."""

    model_config = API_SCHEMA_CONFIG


class PageParams(BaseModel):
    # Temporarily high until every app paginates
    limit: int = Field(50, ge=1, le=10_000)
    """The number of items to return, such as 72. Defaults to 50. The maximum is 10,000."""
    offset: int = Field(0, ge=0)
    """The number of items to skip. For example, 144 returns the third page of 72."""


PAGE_QUERY = as_query_dependency(PageParams)


class LimitOffsetPage[T: PydanticBaseModel](BaseModel):
    items: Sequence[T]
    total: int = Field(ge=0)
    """The number of items across all pages."""
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    """The number of items skipped before this page. For example, 144 for the third page of 72."""

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        params: PageParams,
        *,
        total: int,
    ) -> Self:
        return cls(items=items, total=total, limit=params.limit, offset=params.offset)
