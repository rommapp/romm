import pytest

from config import _get_env_list, _get_env_set, parse_oidc_auth_params


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", {}),
        ('{"prompt": "select_account"}', {"prompt": "select_account"}),
        (
            '{"prompt": "login", "max_age": 0, "ui_locales": "fr en"}',
            {"prompt": "login", "max_age": "0", "ui_locales": "fr en"},
        ),
    ],
)
def test_parse_oidc_auth_params(raw, expected):
    assert parse_oidc_auth_params(raw) == expected


@pytest.mark.parametrize(
    "raw,message",
    [
        ("prompt=select_account", "not valid JSON"),
        ('["prompt"]', "must be a JSON object"),
        ('{"state": "fixed", "nonce": "fixed"}', "cannot set nonce, state"),
        ('{"prompt": "login", "redirect_uri": "https://x"}', "cannot set redirect_uri"),
        ('{"prompt": true}', "strings or integers: prompt"),
        ('{"claims": {"id_token": {}}}', "strings or integers: claims"),
    ],
)
def test_parse_oidc_auth_params_rejects(raw, message):
    with pytest.raises(ValueError, match=message):
        parse_oidc_auth_params(raw)
