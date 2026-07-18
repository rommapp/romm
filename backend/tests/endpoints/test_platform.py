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
