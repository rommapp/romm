import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx2
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User
from utils.zip_cache import playlist_zip_entries

DISC_1 = "disks/Game (Disc 1).chd"
DISC_2 = "disks/Game (Disc 2).chd"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def library(tmp_path: Path, mocker: MockerFixture) -> Path:
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


def _get(client: TestClient, token: str, rom: Rom, **params: str) -> httpx2.Response:
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
    client: TestClient,
    access_token: str,
    m3u_rom: Rom,
    library: Path,
    mocker: MockerFixture,
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


def test_play_skips_an_absolute_entry(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    _write_playlist(library, m3u_rom, str(library / m3u_rom.fs_path / DISC_1), DISC_2)

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert _manifest_names(response.text) == ["Game.m3u", DISC_2]


def test_play_packages_the_tracks_a_cue_sheet_names(
    client: TestClient, access_token: str, m3u_rom: Rom, library: Path
):
    disks = library / m3u_rom.fs_path / "disks"
    (disks / "Game (Disc 1).cue").write_text(
        'FILE "Game (Disc 1) (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n'
        'FILE "../../secret.bin" BINARY\n'
    )
    (disks / "Game (Disc 1) (Track 1).bin").write_bytes(b"track")
    _write_playlist(library, m3u_rom, "disks/Game (Disc 1).cue")

    response = _get(client, access_token, m3u_rom, purpose="play")

    assert _manifest_names(response.text) == [
        "Game.m3u",
        "disks/Game (Disc 1).cue",
        "disks/Game (Disc 1) (Track 1).bin",
    ]


def test_play_leaves_out_a_disc_of_a_rom_the_viewer_cannot_see(
    client: TestClient,
    viewer_access_token: str,
    viewer_user: User,
    m3u_rom: Rom,
    library: Path,
):
    hidden = db_rom_handler.add_rom(
        Rom(
            platform_id=m3u_rom.platform_id,
            name="Hidden",
            slug="hidden_slug",
            fs_name="disks",
            fs_name_no_tags="disks",
            fs_name_no_ext="disks",
            fs_extension="",
            fs_path=m3u_rom.fs_path,
        )
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=hidden.id,
            file_name="Game (Disc 2).chd",
            file_path=f"{m3u_rom.fs_path}/disks",
            file_size_bytes=4,
        )
    )
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=hidden.id, user_id=viewer_user.id
            )
        )
    _write_playlist(library, m3u_rom, DISC_1, DISC_2)

    response = _get(client, viewer_access_token, m3u_rom, purpose="play")

    assert _manifest_names(response.text) == ["Game.m3u", DISC_1]


def test_an_edited_playlist_changes_its_zip_entry(m3u_rom: Rom, library: Path):
    playlist = library / m3u_rom.full_path
    stored = db_rom_handler.get_rom(m3u_rom.id)
    assert stored is not None
    [m3u] = stored.files
    _write_playlist(library, m3u_rom, DISC_1)
    before = playlist_zip_entries(m3u)

    _write_playlist(library, m3u_rom, DISC_1, "# a comment")
    os.utime(playlist, (1_000_000, 1_000_000))
    after = playlist_zip_entries(m3u)

    assert before[0] != after[0]
    assert after[0].updated_at_epoch == 1_000_000
