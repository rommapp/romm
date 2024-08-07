import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_get_raw_asset(client, access_token):
    response = client.get(
        "/api/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav"
    )
    assert response.status_code == 403

    response = client.get(
        "/api/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    assert "SUPER_MARIO_64_SAVE_FILE" in response.text
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
