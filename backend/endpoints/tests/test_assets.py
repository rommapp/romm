from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_delete_saves(access_token, save):
    response = client.post(
        "/saves/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"saves": [save.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "Successfully deleted 1 saves"


def test_delete_states(access_token, state):
    response = client.post(
        "/states/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"states": [state.id], "delete_from_fs": []},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["msg"] == "Successfully deleted 1 states"
