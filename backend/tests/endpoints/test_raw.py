from fastapi import status


def test_get_raw_asset(client, access_token):
    response = client.get(
        "/api/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = client.get(
        "/api/raw/assets/users/557365723a31/saves/n64/mupen64/Super Mario 64 (J) (Rev A).sav",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "SUPER_MARIO_64_SAVE_FILE" in response.text
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
