"""Guards the cross-origin defaults the API is served with."""

from collections.abc import Sequence
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from main import app
from starlette.middleware import Middleware

from config import cors_allow_credentials

FOREIGN_ORIGIN = "https://evil.example"
LISTED_ORIGIN = "https://romm.example"


def _cors_middleware() -> Middleware:
    return next(m for m in app.user_middleware if m.cls is CORSMiddleware)


def _scratch_app(**kwargs: Any) -> TestClient:
    scratch = FastAPI()
    scratch.add_middleware(CORSMiddleware, **kwargs)

    @scratch.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(scratch)


def test_a_wildcard_origin_is_never_paired_with_credentials() -> None:
    cors = _cors_middleware()
    origins = cors.kwargs["allow_origins"]
    assert isinstance(origins, Sequence)
    assert not (cors.kwargs["allow_credentials"] and "*" in origins), (
        "Starlette answers a wildcard with the caller's own Origin and "
        "Access-Control-Allow-Credentials, granting every site credentialed access"
    )


def test_a_foreign_origin_gets_no_cors_grant(client: TestClient) -> None:
    response = client.get("/api/heartbeat", headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 200
    # Starlette ships the credentials header either way; with no Allow-Origin to
    # pair it with, the browser drops the response.
    assert "access-control-allow-origin" not in response.headers


def test_a_listed_origin_is_granted_with_credentials() -> None:
    """Listing an origin is what turns cross-origin access on, credentials included."""
    client = _scratch_app(
        **{**_cors_middleware().kwargs, "allow_origins": [LISTED_ORIGIN]}
    )

    response = client.get("/ping", headers={"Origin": LISTED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == LISTED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_an_explicit_wildcard_is_served_without_credentials() -> None:
    """An operator-set `*` stays open, but is not paired with the session cookie."""
    client = _scratch_app(
        allow_origins=["*"],
        allow_credentials=cors_allow_credentials(["*"]),
    )

    response = client.get("/ping", headers={"Origin": FOREIGN_ORIGIN})

    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    ("origins", "expected"),
    [
        (["*"], False),
        ([], True),
        ([LISTED_ORIGIN], True),
        (["*", LISTED_ORIGIN], False),
    ],
)
def test_credentials_follow_the_wildcard(origins: list[str], expected: bool) -> None:
    assert cors_allow_credentials(origins) is expected
