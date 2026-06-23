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
    # Non-image assets must be served as an opaque download to prevent stored XSS
    # from any user-controlled file (e.g. an HTML uploaded as an avatar).
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
