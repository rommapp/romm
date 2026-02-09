import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_config(client):
    response = client.get("/api/config")
    assert response.status_code == status.HTTP_200_OK

    from config.config_manager import (
        DEFAULT_EXCLUDED_DIRS,
        DEFAULT_EXCLUDED_EXTENSIONS,
        DEFAULT_EXCLUDED_FILES,
    )

    config = response.json()
    assert config.get("EXCLUDED_PLATFORMS") == DEFAULT_EXCLUDED_DIRS
    assert config.get("EXCLUDED_SINGLE_EXT") == [
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    ]
    assert config.get("EXCLUDED_SINGLE_FILES") == DEFAULT_EXCLUDED_FILES
    assert config.get("EXCLUDED_MULTI_FILES") == DEFAULT_EXCLUDED_DIRS
    assert config.get("EXCLUDED_MULTI_PARTS_EXT") == [
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    ]
    assert config.get("EXCLUDED_MULTI_PARTS_FILES") == DEFAULT_EXCLUDED_FILES
    assert config.get("PLATFORMS_BINDING") == {}
    assert not config.get("SKIP_HASH_CALCULATION")
