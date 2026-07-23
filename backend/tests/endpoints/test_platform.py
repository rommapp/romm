from unittest.mock import patch

from fastapi import status

from models.platform import CUSTOM_NAME_MAX_LENGTH, DESCRIPTION_MAX_LENGTH


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


def test_get_platform_description_defaults_to_empty(client, access_token, platform):
    response = client.get(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["description"] == ""


def test_update_platform_description(client, access_token, platform):
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "description": "Contains all Aftermarket, Beta, Demo, Proto, Unl, etc. roms"
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        response.json()["description"]
        == "Contains all Aftermarket, Beta, Demo, Proto, Unl, etc. roms"
    )


def test_update_platform_description_and_custom_name_together(
    client, access_token, platform
):
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "custom_name": "Sega - Genesis/ Mega Drive (Unofficial)",
            "description": "Aftermarket and unlicensed titles only",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["custom_name"] == "Sega - Genesis/ Mega Drive (Unofficial)"
    assert body["description"] == "Aftermarket and unlicensed titles only"


def test_update_platform_omitted_description_is_preserved(
    client, access_token, platform
):
    # An omitted field must not blank the stored value; the endpoint patches
    # only what the caller sent.
    client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": "Keep me"},
    )

    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"custom_name": "Renamed"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["description"] == "Keep me"


def test_update_platform_description_can_be_cleared(client, access_token, platform):
    client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": "Temporary"},
    )

    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": ""},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["description"] == ""


def test_update_platform_oversized_description_is_rejected(
    client, access_token, platform
):
    # Without a bound the oversized value reaches the database and surfaces as
    # an unhandled DataError (500); it must be a validation error instead.
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": "A" * (DESCRIPTION_MAX_LENGTH + 1)},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_update_platform_oversized_custom_name_is_rejected(
    client, access_token, platform
):
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"custom_name": "A" * (CUSTOM_NAME_MAX_LENGTH + 1)},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_update_platform_description_at_max_length_is_accepted(
    client, access_token, platform
):
    response = client.put(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"description": "A" * DESCRIPTION_MAX_LENGTH},
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["description"]) == DESCRIPTION_MAX_LENGTH


def test_update_platform_description_requires_write_scope(client, platform):
    response = client.put(
        f"/api/platforms/{platform.id}",
        json={"description": "Nope"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
