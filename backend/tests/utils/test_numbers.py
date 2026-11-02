import pytest

from utils import float_or_none


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("80.9", 80.9),
        (52, 52.0),
        (None, None),
        ("", None),
        ("n/a", None),
        ("NaN", None),
        ("inf", None),
        (float("-inf"), None),
    ],
)
def test_float_or_none(value, expected):
    assert float_or_none(value) == expected
