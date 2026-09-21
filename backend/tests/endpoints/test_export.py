import csv
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from handler.database import db_rom_handler
from models.rom import Rom, RomUserStatus
from models.user import User
from utils.backloggd_exporter import CSV_HEADER
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


BACKLOGGD_PATH = "/api/export/backloggd"


def _backloggd_rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body)))


def test_backloggd_rejects_anonymous(client):
    response = client.get(BACKLOGGD_PATH)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_backloggd_allows_viewer(client, viewer_access_token: str):
    # Reading your own play state is a read scope, unlike the library exports.
    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {viewer_access_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert _backloggd_rows(response.text) == [CSV_HEADER]


def test_backloggd_serves_a_csv_download(client, access_token: str):
    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert ".csv" in response.headers["content-disposition"]


def test_backloggd_exports_the_callers_play_state(
    client, access_token: str, admin_user: User, rom: Rom
):
    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None
    db_rom_handler.update_rom_user(
        rom_user.id,
        {
            "rating": 7,
            "status": RomUserStatus.FINISHED,
            "last_played": datetime(2024, 3, 4, tzinfo=timezone.utc),
        },
    )

    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {access_token}"}
    )

    assert _backloggd_rows(response.text)[1] == [
        "test_rom",
        "",
        "3.5",
        "completed",
        "2024-03-04",
    ]


def test_backloggd_skips_roms_with_no_play_state(
    client, access_token: str, rom: Rom, second_rom: Rom, admin_user: User
):
    # Both ROMs have a rom_user row; only one of them says anything.
    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None
    db_rom_handler.update_rom_user(rom_user.id, {"backlogged": True})

    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {access_token}"}
    )

    assert [row[0] for row in _backloggd_rows(response.text)[1:]] == ["test_rom"]


def test_backloggd_skips_hidden_roms(
    client, access_token: str, rom: Rom, admin_user: User
):
    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None
    db_rom_handler.update_rom_user(rom_user.id, {"rating": 9, "hidden": True})

    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {access_token}"}
    )

    assert _backloggd_rows(response.text) == [CSV_HEADER]


def test_backloggd_does_not_leak_another_users_play_state(
    client, viewer_access_token: str, rom: Rom, admin_user: User
):
    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None
    db_rom_handler.update_rom_user(rom_user.id, {"rating": 10})

    response = client.get(
        BACKLOGGD_PATH, headers={"Authorization": f"Bearer {viewer_access_token}"}
    )

    assert _backloggd_rows(response.text) == [CSV_HEADER]
