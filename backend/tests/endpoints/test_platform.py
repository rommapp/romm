from unittest.mock import patch

from fastapi import status


def test_get_platforms(client, access_token, platform):
    response = client.get("/api/platforms")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = client.get(
        "/api/platforms", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK

    platforms = response.json()
    assert len(platforms) == 1


def test_get_filesystem_platforms(client, access_token, platform):
    with patch(
        "utils.platforms.fs_platform_handler.get_platforms"
    ) as mock_get_platforms:
        # A folder already backed by a database row is excluded; a brand-new
        # folder with no database row is returned as an id -1 / 0-rom entry.
        mock_get_platforms.return_value = [platform.fs_slug, "segacd"]

        response = client.get("/api/platforms/filesystem")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = client.get(
            "/api/platforms/filesystem",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    platforms = response.json()
    fs_slugs = [p["fs_slug"] for p in platforms]
    assert platform.fs_slug not in fs_slugs
    assert "segacd" in fs_slugs

    segacd = next(p for p in platforms if p["fs_slug"] == "segacd")
    assert segacd["id"] == -1
    assert segacd["rom_count"] == 0


def test_update_platform_custom_name(client, access_token, platform):
    # The body is an embedded key, not a bare scalar; sending {"custom_name": ...}
    # must be accepted (regression against the single-body-param 422).
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"custom_name": "My Custom Name"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["custom_name"] == "My Custom Name"
