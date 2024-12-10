import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_delete_saves(client, access_token, save):
    response = client.post(
        "/api/saves/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"saves": [save.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "Successfully deleted 1 saves"


def test_delete_states(client, access_token, state):
    response = client.post(
        "/api/states/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"states": [state.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "Successfully deleted 1 states"
