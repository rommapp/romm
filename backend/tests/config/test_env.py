import pytest

from config import _get_env_list, _get_env_set


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ("", []),
        ("admins", ["admins"]),
        ("romm-admin,platform-admins", ["romm-admin", "platform-admins"]),
        (" romm-admin , ,platform-admins, ", ["romm-admin", "platform-admins"]),
        ("b,a,b", ["b", "a", "b"]),
    ],
)
def test_get_env_list(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("ROMM_TEST_LIST", raising=False)
    else:
        monkeypatch.setenv("ROMM_TEST_LIST", value)
    assert _get_env_list("ROMM_TEST_LIST") == expected


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


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, frozenset({"win", "dos"})),
        ("", frozenset({"win", "dos"})),
        ("n64", frozenset({"n64"})),
    ],
)
def test_get_env_set_fallback(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("ROMM_TEST_SET", raising=False)
    else:
        monkeypatch.setenv("ROMM_TEST_SET", value)
    assert _get_env_set("ROMM_TEST_SET", "win, dos") == expected
