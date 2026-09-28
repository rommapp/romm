import pytest

from utils.hltb_search import HLTB_BASE_URL, HLTBSession, parse_session, search_headers


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


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"hpKey": "ign_k", "hpVal": "v"}, id="no-token"),
        pytest.param([{"token": "t"}], id="not-a-json-object"),
    ],
)
def test_parse_session_without_a_token_object_issues_none(data: object):
    assert parse_session(data) is None


def test_search_headers_carry_the_origin_a_browser_sends():
    headers = search_headers(HLTB_BASE_URL, HLTBSession("t"))

    assert headers["Origin"] == HLTB_BASE_URL
    assert headers["Referer"] == HLTB_BASE_URL
