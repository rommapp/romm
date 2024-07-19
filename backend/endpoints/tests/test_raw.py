from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_raw_asset(access_token):
    response = client.get(
        "/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav"
    )
    assert response.status_code == 403

    response = client.get(
        "/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    assert "SUPER_MARIO_64_SAVE_FILE" in response.text
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
