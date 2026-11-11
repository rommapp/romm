from fastapi import status

from models.rom import Rom


def test_stats_require_authentication(client, rom: Rom):
    response = client.get("/api/stats")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_stats_for_a_viewer(client, viewer_access_token: str, rom: Rom):
    response = client.get(
        "/api/stats",
        params={"include_platform_stats": True},
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["ROMS"] == 1
