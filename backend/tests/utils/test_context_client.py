import httpx2
import pytest

from utils.context import (
    ctx_httpx_sync_client,
    create_httpx_client,
    sync_httpx_client,
)
from utils.ssrf import ValidationError, validate_url_for_http_request


def test_the_shared_client_is_the_one_the_app_created():
    with create_httpx_client(allowlist=frozenset()) as app_client:
        token = ctx_httpx_sync_client.set(app_client)
        try:
            assert sync_httpx_client() is app_client
        finally:
            ctx_httpx_sync_client.reset(token)


def test_without_an_app_every_caller_shares_one_client():
    # A test or a command-line run has no request to borrow a client from. The
    # first call makes one and later calls reuse it, so connections are still
    # pooled rather than opened per call.
    assert sync_httpx_client() is sync_httpx_client()
    assert isinstance(sync_httpx_client(), httpx2.Client)
    assert not sync_httpx_client().is_closed


def test_a_public_only_client_refuses_a_private_origin():
    # The same gate the shared client runs as a request hook: an empty allowlist
    # is what keeps a plugin's URL away from this instance's own network.
    with pytest.raises(ValidationError):
        validate_url_for_http_request(
            "http://127.0.0.1:8080/plugin.json", allowlist=frozenset()
        )
