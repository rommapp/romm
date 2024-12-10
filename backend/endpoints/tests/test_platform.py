import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_get_platforms(client, access_token, platform):
    response = client.get("/api/platforms")
    assert response.status_code == 403

    response = client.get(
        "/api/platforms", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

    platforms = response.json()
    assert len(platforms) == 1
