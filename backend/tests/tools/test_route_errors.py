from fastapi import APIRouter
from tests.tools import route_errors_fixture as fixture
from tools.route_errors import UNREADABLE_STATUS, statuses, undocumented

FIXTURE = "tests.tools.route_errors_fixture"


def _raised(module: str, function: str) -> list[int]:
    return sorted(statuses(("func", module, function)))


def test_follows_a_module_level_http_exception():
    # login raises AuthCredentialsException from exceptions/auth_exceptions.py.
    assert 401 in _raised("endpoints.auth", "login")


def test_follows_a_custom_exception_class():
    # CollectionNotFoundInDatabaseException raises a 404 from its __init__.
    assert 404 in _raised("endpoints.collections", "get_collection")


def test_follows_a_handler_function_into_another_package():
    # The broker in handler/streaming raises 502 when it cannot reach a host.
    assert 502 in _raised("endpoints.streaming", "join_session")


def test_follows_an_http_exception_subclass():
    # ImportSpecUnavailable passes 503 to HTTPException.__init__ through super().
    sym = ("class", "handler.streaming.webstation", "ImportSpecUnavailable")
    assert statuses(sym) == {503}


def test_follows_a_dependency_in_a_default():
    assert _raised("tests.tools.route_errors_fixture", "route_with_a_default") == [409]


def test_follows_a_dependency_in_an_annotated_alias():
    assert _raised("tests.tools.route_errors_fixture", "route_with_an_alias") == [409]


def test_ignores_an_unrelated_function_with_the_same_name():
    # `os.path.join` must not resolve to the streaming `join` helper, which can 502.
    assert 502 not in _raised("endpoints.heartbeat", "get_setup_library_info")


def test_skips_a_gather_that_returns_exceptions():
    fixture = "tests.tools.route_errors_fixture"
    assert _raised(fixture, "route_that_gathers_errors") == []
    assert _raised(fixture, "route_that_gathers") == [409]


def test_skips_code_marked_as_ignored():
    fixture = "tests.tools.route_errors_fixture"
    assert _raised(fixture, "route_with_an_ignored_call") == []
    assert _raised(fixture, "route_with_an_ignored_trailing_call") == []


def test_counts_a_returned_error_response():
    assert _raised(FIXTURE, "route_that_returns_an_error") == [410]


def test_follows_a_status_passed_to_a_helper():
    assert _raised(FIXTURE, "route_that_forwards_a_status") == [423]


def test_reads_every_status_of_a_status_map():
    assert _raised(FIXTURE, "route_with_a_status_map") == [400, 502]


def test_reads_a_status_held_in_a_local_variable():
    assert _raised(FIXTURE, "route_with_a_status_variable") == [403]


def test_flags_a_status_it_cannot_read():
    assert _raised(FIXTURE, "route_with_an_unreadable_status") == [UNREADABLE_STATUS]


def test_skips_a_route_left_out_of_the_schema():
    router = APIRouter()
    router.get("/hidden", include_in_schema=False)(fixture.route_that_returns_an_error)
    assert undocumented(router.routes) == {}


def test_counts_422_as_documented_only_for_a_route_that_takes_input():
    router = APIRouter()
    router.get("/bare")(fixture.route_that_refuses_input)
    router.get("/input")(fixture.route_with_input_that_it_refuses)
    assert undocumented(router.routes) == {f"{FIXTURE}:route_that_refuses_input": [422]}
