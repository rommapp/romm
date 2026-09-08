from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from utils.gamelist_exporter import GamelistExporter
from utils.pegasus_exporter import PegasusExporter

EXPORTERS = {
    "/api/export/gamelist-xml": GamelistExporter,
    "/api/export/pegasus": PegasusExporter,
}

with_endpoint = pytest.mark.parametrize("path", list(EXPORTERS))


@with_endpoint
def test_export_rejects_viewer(client, viewer_access_token: str, platform, path: str):
    # Both endpoints write into the library, so reading ROMs is not enough.
    response = client.post(
        f"{path}?platform_ids={platform.id}",
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@with_endpoint
def test_export_rejects_anonymous(client, platform, path: str):
    response = client.post(f"{path}?platform_ids={platform.id}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@with_endpoint
def test_export_allows_editor(client, editor_access_token: str, platform, path: str):
    with patch.object(
        EXPORTERS[path],
        "export_platform_to_file",
        new_callable=AsyncMock,
        return_value=True,
    ) as export_mock:
        response = client.post(
            f"{path}?platform_ids={platform.id}",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    export_mock.assert_awaited_once()


@with_endpoint
def test_export_unknown_platform_is_404(client, editor_access_token: str, path: str):
    # Matches the 404 a hidden platform gets, so the response is not an oracle
    # for whether the platform exists (see test_permissions_visibility).
    with patch.object(
        EXPORTERS[path], "export_platform_to_file", new_callable=AsyncMock
    ) as export_mock:
        response = client.post(
            f"{path}?platform_ids=99999",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    export_mock.assert_not_awaited()


@with_endpoint
def test_export_rejects_batch_with_one_unknown_platform(
    client, editor_access_token: str, platform, path: str
):
    # The whole request is refused up front, so a partial batch never writes.
    with patch.object(
        EXPORTERS[path], "export_platform_to_file", new_callable=AsyncMock
    ) as export_mock:
        response = client.post(
            f"{path}?platform_ids={platform.id}&platform_ids=99999",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    export_mock.assert_not_awaited()
