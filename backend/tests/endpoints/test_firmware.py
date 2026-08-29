"""Tests for `GET /api/firmware`."""

from fastapi import status


def test_get_firmware_requires_auth(client, firmware):
    response = client.get("/api/firmware")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_firmware_returns_everything_by_default(
    client, access_token, firmware, missing_firmware
):
    response = client.get(
        "/api/firmware", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK

    names = [f["file_name"] for f in response.json()]
    assert sorted(names) == ["gone.bin", "present.bin"]


def test_get_firmware_missing_true_returns_only_missing(
    client, access_token, firmware, missing_firmware
):
    response = client.get(
        "/api/firmware",
        params={"missing": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert [f["file_name"] for f in body] == ["gone.bin"]
    assert body[0]["missing_from_fs"] is True


def test_get_firmware_missing_false_excludes_missing(
    client, access_token, firmware, missing_firmware
):
    response = client.get(
        "/api/firmware",
        params={"missing": "false"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert [f["file_name"] for f in body] == ["present.bin"]
    assert body[0]["missing_from_fs"] is False


def test_get_firmware_exposes_its_platform(client, access_token, platform, firmware):
    """The library-wide missing view groups by platform, so the row has to
    carry one without a second round trip per entry."""
    response = client.get(
        "/api/firmware", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["platform_id"] == platform.id


def test_get_firmware_missing_filter_stacks_with_platform_id(
    client, access_token, platform, firmware, missing_firmware
):
    response = client.get(
        "/api/firmware",
        params={"platform_id": platform.id, "missing": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert [f["file_name"] for f in response.json()] == ["gone.bin"]
