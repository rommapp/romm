"""Guards the cross-origin defaults the API is served with."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from main import app
from starlette.middleware import Middleware

FOREIGN_ORIGIN = "https://evil.example"
LISTED_ORIGIN = "https://romm.example"


def _cors_middleware() -> Middleware:
    return next(m for m in app.user_middleware if m.cls is CORSMiddleware)


def test_a_wildcard_origin_is_never_paired_with_credentials() -> None:
    cors = _cors_middleware()
    assert not (
        cors.kwargs["allow_credentials"] and "*" in cors.kwargs["allow_origins"]
    ), (
        "Starlette answers a wildcard with the caller's own Origin and "
        "Access-Control-Allow-Credentials, granting every site credentialed access"
    )


def test_a_foreign_origin_gets_no_cors_grant(client) -> None:
    response = client.get("/api/heartbeat", headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 200
    # Starlette ships the credentials header either way; with no Allow-Origin to
    # pair it with, the browser drops the response.
    assert "access-control-allow-origin" not in response.headers


def test_a_listed_origin_is_granted_with_credentials() -> None:
    """Listing an origin is what turns cross-origin access on, credentials included."""
    scratch = FastAPI()
    scratch.add_middleware(
        CORSMiddleware,
        **{**_cors_middleware().kwargs, "allow_origins": [LISTED_ORIGIN]},
    )

    @scratch.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(scratch).get("/ping", headers={"Origin": LISTED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == LISTED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
