from utils.update_hltb_api_url import BUILD_MANIFEST_REGEX, candidate_search_routes

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
