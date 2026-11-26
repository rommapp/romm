import base64

import pytest

from models.collection import VirtualCollection


def _encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode()


def test_from_id_decodes_an_encoded_id():
    collection = VirtualCollection(name="Racing", type="genre")

    assert VirtualCollection.from_id(collection.id) == ("Racing", "genre")


@pytest.mark.parametrize(
    "id_",
    [
        "!!!",
        _encode("not json"),
        _encode("[]"),
        _encode('{"name": "Racing"}'),
        _encode('{"name": 1, "type": "genre"}'),
        "\udcff",
    ],
    ids=[
        "not base64",
        "not json",
        "not an object",
        "missing type",
        "non-string name",
        "not ascii",
    ],
)
def test_from_id_refuses_a_malformed_id(id_: str):
    with pytest.raises(ValueError, match="Invalid virtual collection id"):
        VirtualCollection.from_id(id_)
