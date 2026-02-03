import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from handler.database import db_platform_handler, db_rom_handler
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory, RomMetadata


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_webrcade_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "Nintendo Entertainment System", "slug": UPS.NES, "fs_slug": UPS.NES},
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Super Test Bros",
            "fs_name": "Super Test Bros.zip",
            "fs_name_no_tags": "Super Test Bros",
            "fs_name_no_ext": "Super Test Bros",
            "fs_extension": "zip",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/webrcade",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["title"] == "RomM Feed"
    assert len(body["categories"]) == 1
    assert body["categories"][0]["title"] == platform.name
    assert len(body["categories"][0]["items"]) == 1


def test_tinfoil_feed(client: TestClient, platform: Platform, rom: Rom):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "Nintendo Switch", "slug": UPS.SWITCH, "fs_slug": UPS.SWITCH},
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test Switch",
            "fs_name": "Test Switch.nsp",
            "fs_name_no_tags": "Test Switch",
            "fs_name_no_ext": "Test Switch",
            "fs_extension": "nsp",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test Switch.nsp",
            file_path=rom.fs_path,
            file_size_bytes=456,
            sha1_hash="beadfeed",
        )
    )

    response = client.get("/api/feeds/tinfoil?slug=switch")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body["files"]) == 1
    assert body["files"][0]["size"] > 0


def test_pkgi_ps3_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id, {"name": "PlayStation 3", "slug": UPS.PS3, "fs_slug": UPS.PS3}
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PS3",
            "fs_name": "Test PS3.pkg",
            "fs_name_no_tags": "Test PS3",
            "fs_name_no_ext": "Test PS3",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PS3.pkg",
            file_path=rom.fs_path,
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
    )

    response = client.get(
        "/api/feeds/pkgi/ps3/game",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgi_game.txt"
    assert "Test PS3" in response.text


def test_pkgi_psvita_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Vita", "slug": UPS.PSVITA, "fs_slug": UPS.PSVITA},
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSV",
            "fs_name": "Test PSV.pkg",
            "fs_name_no_tags": "Test PSV",
            "fs_name_no_ext": "Test PSV",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSV.pkg",
            file_path=rom.fs_path,
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
    )

    response = client.get(
        "/api/feeds/pkgi/psvita/game",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgi_game.txt"
    assert "Test PSV" in response.text


def test_pkgi_psp_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Portable", "slug": UPS.PSP, "fs_slug": UPS.PSP},
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSP",
            "fs_name": "Test PSP.pkg",
            "fs_name_no_tags": "Test PSP",
            "fs_name_no_ext": "Test PSP",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSP.pkg",
            file_path=rom.fs_path,
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
    )

    response = client.get(
        "/api/feeds/pkgi/psp/game",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgi_game.txt"
    assert "Test PSP" in response.text


def test_fpkgi_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id, {"name": "PlayStation 4", "slug": UPS.PS4, "fs_slug": UPS.PS4}
    )
    rom = db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PS4",
            "fs_name": "Test PS4.pkg",
            "fs_name_no_tags": "Test PS4",
            "fs_name_no_ext": "Test PS4",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/fpkgi/ps4",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "DATA" in body
    assert len(body["DATA"]) == 1


def test_kekatsu_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id, {"name": "Nintendo DS", "slug": UPS.NDS, "fs_slug": UPS.NDS}
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test DS",
            "fs_name": "Test DS.nds",
            "fs_name_no_tags": "Test DS",
            "fs_name_no_ext": "Test DS",
            "fs_extension": "nds",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/kekatsu/nds",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("1")
    assert "Test DS" in response.text


def test_pkgj_psp_games_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Portable", "slug": UPS.PSP, "fs_slug": UPS.PSP},
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSP Game",
            "fs_name": "Test PSP Game.pkg",
            "fs_name_no_tags": "Test PSP Game",
            "fs_name_no_ext": "Test PSP Game",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/pkgj/psp/games",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psp_games.txt"
    assert "Test PSP Game" in response.text


def test_pkgj_psp_dlc_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Portable", "slug": UPS.PSP, "fs_slug": UPS.PSP},
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSP DLC",
            "fs_name": "Test PSP DLC.pkg",
            "fs_name_no_tags": "Test PSP DLC",
            "fs_name_no_ext": "Test PSP DLC",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/pkgj/psp/dlc",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psp_dlc.txt"
    assert "Test PSP DLC" in response.text


def test_pkgj_psvita_games_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Vita", "slug": UPS.PSVITA, "fs_slug": UPS.PSVITA},
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSV Game",
            "fs_name": "Test PSV Game.pkg",
            "fs_name_no_tags": "Test PSV Game",
            "fs_name_no_ext": "Test PSV Game",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/pkgj/psvita/games",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psvita_games.txt"
    assert "Test PSV Game" in response.text


def test_pkgj_psvita_dlc_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "PlayStation Vita", "slug": UPS.PSVITA, "fs_slug": UPS.PSVITA},
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSV DLC",
            "fs_name": "Test PSV DLC.pkg",
            "fs_name_no_tags": "Test PSV DLC",
            "fs_name_no_ext": "Test PSV DLC",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/pkgj/psvita/dlc",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psvita_dlc.txt"
    assert "Test PSV DLC" in response.text


def test_pkgj_psx_games_feed(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id, {"name": "PlayStation", "slug": UPS.PSX, "fs_slug": UPS.PSX}
    )
    db_rom_handler.update_rom(
        rom.id,
        {
            "platform_id": platform.id,
            "name": "Test PSX Game",
            "fs_name": "Test PSX Game.pkg",
            "fs_name_no_tags": "Test PSX Game",
            "fs_name_no_ext": "Test PSX Game",
            "fs_extension": "pkg",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 123,
            "sha1_hash": "deadbeef",
            "regions": ["US"],
        },
    )

    response = client.get(
        "/api/feeds/pkgj/psx/games",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psx_games.txt"
    assert "Test PSX Game" in response.text
