from collections.abc import Callable, Mapping
from functools import cache
from typing import Annotated

from fastapi import HTTPException, Query, Response, status
from pydantic import BaseModel


@cache
def field_names(schema: type[BaseModel]) -> frozenset[str]:
    """Every field `schema` serves, computed ones included."""
    return frozenset(schema.model_fields) | frozenset(schema.model_computed_fields)


def field_selection(
    schema: type[BaseModel],
    *,
    groups: Mapping[str, frozenset[str]] | None = None,
) -> Callable[..., frozenset[str] | None]:
    """The dependency behind a `fields` query parameter: the names to keep, or None, with a 422 for a name `schema` lacks."""
    allowed = field_names(schema)
    known_groups = groups or {}

    def dependency(
        fields: Annotated[
            str | None,
            Query(
                description=(
                    f"Comma-separated names of the `{schema.__name__}` fields to"
                    " return, or `@` followed by a group name to return every field"
                    f" in the group. Groups: {', '.join(f'`@{g}`' for g in known_groups) or 'none'}."
                    " Name only the fields you read to get a much smaller response;"
                    " the raw provider metadata, `@provider_metadata`, is the largest"
                    " part. `id` is always included. A requested field with no value is"
                    " null, and a field left out is not in the response. Leave"
                    " `fields` out to get every field. A name the schema does not"
                    " have returns 422."
                )
            ),
        ] = None,
    ) -> frozenset[str] | None:
        if fields is None:
            return None
        names: set[str] = set()
        for name in (part.strip() for part in fields.split(",")):
            if name.startswith("@") and name[1:] in known_groups:
                names |= known_groups[name[1:]]
            elif name:
                names.add(name)
        unknown = names - allowed
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{schema.__name__} has no fields named {', '.join(sorted(unknown))}.",
            )
        return frozenset(names) | {"id"}

    return dependency


def project_page(
    page: BaseModel, schema: type[BaseModel], selection: frozenset[str]
) -> Response:
    """A JSON response of `page` whose items keep only the `selection` fields of `schema`."""
    drop = set(field_names(schema) - selection)
    return Response(
        page.model_dump_json(by_alias=True, exclude={"items": {"__all__": drop}}),
        media_type="application/json",
    )
