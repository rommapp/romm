import pytest

from utils.hltb_search import HLTBSession, parse_session


def test_a_session_with_both_honeypot_fields_echoes_the_pair():
    assert HLTBSession("t", "ign_k", "v").honeypot() == ("ign_k", "v")


@pytest.mark.parametrize(
    "session",
    [
        pytest.param(HLTBSession("t"), id="token-only"),
        pytest.param(HLTBSession("t", "ign_k", None), id="key-without-val"),
        pytest.param(HLTBSession("t", None, "v"), id="val-without-key"),
    ],
)
def test_a_session_without_both_honeypot_fields_has_no_pair(session: HLTBSession):
    assert session.honeypot() is None


def test_parse_session_needs_only_a_token():
    session = parse_session({"token": "t"})

    assert session is not None
    assert session.token == "t"
    assert session.honeypot() is None


def test_parse_session_without_a_token_issues_none():
    assert parse_session({"hpKey": "ign_k", "hpVal": "v"}) is None
