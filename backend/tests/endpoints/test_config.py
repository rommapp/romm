from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from config.config_manager import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
)
from config.config_manager import config_manager as cm


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_config(client):
    response = client.get("/api/config")
    assert response.status_code == status.HTTP_200_OK

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


def test_add_platform_binding_payload_shape(client, access_token: str):
    with patch.object(cm, "add_platform_binding") as add_platform_binding:
        response = client.post(
            "/api/config/system/platforms",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fs_slug": "n64", "slug": "nintendo-64"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_platform_binding.assert_called_once_with("n64", "nintendo-64")


def test_add_platform_version_payload_shape(client, access_token: str):
    with patch.object(cm, "add_platform_version") as add_platform_version:
        response = client.post(
            "/api/config/system/versions",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fs_slug": "n64", "slug": "1.0"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_platform_version.assert_called_once_with("n64", "1.0")


def test_add_exclusion_payload_shape(client, access_token: str):
    with patch.object(cm, "add_exclusion") as add_exclusion:
        response = client.post(
            "/api/config/exclude",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"exclusion_type": "single_files", "exclusion_value": "README.txt"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_exclusion.assert_called_once_with("single_files", "README.txt")
