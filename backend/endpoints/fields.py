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
    on_request: frozenset[str] = frozenset(),
) -> Callable[..., frozenset[str] | None]:
    """The dependency behind a `fields` query parameter.

    Args:
        schema: The model whose fields can be selected.
        groups: Names that stand for several fields, written `@name`.
        on_request: Fields a response holds only when they are named.

    Returns:
        A dependency giving the names to keep, or None without `fields`. It
        raises a 422 for a name `schema` lacks, or for a mix of names to keep
        and names to leave out.
    """
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
                    " part. To name what to leave out instead, start every name"
                    " with `-`, as in `-summary,-@group`; every other field is"
                    " returned"
                    f"{''.join(f', except `{f}`' for f in sorted(on_request))}."
                    " Names with and without `-` cannot be mixed."
                    " `id` is always included. A requested field with no value is"
                    " null, and a field left out is not in the response. Leave"
                    " `fields` out to get every field. A name the schema does not"
                    " have returns 422. The response schema lists every field, and"
                    " a response to `fields` holds only a subset of them."
                )
            ),
        ] = None,
    ) -> frozenset[str] | None:
        if fields is None:
            return None
        parts = [part for part in (p.strip() for p in fields.split(",")) if part]
        excluding = any(part.startswith("-") for part in parts)
        if excluding and not all(part.startswith("-") for part in parts):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="fields cannot mix names to include and names to leave out.",
            )
        names: set[str] = set()
        for part in parts:
            name = part.removeprefix("-")
            if name.startswith("@") and name[1:] in known_groups:
                names |= known_groups[name[1:]]
            else:
                names.add(name)
        unknown = names - allowed
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{schema.__name__} has no fields named {', '.join(sorted(unknown))}.",
            )
        selected = allowed - names - on_request if excluding else frozenset(names)
        return selected | {"id"}

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
