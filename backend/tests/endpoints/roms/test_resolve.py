from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom


def _resolve(client: TestClient, access_token: str, payload: dict):
    return client.post(
        "/api/roms/resolve",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def test_resolve_creates_virtual_rom(
    client: TestClient, access_token: str, platform: Platform
):
    response = _resolve(
        client,
        access_token,
        {
            "platform_slug": platform.fs_slug,
            "fs_name": "Metroid Fusion (USA).gba",
            "md5_hash": "abc123",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["is_virtual"] is True
    assert body["missing_from_fs"] is False
    assert body["fs_name"] == "Metroid Fusion (USA).gba"
    assert body["md5_hash"] == "abc123"
    assert body["platform_id"] == platform.id

    rom = db_rom_handler.get_rom(body["id"])
    assert rom is not None
    assert rom.fs_size_bytes == 0
    assert rom.fs_extension == "gba"
    assert rom.fs_name_no_tags == "Metroid Fusion"


def test_resolve_is_idempotent(
    client: TestClient, access_token: str, platform: Platform
):
    payload = {
        "platform_slug": platform.fs_slug,
        "fs_name": "Metroid Fusion (USA).gba",
        "md5_hash": "abc123",
    }
    first = _resolve(client, access_token, payload)
    second = _resolve(client, access_token, payload)

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert first.json()["id"] == second.json()["id"]


def test_resolve_matches_existing_rom_by_hash(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    db_rom_handler.update_rom(rom.id, {"md5_hash": "d41d8cd98f00b204e9800998ecf8427e"})

    # A renamed file on another device still resolves to the same entry.
    response = _resolve(
        client,
        access_token,
        {
            "platform_slug": platform.fs_slug,
            "fs_name": "renamed_dump.zip",
            "md5_hash": "d41d8cd98f00b204e9800998ecf8427e",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["id"] == rom.id
    assert body["is_virtual"] is False


def test_resolve_matches_existing_rom_by_fs_name(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    response = _resolve(
        client,
        access_token,
        {
            "platform_slug": platform.fs_slug,
            "fs_name": rom.fs_name,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == rom.id


def test_resolve_hash_match_wins_over_name_match(
    client: TestClient, access_token: str, platform: Platform, rom: Rom
):
    db_rom_handler.update_rom(rom.id, {"md5_hash": "aaa"})
    other = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="other_rom",
            fs_name="other_rom.zip",
            fs_name_no_tags="other_rom",
            fs_name_no_ext="other_rom",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            md5_hash="bbb",
        )
    )

    # fs_name points at `other`, but the hash identifies `rom`.
    response = _resolve(
        client,
        access_token,
        {
            "platform_slug": platform.fs_slug,
            "fs_name": other.fs_name,
            "md5_hash": "aaa",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == rom.id


def test_resolve_creates_platform_when_missing(client: TestClient, access_token: str):
    assert db_platform_handler.get_platform_by_fs_slug("n64") is None

    response = _resolve(
        client,
        access_token,
        {
            "platform_slug": "n64",
            "fs_name": "Super Mario 64 (USA).z64",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    platform = db_platform_handler.get_platform_by_fs_slug("n64")
    assert platform is not None
    assert response.json()["platform_id"] == platform.id


def test_resolve_requires_write_scope(client: TestClient, platform: Platform):
    response = client.post(
        "/api/roms/resolve",
        json={"platform_slug": platform.fs_slug, "fs_name": "game.gba"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
