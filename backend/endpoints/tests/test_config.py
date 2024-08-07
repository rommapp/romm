import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200

    config = response.json()
    assert config.get("EXCLUDED_PLATFORMS") == []
    assert config.get("EXCLUDED_SINGLE_EXT") == []
    assert config.get("EXCLUDED_SINGLE_FILES") == []
    assert config.get("EXCLUDED_MULTI_FILES") == []
    assert config.get("EXCLUDED_MULTI_PARTS_EXT") == []
    assert config.get("EXCLUDED_MULTI_PARTS_FILES") == []
    assert config.get("PLATFORMS_BINDING") == {}
    assert config.get("ROMS_FOLDER_NAME") == "roms"
    assert config.get("FIRMWARE_FOLDER_NAME") == "bios"
