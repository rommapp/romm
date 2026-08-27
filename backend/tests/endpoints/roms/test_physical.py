from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom

MOCK_IGDB_ID = 424242


async def _fake_scan_rom(*, rom: Rom, platform: Platform, fs_rom, **kwargs) -> Rom:
    """A fresh Rom carrying the columns the real scan_rom forwards, plus a match."""
    return Rom(
        id=rom.id,
        platform_id=platform.id,
        fs_name=fs_rom["fs_name"],
        fs_path=rom.fs_path,
        fs_size_bytes=0,
        name=rom.name,
        is_physical=rom.is_physical,
        upc=rom.upc,
        igdb_id=MOCK_IGDB_ID,
        url_cover="",
        url_manual="",
        url_screenshots=[],
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
def test_create_physical_rom_by_name(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "name": "Sonic the Hedgehog"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["is_physical"] is True
    assert body["has_file_on_disk"] is False
    assert body["upc"] is None
    assert body["name"] == "Sonic the Hedgehog"
    assert body["fs_path"].endswith("/.physical")
    assert body["igdb_id"] == MOCK_IGDB_ID
    assert scan_rom_mock.called
    assert download_mock.called

    stored = db_rom_handler.get_rom(body["id"])
    assert stored is not None
    assert stored.is_physical is True


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
def test_physical_rom_content_is_not_downloadable(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    created = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "name": "Sonic the Hedgehog"},
    )
    rom_id = created.json()["id"]

    response = client.get(
        f"/api/roms/{rom_id}/content/sonic.zip", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
@patch(
    "endpoints.roms.meta_upc_handler.resolve_upc_to_title",
    new_callable=AsyncMock,
    return_value="Sonic the Hedgehog",
)
def test_create_physical_rom_by_upc_resolves_title(
    resolve_mock: AsyncMock,
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "upc": "012345678905"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["name"] == "Sonic the Hedgehog"
    assert body["upc"] == "012345678905"
    assert resolve_mock.called


@patch(
    "endpoints.roms.meta_upc_handler.resolve_upc_to_title",
    new_callable=AsyncMock,
    return_value=None,
)
def test_create_physical_rom_unresolved_upc_returns_400(
    resolve_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "upc": "000000000000"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_physical_rom_requires_name_or_upc(
    client: TestClient, access_token: str, platform: Platform
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_physical_rom_unknown_platform_returns_404(
    client: TestClient, access_token: str
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": 999999, "name": "Sonic"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
def test_create_physical_rom_duplicate_name_returns_409(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    payload = {"platform_id": platform.id, "name": "Sonic"}
    first = client.post("/api/roms/physical", headers=_auth(access_token), json=payload)
    second = client.post(
        "/api/roms/physical", headers=_auth(access_token), json=payload
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_409_CONFLICT

    first_rom = db_rom_handler.get_rom(first.json()["id"])
    assert first_rom is not None
    assert first_rom.fs_name == "Sonic"


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=RuntimeError("provider exploded"))
def test_create_physical_rom_rolls_back_a_failed_enrichment(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    platform: Platform,
):
    """A failure after the initial insert must not strand a metadata-less row,
    which the unique index would then turn into a 409 on every retry."""
    payload = {"platform_id": platform.id, "name": "Sonic"}

    with pytest.raises(RuntimeError):
        client.post("/api/roms/physical", headers=_auth(access_token), json=payload)

    assert (
        db_rom_handler.get_roms_by_fs_name(platform_id=platform.id, fs_names=["Sonic"])
        == {}
    )

    # The retry is what the rollback is for.
    with patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom):
        retry = client.post(
            "/api/roms/physical", headers=_auth(access_token), json=payload
        )
    assert retry.status_code == status.HTTP_200_OK


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
def test_roms_listing_physical_filter(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
):
    """`?physical=` is what the v2 gallery's physical filter sends."""
    create = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "name": "Sonic"},
    )
    physical_id = create.json()["id"]

    def ids(query: str) -> set[int]:
        resp = client.get(f"/api/roms?{query}", headers=_auth(access_token))
        assert resp.status_code == status.HTTP_200_OK
        return {item["id"] for item in resp.json()["items"]}

    assert ids(f"platform_id={platform.id}") == {rom.id, physical_id}
    assert ids(f"platform_id={platform.id}&physical=true") == {physical_id}
    assert ids(f"platform_id={platform.id}&physical=false") == {rom.id}


def test_create_physical_rom_requires_write_scope(
    client: TestClient, viewer_access_token: str, platform: Platform
):
    response = client.post(
        "/api/roms/physical",
        headers=_auth(viewer_access_token),
        json={"platform_id": platform.id, "name": "Sonic"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@patch("endpoints.roms.download_rom_resources", new_callable=AsyncMock)
@patch("endpoints.roms.scan_rom", side_effect=_fake_scan_rom)
def test_physical_rom_intermingles_in_listing(
    scan_rom_mock: AsyncMock,
    download_mock: AsyncMock,
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
):
    create = client.post(
        "/api/roms/physical",
        headers=_auth(access_token),
        json={"platform_id": platform.id, "name": "Sonic"},
    )
    physical_id = create.json()["id"]

    listing = client.get(
        f"/api/roms?platform_id={platform.id}",
        headers=_auth(access_token),
    )
    assert listing.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in listing.json()["items"]}
    assert {rom.id, physical_id}.issubset(ids)
