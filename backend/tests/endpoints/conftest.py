from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from main import app

from config import (
    OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS,
    OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS,
)
from handler.auth import oauth_handler
from handler.redis_handler import sync_cache


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def _isolated_assets_dir(tmp_path, monkeypatch):
    """Redirect the shared fs_asset_handler to a tmp dir for the test's duration.

    Upload, scan, compute_content_hash, and remove_file all dispatch through
    self.base_path; rebinding base_path to a tmp dir keeps the test from
    leaking files into the real ROMM_BASE_PATH and lets every IO path resolve
    consistently.
    """
    from pathlib import Path

    from handler.filesystem import fs_asset_handler

    new_base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_asset_handler, "base_path", new_base)
    return new_base


@pytest.fixture(autouse=True)
def clear_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


@pytest.fixture()
def access_token(admin_user):  # noqa
    data = {
        "sub": admin_user.username,
        "iss": "romm:oauth",
        "scopes": " ".join(admin_user.oauth_scopes),
    }

    return oauth_handler.create_access_token(
        data=data, expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS)
    )


@pytest.fixture()
def refresh_token(admin_user):  # noqa
    data = {
        "sub": admin_user.username,
        "iss": "romm:oauth",
        "scopes": " ".join(admin_user.oauth_scopes),
    }

    return oauth_handler.create_refresh_token(
        data=data, expires_delta=timedelta(seconds=OAUTH_REFRESH_TOKEN_EXPIRE_SECONDS)
    )


@pytest.fixture
def editor_access_token(editor_user):  # noqa
    return oauth_handler.create_access_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


@pytest.fixture
def viewer_access_token(viewer_user):  # noqa
    return oauth_handler.create_access_token(
        data={
            "sub": viewer_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(viewer_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
