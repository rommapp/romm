import pytest

from config import _get_env_set


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, frozenset()),
        ("", frozenset()),
        ("admins", frozenset({"admins"})),
        ("romm-admin,platform-admins", frozenset({"romm-admin", "platform-admins"})),
        (
            " romm-admin , ,platform-admins, ",
            frozenset({"romm-admin", "platform-admins"}),
        ),
    ],
)
def test_get_env_set(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("ROMM_TEST_SET", raising=False)
    else:
        monkeypatch.setenv("ROMM_TEST_SET", value)
    assert _get_env_set("ROMM_TEST_SET") == expected
