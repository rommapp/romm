from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User

DISC_1 = "disks/Game (Disc 1).chd"
DISC_2 = "disks/Game (Disc 2).chd"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def library(tmp_path: Path, mocker) -> Path:
    mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(tmp_path))
    mocker.patch("endpoints.roms.LIBRARY_BASE_PATH", str(tmp_path))
    return tmp_path


@pytest.fixture
def m3u_rom(admin_user: User, platform: Platform, library: Path) -> Rom:
    """A lone Game.m3u at the platform root, its discs in a subfolder."""
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Game",
            slug="game_slug",
            fs_name="Game.m3u",
            fs_name_no_tags="Game",
            fs_name_no_ext="Game",
            fs_extension="m3u",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Game.m3u",
            file_path=rom.fs_path,
            file_size_bytes=64,
        )
    )
    roms_dir = library / rom.fs_path
    (roms_dir / "disks").mkdir(parents=True)
    for disc in (DISC_1, DISC_2):
        (roms_dir / disc).write_bytes(b"disc")
    (library / platform.slug / "secret.bin").write_bytes(b"secret")
    return rom


def _write_playlist(library: Path, rom: Rom, *entries: str) -> None:
    (library / rom.full_path).write_text("\n".join(entries) + "\n")


def _manifest_names(body: str) -> list[str]:
    # mod_zip lines are "<crc> <size> <location> <name>"; names may hold spaces.
    return [line.split(" ", 3)[3] for line in body.splitlines()]


def _get(client: TestClient, token: str, rom: Rom, **params: str):
    return client.get(
        f"/api/roms/{rom.id}/content/{rom.fs_name}",
        headers=_auth(token),
        params=params,
        follow_redirects=False,
    )


def test_play_zips_the_playlist_with_its_discs(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, DISC_1, DISC_2)

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Archive-Files"] == "zip"
    # The rom's own playlist is kept, so no generated one is added.
    assert _manifest_names(response.text) == ["Game.m3u", DISC_1, DISC_2]


def test_play_skips_an_entry_outside_the_rom_folder(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, "../secret.bin", DISC_1)

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert response.status_code == status.HTTP_200_OK
    assert _manifest_names(response.text) == ["Game.m3u", DISC_1]
    assert "secret" not in response.text


def test_play_skips_a_missing_entry(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, "disks/missing.chd", DISC_2)

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert response.status_code == status.HTTP_200_OK
    assert _manifest_names(response.text) == ["Game.m3u", DISC_2]


def test_play_serves_the_playlist_alone_when_it_lists_nothing_on_disk(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, "../secret.bin", "disks/missing.chd")

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert response.status_code == status.HTTP_200_OK
    assert "X-Accel-Redirect" in response.headers


def test_download_without_play_is_unchanged(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, DISC_1, DISC_2)

    response = _get(client, access_token, m3u_rom)

    assert response.status_code == status.HTTP_200_OK
    assert "X-Archive-Files" not in response.headers
    assert "X-Accel-Redirect" in response.headers


def test_play_in_dev_mode_builds_the_zip(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path, mocker
):
    mocker.patch("endpoints.roms.DEV_MODE", True)
    _write_playlist(library, m3u_rom, DISC_1, DISC_2)

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert response.status_code == status.HTTP_200_OK
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["Game.m3u", DISC_1, DISC_2]
        assert archive.read(DISC_1) == b"disc"


def test_head_for_play_describes_the_zip(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, DISC_1)

    response = client.head(
        f"/api/roms/{m3u_rom.id}/content/{m3u_rom.fs_name}",
        headers=_auth(access_token),
        params={"purpose": "play"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert "X-Accel-Redirect" not in response.headers
    assert response.headers["Content-Type"] == "application/zip"
