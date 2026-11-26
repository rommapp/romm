from fastapi import APIRouter, status
from tests.tools import route_errors_fixture as fixture_routes
from tools.route_errors import UNREADABLE_STATUS, stale, statuses, undocumented

from decorators.auth import SCOPE_ERRORS

FIXTURE = fixture_routes.__name__


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
    assert _raised(FIXTURE, "route_with_a_default") == [409]


def test_follows_a_dependency_in_an_annotated_alias():
    assert _raised(FIXTURE, "route_with_an_alias") == [409]


def test_ignores_an_unrelated_function_with_the_same_name():
    # `os.path.join` must not resolve to the streaming `join` helper, which can 502.
    assert 502 not in _raised("endpoints.heartbeat", "get_setup_library_info")


def test_skips_a_gather_that_returns_exceptions():
    assert _raised(FIXTURE, "route_that_gathers_errors") == []
    assert _raised(FIXTURE, "route_that_gathers") == [409]


def test_skips_code_marked_as_ignored():
    assert _raised(FIXTURE, "route_with_an_ignored_call") == []
    assert _raised(FIXTURE, "route_with_an_ignored_trailing_call") == []


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
    router.get("/hidden", include_in_schema=False)(
        fixture_routes.route_that_returns_an_error
    )
    assert undocumented(router.routes) == {}


def test_counts_422_as_documented_only_for_a_route_that_takes_input():
    router = APIRouter()
    router.get("/bare")(fixture_routes.route_that_refuses_input)
    router.get("/input")(fixture_routes.route_with_input_that_it_refuses)
    assert undocumented(router.routes) == {f"{FIXTURE}:route_that_refuses_input": [422]}


def test_follows_a_function_run_in_a_thread():
    assert _raised(FIXTURE, "route_that_offloads") == [504]


def test_skips_a_try_that_swallows_errors_but_keeps_its_responses():
    assert _raised(FIXTURE, "route_that_swallows_errors") == [410]
    assert _raised(FIXTURE, "route_that_reraises") == [409]


def test_reads_declared_statuses_in_place_of_the_line():
    assert _raised(FIXTURE, "route_with_a_declared_status") == [502]
    assert _raised(FIXTURE, "route_with_a_declared_status_above") == [502, 503]


def test_flags_a_documented_status_the_route_cannot_raise():
    router = APIRouter()
    router.get(
        "/stale",
        responses={
            status.HTTP_404_NOT_FOUND: {},
            status.HTTP_409_CONFLICT: {"description": "Raised."},
            status.HTTP_410_GONE: {"description": "No longer raised."},
        },
    )(fixture_routes.route_with_a_default)
    assert stale(router.routes) == {f"{FIXTURE}:route_with_a_default": [404, 410]}


def test_counts_a_status_range_or_default_as_documented():
    router = APIRouter()
    router.get("/range", responses={"4XX": {"description": "A client error."}})(
        fixture_routes.route_with_a_default
    )
    router.get("/default", responses={"default": {"description": "An error."}})(
        fixture_routes.route_with_an_alias
    )
    assert undocumented(router.routes) == {}
    assert stale(router.routes) == {}


def test_respects_markers_in_a_try_that_swallows_errors():
    assert _raised(FIXTURE, "route_with_markers_in_a_swallowing_try") == [502]


def test_keeps_an_http_error_an_earlier_handler_reraises():
    assert _raised(FIXTURE, "route_that_reraises_http_errors_first") == [409]


def test_flags_a_status_taken_from_the_request():
    router = APIRouter()
    router.get("/echo")(fixture_routes.route_with_a_status_from_its_input)
    assert undocumented(router.routes) == {
        f"{FIXTURE}:route_with_a_status_from_its_input": [UNREADABLE_STATUS]
    }


def test_follows_a_status_passed_through_an_offload_or_a_class():
    assert _raised(FIXTURE, "route_that_offloads_a_status") == [423]
    assert _raised(FIXTURE, "route_that_raises_a_status_class") == [451]


def test_reads_the_default_of_a_status_left_out():
    assert _raised(FIXTURE, "route_that_uses_a_default_status") == [418]
    assert _raised(FIXTURE, "route_that_falls_back_to_a_status") == [500]


def test_flags_a_status_bound_in_a_way_it_cannot_read():
    assert _raised(FIXTURE, "route_with_an_unpacked_status") == [
        UNREADABLE_STATUS,
        400,
    ]


def test_reads_a_module_level_status():
    assert _raised(FIXTURE, "route_with_a_status_constant") == [503]


def test_counts_a_set_status_and_a_response_subclass():
    assert _raised(FIXTURE, "route_that_sets_a_status") == [404, 410]


def test_skips_the_scope_guard_default_but_not_a_route_reason():
    router = APIRouter()
    router.get(
        "/scoped",
        responses={
            status.HTTP_401_UNAUTHORIZED: {"description": SCOPE_ERRORS[401][0]},
            status.HTTP_403_FORBIDDEN: {
                "description": f"Not the owner. {SCOPE_ERRORS[403][1]}"
            },
        },
    )(fixture_routes.route_with_a_default)
    assert stale(router.routes) == {f"{FIXTURE}:route_with_a_default": [403]}


def test_counts_a_helper_response_but_not_its_errors_in_a_swallowing_try():
    assert _raised(FIXTURE, "_refuse_or_respond") == [409]
    assert _raised(
        FIXTURE, "route_that_returns_a_helper_response_from_a_swallowing_try"
    ) == [423]


def test_skips_a_declared_raise_in_a_swallowing_try():
    assert _raised(FIXTURE, "route_with_a_declared_raise_in_a_swallowing_try") == []


def test_swallows_only_handlers_that_catch_fastapi_http_errors():
    assert _raised(FIXTURE, "route_that_catches_an_unrelated_http_exception") == [409]
    assert _raised(FIXTURE, "route_that_catches_starlette_http_errors") == []
