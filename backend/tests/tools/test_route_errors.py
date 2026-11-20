from tools.route_errors import statuses


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


def test_ignores_an_unrelated_function_with_the_same_name():
    # `os.path.join` must not resolve to the streaming `join` helper, which can 502.
    assert 502 not in _raised("endpoints.heartbeat", "get_setup_library_info")
