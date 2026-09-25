import math
import shutil
import struct
import subprocess
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler import cd_audio
from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory, TrackMeta
from models.user import User

AUDIO_SECTOR = 2352
SECTORS_PER_SECOND = 75

CUE_SHEET = """FILE "Disc (Track 1).bin" BINARY
  TRACK 01 MODE2/2352
    INDEX 01 00:00:00
FILE "Disc (Track 2).bin" BINARY
  TRACK 02 AUDIO
    TITLE "Opening"
    INDEX 00 00:00:00
    INDEX 01 00:00:10
FILE "Disc (Track 3).bin" BINARY
  TRACK 03 AUDIO
    INDEX 01 00:00:00
"""


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# Track 3 is left off a multiple of four sectors, which CHD pads.
TRACK_2_SECTORS = 75
TRACK_3_SECTORS = 38


def _tone(sectors: int) -> bytes:
    """Little-endian 16-bit stereo PCM, the layout of a raw audio track."""
    count = sectors * AUDIO_SECTOR // 4
    samples = (
        int(8000 * math.sin(2 * math.pi * 440 * i / 44100)) for i in range(count)
    )
    return b"".join(struct.pack("<hh", s, s) for s in samples)


def write_cue_disc(folder: Path) -> dict[str, bytes]:
    """Write a data track and two audio tracks as a cue/bin set."""
    folder.mkdir(parents=True, exist_ok=True)
    contents = {
        "Disc.cue": CUE_SHEET.encode(),
        "Disc (Track 1).bin": b"\x01" * AUDIO_SECTOR * 4,
        # Ten sectors of pregap silence ahead of the tone.
        "Disc (Track 2).bin": b"\0" * AUDIO_SECTOR * 10 + _tone(TRACK_2_SECTORS),
        "Disc (Track 3).bin": _tone(TRACK_3_SECTORS),
    }
    for name, data in contents.items():
        (folder / name).write_bytes(data)
    return contents


def _add_disc_rom(
    admin_user: User,
    platform: Platform,
    fs_name: str,
    files: dict[str, int],
    file_path: str,
) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Disc Game",
            slug="disc_game",
            fs_name=fs_name,
            fs_name_no_tags="Disc Game",
            fs_name_no_ext="Disc Game",
            fs_extension=fs_name.rpartition(".")[2] if "." in fs_name else "",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    for name, size in files.items():
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=name,
                file_path=file_path,
                file_size_bytes=size,
                category=RomFileCategory.GAME,
            )
        )
    loaded = db_rom_handler.get_rom(rom.id)
    assert loaded is not None
    return loaded


def _soundtrack_metas(rom_id: int) -> dict[str, TrackMeta | None]:
    rom = db_rom_handler.get_rom(rom_id)
    assert rom is not None
    return {
        f.file_name: f.track_meta
        for f in rom.files
        if f.category == RomFileCategory.SOUNDTRACK
    }


@pytest.fixture
def cd_rom(admin_user: User, platform: Platform, real_library: Path) -> Rom:
    """A disc folder with a data track and two audio tracks, written to disk."""
    fs_path = f"{platform.slug}/roms/Disc Game"
    contents = write_cue_disc(real_library / fs_path)
    return _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {name: len(data) for name, data in contents.items()},
        fs_path,
    )


def _create_chd(source: Path, output: Path) -> None:
    chdman = shutil.which("chdman")
    assert chdman, "chdman (mame-tools) is needed to build CHD fixtures"
    subprocess.run(
        [chdman, "createcd", "-i", str(source), "-o", str(output)],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def chd_rom(
    admin_user: User, platform: Platform, real_library: Path, tmp_path: Path
) -> Rom:
    """The same disc compressed to a CHD, alone in its own folder."""
    fs_path = f"{platform.slug}/roms/Disc Game"
    (real_library / fs_path).mkdir(parents=True)
    chd = real_library / fs_path / "Disc.chd"
    write_cue_disc(tmp_path / "source")
    _create_chd(tmp_path / "source" / "Disc.cue", chd)
    return _add_disc_rom(
        admin_user, platform, "Disc Game", {"Disc.chd": chd.stat().st_size}, fs_path
    )


def test_extracts_each_audio_track_to_flac(
    client: TestClient, access_token: str, cd_rom: Rom, real_library: Path
):
    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "extracted": ["Disc - Track 02.flac", "Disc - Track 03.flac"],
        "skipped": [],
    }
    soundtrack = real_library / cd_rom.full_path / "soundtrack"
    assert sorted(p.name for p in soundtrack.iterdir()) == [
        "Disc - Track 02.flac",
        "Disc - Track 03.flac",
    ]
    assert (soundtrack / "Disc - Track 02.flac").read_bytes()[:4] == b"fLaC"

    metas = _soundtrack_metas(cd_rom.id)
    opening = metas["Disc - Track 02.flac"]
    assert opening is not None
    assert opening.title == "Opening"
    assert opening.album == "Disc Game"
    assert opening.track == 2
    assert opening.duration_seconds == pytest.approx(
        TRACK_2_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )
    untitled = metas["Disc - Track 03.flac"]
    assert untitled is not None
    assert untitled.title == "Track 03"
    assert untitled.duration_seconds == pytest.approx(
        TRACK_3_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )


def test_extracts_the_audio_tracks_of_a_chd(
    client: TestClient, access_token: str, chd_rom: Rom
):
    response = client.post(
        f"/api/roms/{chd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "extracted": ["Disc - Track 02.flac", "Disc - Track 03.flac"],
        "skipped": [],
    }
    metas = _soundtrack_metas(chd_rom.id)
    second = metas["Disc - Track 02.flac"]
    assert second is not None
    # CHD keeps no CD-Text, and its stored pregap stays out of the track.
    assert second.title == "Track 02"
    assert second.album == "Disc Game"
    assert second.duration_seconds == pytest.approx(
        TRACK_2_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )
    third = metas["Disc - Track 03.flac"]
    assert third is not None
    assert third.duration_seconds == pytest.approx(
        TRACK_3_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )


def test_moves_a_lone_chd_into_its_own_folder(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
    tmp_path: Path,
):
    fs_path = f"{platform.slug}/roms"
    (real_library / fs_path).mkdir(parents=True)
    write_cue_disc(tmp_path / "source")
    chd = real_library / fs_path / "Disc Game.chd"
    _create_chd(tmp_path / "source" / "Disc.cue", chd)
    rom = _add_disc_rom(
        admin_user,
        platform,
        "Disc Game.chd",
        {"Disc Game.chd": chd.stat().st_size},
        fs_path,
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["extracted"] == [
        "Disc Game - Track 02.flac",
        "Disc Game - Track 03.flac",
    ]
    folder = real_library / fs_path / "Disc Game"
    assert (folder / "Disc Game.chd").is_file()
    assert (folder / "soundtrack" / "Disc Game - Track 02.flac").is_file()


def test_reports_missing_chd_support(
    client: TestClient,
    access_token: str,
    chd_rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cd_audio, "load_libchdr", lambda: None)

    response = client.post(
        f"/api/roms/{chd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_skips_tracks_already_extracted(
    client: TestClient, access_token: str, cd_rom: Rom
):
    url = f"/api/roms/{cd_rom.id}/soundtracks/cd-audio"
    client.post(url, headers=_auth(access_token))

    response = client.post(url, headers=_auth(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "extracted": [],
        "skipped": ["Disc - Track 02.flac", "Disc - Track 03.flac"],
    }


def test_extracts_nothing_without_a_cue_sheet(
    client: TestClient, access_token: str, game_folder_rom: Rom, game_folder_on_disk
):
    response = client.post(
        f"/api/roms/{game_folder_rom.id}/soundtracks/cd-audio",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"extracted": [], "skipped": []}


def test_refuses_a_sheet_loose_in_the_platform_folder(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Loose",
            slug="loose",
            fs_name="Loose.cue",
            fs_name_no_tags="Loose",
            fs_name_no_ext="Loose",
            fs_extension="cue",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="Loose.cue",
            file_path=rom.fs_path,
            file_size_bytes=10,
            category=RomFileCategory.GAME,
        )
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_reports_a_missing_encoder(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cd_audio, "FLAC_BINARY", "romm-no-such-flac")

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_registers_the_tracks_written_before_a_failure(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    real_encode = cd_audio.encode_track

    async def fail_on_third(source, output, album):
        if source.number == 3:
            raise cd_audio.CdAudioEncodeException("boom")
        await real_encode(source, output, album)

    monkeypatch.setattr(cd_audio, "encode_track", fail_on_third)

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert set(_soundtrack_metas(cd_rom.id)) == {"Disc - Track 02.flac"}


def test_leaves_no_partial_file_when_the_image_cannot_be_read(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    async def unreadable(stdin, pcm):
        raise OSError("read failed")

    monkeypatch.setattr(cd_audio, "_feed", unreadable)

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    soundtrack = real_library / cd_rom.full_path / "soundtrack"
    assert list(soundtrack.iterdir()) == []


def test_requires_the_roms_write_scope(
    client: TestClient, viewer_access_token: str, cd_rom: Rom
):
    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio",
        headers=_auth(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
