import json

import pytest
from fastapi import HTTPException, status
from pydantic import BaseModel

from endpoints.fields import field_names, field_selection, project_page


class Item(BaseModel):
    id: int
    name: str
    summary: str | None
    igdb_metadata: dict[str, int] | None
    ss_metadata: dict[str, int] | None


GROUPS = {"provider": frozenset({"igdb_metadata", "ss_metadata"})}
select = field_selection(Item, groups=GROUPS)


def test_field_names_lists_every_field() -> None:
    assert field_names(Item) == {
        "id",
        "name",
        "summary",
        "igdb_metadata",
        "ss_metadata",
    }


def test_selection_is_none_without_fields() -> None:
    assert select(None) is None


def test_selection_always_includes_id() -> None:
    assert select("name") == frozenset({"id", "name"})


def test_selection_expands_a_group() -> None:
    assert select("name,@provider") == frozenset(
        {"id", "name", "igdb_metadata", "ss_metadata"}
    )


def test_selection_ignores_blanks_and_spaces() -> None:
    assert select(" name , ,summary ") == frozenset({"id", "name", "summary"})


@pytest.mark.parametrize("fields", ["nope", "name,@nope", "@name"])
def test_selection_rejects_unknown_names(fields: str) -> None:
    with pytest.raises(HTTPException) as error:
        select(fields)

    assert error.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class Page(BaseModel):
    items: list[Item]
    total: int


def test_project_page_keeps_only_the_selected_item_fields() -> None:
    page = Page(
        items=[
            Item(id=1, name="a", summary=None, igdb_metadata={"x": 1}, ss_metadata=None)
        ],
        total=1,
    )

    response = project_page(page, Item, frozenset({"id", "name"}))

    assert json.loads(bytes(response.body)) == {
        "items": [{"id": 1, "name": "a"}],
        "total": 1,
    }
    assert response.media_type == "application/json"
