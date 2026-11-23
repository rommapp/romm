import pytest

from utils.facets import facet_names


@pytest.mark.parametrize(
    ("column", "names"),
    [
        (["RPG", " Action "], ["RPG", "Action"]),
        ([{"id": 1, "name": "RPG"}, {"name": " Action "}], ["RPG", "Action"]),
        (["RPG", None, 42, {"id": 1}, {"name": None}, {"name": "  "}], ["RPG"]),
        ("RPG", ["RPG"]),
        ("  ", []),
        (None, []),
        (42, []),
        ({"id": 1, "name": "RPG"}, []),
    ],
)
def test_facet_names(column, names):
    assert facet_names(column) == names
