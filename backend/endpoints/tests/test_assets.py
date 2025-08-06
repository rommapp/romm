import pytest
from fastapi import status
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
        json={"saves": [save.id]},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body) == 1


def test_delete_states(client, access_token, state):
    response = client.post(
        "/api/states/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"states": [state.id]},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body) == 1
