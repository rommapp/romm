from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from utils.platform_slugs import UniversalPlatformSlug as UPS


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


def test_webrcade_feed_skips_roms_without_a_file(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    platform = db_platform_handler.update_platform(
        platform.id,
        {"name": "Nintendo Entertainment System", "slug": UPS.NES, "fs_slug": UPS.NES},
    )
    db_rom_handler.update_rom(rom.id, {"platform_id": platform.id})
    db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Physical Game",
            fs_name="Physical Game",
            fs_path=f"{platform.slug}/roms/.physical",
            fs_size_bytes=0,
            is_physical=True,
        )
    )
    db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Gone Game",
            fs_name="Gone Game.zip",
            fs_path=f"{platform.slug}/roms",
            fs_size_bytes=123,
            missing_from_fs=True,
        )
    )

    response = client.get(
        "/api/feeds/webrcade",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    items = response.json()["categories"][0]["items"]
    assert [item["title"] for item in items] == [rom.name]


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
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PS4 [CUSA12345].pkg",
            file_path=rom.fs_path,
            file_size_bytes=456,
            sha1_hash="beadfeed",
        )
    )

    response = client.get(
        "/api/feeds/fpkgi/ps4",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "DATA" in body
    assert len(body["DATA"]) == 1

    entry = next(iter(body["DATA"].values()))
    assert entry["name"] == "Test PS4"
    assert entry["size"] == 456
    assert entry["title_id"] == "CUSA12345"


def test_fpkgi_feed_multi_file_rom(
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
            "fs_name": "Test PS4",
            "fs_name_no_tags": "Test PS4",
            "fs_name_no_ext": "Test PS4",
            "fs_extension": "",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 369,
            "regions": ["US"],
        },
    )
    for file_name, category, missing_from_fs in (
        ("Test PS4 base.pkg", None, False),
        ("Test PS4 update.pkg", RomFileCategory.UPDATE, False),
        ("Test PS4 dlc.pkg", RomFileCategory.DLC, False),
        ("Test PS4 cover.png", None, False),
        ("Test PS4 deleted.pkg", None, True),
    ):
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=f"{rom.fs_path}/{rom.fs_name}",
                file_size_bytes=123,
                category=category,
                missing_from_fs=missing_from_fs,
            )
        )

    response = client.get(
        "/api/feeds/fpkgi/ps4",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()["DATA"]
    assert len(data) == 3
    assert all(url.endswith(".pkg") for url in data)
    assert not any("deleted" in url for url in data)
    assert all(entry["size"] == 123 for entry in data.values())
    assert sorted(entry["name"] for entry in data.values()) == [
        "Test PS4 - DLC",
        "Test PS4 - Test PS4 base",
        "Test PS4 - Update",
    ]
    # Packages of the same game stay grouped under one title id
    assert len({entry["title_id"] for entry in data.values()}) == 1

    response = client.get(
        "/api/feeds/fpkgi/ps4?content_type=update",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()["DATA"]
    assert len(data) == 1
    assert next(iter(data.values()))["name"] == "Test PS4 - Update"

    response = client.get(
        "/api/feeds/fpkgi/ps4?content_type=not-a-category",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_fpkgi_feed_names_are_unique_within_a_rom(
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
            "fs_name": "Test PS4",
            "fs_name_no_tags": "Test PS4",
            "fs_name_no_ext": "Test PS4",
            "fs_extension": "",
            "fs_path": f"{platform.slug}/roms",
            "fs_size_bytes": 369,
            "regions": ["US"],
        },
    )
    for sub_path, file_name, category in (
        ("", "Test PS4 base.pkg", None),
        ("update", "Test PS4 patch.pkg", RomFileCategory.UPDATE),
        ("dlc", "Test PS4 brawler.pkg", RomFileCategory.DLC),
        ("dlc", "Test PS4 loadout.pkg", RomFileCategory.DLC),
        # Same file name in two categories, so the file name alone is ambiguous
        ("dlc", "Test PS4 extra.pkg", RomFileCategory.DLC),
        ("demo", "Test PS4 extra.pkg", RomFileCategory.DEMO),
        ("demo", "Test PS4 trial.pkg", RomFileCategory.DEMO),
    ):
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=f"{rom.fs_path}/{rom.fs_name}/{sub_path}".rstrip("/"),
                file_size_bytes=123,
                category=category,
            )
        )

    response = client.get(
        "/api/feeds/fpkgi/ps4",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()["DATA"]
    assert len(data) == 7
    assert sorted(entry["name"] for entry in data.values()) == [
        "Test PS4 - DLC - Test PS4 extra",
        "Test PS4 - Demo - Test PS4 extra",
        "Test PS4 - Test PS4 base",
        "Test PS4 - Test PS4 brawler",
        "Test PS4 - Test PS4 loadout",
        "Test PS4 - Test PS4 trial",
        "Test PS4 - Update",
    ]

    # Filtering must not change the name a package is served under
    response = client.get(
        "/api/feeds/fpkgi/ps4?content_type=dlc",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    dlc_data = response.json()["DATA"]
    assert sorted(entry["name"] for entry in dlc_data.values()) == [
        "Test PS4 - DLC - Test PS4 extra",
        "Test PS4 - Test PS4 brawler",
        "Test PS4 - Test PS4 loadout",
    ]


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

    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSP Game.pkg",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
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

    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSP DLC.pkg",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.DLC,
        )
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

    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSV Game.pkg",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
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

    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSV DLC.pkg",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.DLC,
        )
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

    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Test PSX Game.pkg",
            file_path=f"{platform.slug}/roms",
            file_size_bytes=456,
            sha1_hash="beadfeed",
            category=RomFileCategory.GAME,
        )
    )

    response = client.get(
        "/api/feeds/pkgj/psx/games",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == "filename=pkgj_psx_games.txt"
    assert "Test PSX Game" in response.text
