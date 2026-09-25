import math
import struct
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler import cd_audio
from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
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


def _tone(seconds: float) -> bytes:
    """Little-endian 16-bit stereo PCM, the layout of a raw audio track."""
    frames = int(44100 * seconds)
    samples = (
        int(8000 * math.sin(2 * math.pi * 440 * i / 44100)) for i in range(frames)
    )
    return b"".join(struct.pack("<hh", s, s) for s in samples)


@pytest.fixture
def cd_rom(admin_user: User, platform: Platform, real_library: Path) -> Rom:
    """A disc folder with a data track and two audio tracks, written to disk."""
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Disc Game",
            slug="disc_game",
            fs_name="Disc Game",
            fs_name_no_tags="Disc Game",
            fs_name_no_ext="Disc Game",
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    folder = real_library / rom.full_path
    folder.mkdir(parents=True)
    contents = {
        "Disc.cue": CUE_SHEET.encode(),
        "Disc (Track 1).bin": b"\x01" * AUDIO_SECTOR * 4,
        # Ten sectors of pregap silence ahead of the tone.
        "Disc (Track 2).bin": b"\0" * AUDIO_SECTOR * 10 + _tone(1),
        "Disc (Track 3).bin": _tone(0.5),
    }
    for name, data in contents.items():
        (folder / name).write_bytes(data)
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=name,
                file_path=rom.full_path,
                file_size_bytes=len(data),
                category=RomFileCategory.GAME,
            )
        )
    return db_rom_handler.get_rom(rom.id)


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

    rom_after = db_rom_handler.get_rom(cd_rom.id)
    metas = {
        f.file_name: f.track_meta
        for f in rom_after.files
        if f.category == RomFileCategory.SOUNDTRACK
    }
    opening = metas["Disc - Track 02.flac"]
    assert opening is not None
    assert opening.title == "Opening"
    assert opening.album == "Disc Game"
    assert opening.track == 2
    assert opening.duration_seconds == pytest.approx(1.0, abs=0.01)
    untitled = metas["Disc - Track 03.flac"]
    assert untitled is not None
    assert untitled.title == "Track 03"
    assert untitled.duration_seconds == pytest.approx(0.5, abs=0.01)


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

    async def fail_on_third(source, track, output, album):
        if track.number == 3:
            raise cd_audio.CdAudioEncodeException("boom")
        await real_encode(source, track, output, album)

    monkeypatch.setattr(cd_audio, "encode_track", fail_on_third)

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    names = {
        f.file_name
        for f in db_rom_handler.get_rom(cd_rom.id).files
        if f.category == RomFileCategory.SOUNDTRACK
    }
    assert names == {"Disc - Track 02.flac"}


def test_leaves_no_partial_file_when_the_image_cannot_be_read(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    async def unreadable(stdin, source, track):
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
