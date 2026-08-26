from unittest.mock import MagicMock

from utils.update_hltb_api_url import (
    BASE_URL,
    BUILD_MANIFEST_REGEX,
    VALIDATION_SEARCH_TERM,
    candidate_search_routes,
    serves_game_search,
)

# Abridged from the real manifest: the search route, its /init sibling, and the
# unrelated routes a naive "/api/search" match would also accept.
MANIFEST = """
self.__BUILD_MANIFEST={"/api/forum/search":["x.js"],"/api/search/site":["y.js"],
"/api/search/site/init":["z.js"],"/api/stats/games":["w.js"],"/api/user":["v.js"]}
"""


def test_search_route_is_the_one_paired_with_a_session_mint():
    assert candidate_search_routes(MANIFEST) == ["/api/search/site"]


def test_a_route_without_an_init_sibling_is_not_a_candidate():
    assert candidate_search_routes('{"/api/search/site":[]}') == []


def test_search_like_candidates_are_tried_first():
    manifest = '{"/api/aaa":[],"/api/aaa/init":[],"/api/search/site":[],"/api/search/site/init":[]}'

    assert candidate_search_routes(manifest) == ["/api/search/site", "/api/aaa"]


def test_build_manifest_is_located_by_its_hashed_build_id():
    html = '<script src="/_next/static/xXfhvAtyEbN6z1HpYBEoi/_buildManifest.js" defer></script>'

    match = BUILD_MANIFEST_REGEX.search(html)

    assert match is not None
    assert match.group("path") == (
        "/_next/static/xXfhvAtyEbN6z1HpYBEoi/_buildManifest.js"
    )


def test_turbopack_chunks_are_not_mistaken_for_the_manifest():
    # The chunk names that replaced the old _app bundle must not match.
    html = '<script src="/_next/static/chunks/turbopack-3c7ykt0_ogp3s.js"></script>'

    assert BUILD_MANIFEST_REGEX.search(html) is None


def _client(session: dict, search_body: dict) -> MagicMock:
    """A stand-in HLTB whose /init and search responses the test controls."""
    client = MagicMock()
    client.get.return_value = _json_response(session)
    client.post.return_value = _json_response(search_body)
    return client


def _json_response(body: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


SESSION = {"token": "t", "hpKey": "ign_k", "hpVal": "v"}
GAME = {"game_id": 6909, "game_name": "Paper Mario"}


def test_a_route_serving_real_games_is_accepted():
    client = _client(SESSION, {"data": [GAME]})

    assert serves_game_search(client, BASE_URL, f"{BASE_URL}/api/search/site") is True


def test_a_route_that_mints_but_does_not_search_is_rejected():
    # The gap the /init-only check left open: session-backed, but not search.
    client = _client(SESSION, {"ok": True})

    assert serves_game_search(client, BASE_URL, f"{BASE_URL}/api/other") is False


def test_a_route_returning_non_game_results_is_rejected():
    client = _client(SESSION, {"data": [{"userId": 1, "name": "someone"}]})

    assert serves_game_search(client, BASE_URL, f"{BASE_URL}/api/other") is False


def test_a_route_returning_no_results_is_rejected():
    client = _client(SESSION, {"data": []})

    assert serves_game_search(client, BASE_URL, f"{BASE_URL}/api/other") is False


def test_an_incomplete_session_is_rejected_before_searching():
    client = _client({"token": "t"}, {"data": [GAME]})

    assert serves_game_search(client, BASE_URL, f"{BASE_URL}/api/search/site") is False
    client.post.assert_not_called()


def test_the_search_carries_the_session_and_honeypot_key():
    client = _client(SESSION, {"data": [GAME]})

    serves_game_search(client, BASE_URL, f"{BASE_URL}/api/search/site")

    kwargs = client.post.call_args.kwargs
    assert kwargs["headers"]["x-auth-token"] == "t"
    # HLTB requires the rotating honeypot key in the body, not just the headers.
    assert kwargs["json"]["ign_k"] == "v"
    assert kwargs["json"]["searchTerms"] == [VALIDATION_SEARCH_TERM]
