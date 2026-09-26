import asyncio
import math
import shutil
import struct
import subprocess
import threading
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler import cd_audio
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
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


def write_gdi_disc(folder: Path) -> dict[str, bytes]:
    """Write a Dreamcast data track and two audio tracks as a .gdi set."""
    folder.mkdir(parents=True, exist_ok=True)
    # 150-sector gaps between tracks, as on a real disc.
    third_lba = 154 + TRACK_2_SECTORS + 150
    contents = {
        "disc.gdi": (
            f"3\n1 0 4 2352 track01.bin 0\n2 154 0 2352 track02.raw 0\n"
            f"3 {third_lba} 0 2352 track03.raw 0\n"
        ).encode(),
        "track01.bin": b"\x01" * AUDIO_SECTOR * 4,
        "track02.raw": _tone(TRACK_2_SECTORS),
        "track03.raw": _tone(TRACK_3_SECTORS),
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
def gdi_rom(admin_user: User, platform: Platform, real_library: Path) -> Rom:
    fs_path = f"{platform.slug}/roms/Disc Game"
    contents = write_gdi_disc(real_library / fs_path)
    return _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {name: len(data) for name, data in contents.items()},
        fs_path,
    )


@pytest.fixture
def gdrom_chd_rom(
    admin_user: User, platform: Platform, real_library: Path, tmp_path: Path
) -> Rom:
    """The Dreamcast disc compressed to a GD-ROM CHD."""
    fs_path = f"{platform.slug}/roms/Disc Game"
    (real_library / fs_path).mkdir(parents=True)
    chd = real_library / fs_path / "disc.chd"
    write_gdi_disc(tmp_path / "source")
    _create_chd(tmp_path / "source" / "disc.gdi", chd)
    return _add_disc_rom(
        admin_user, platform, "Disc Game", {"disc.chd": chd.stat().st_size}, fs_path
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


@pytest.mark.parametrize("fixture", ["gdi_rom", "gdrom_chd_rom"])
def test_extracts_the_audio_tracks_of_a_dreamcast_disc(
    client: TestClient,
    access_token: str,
    fixture: str,
    request: pytest.FixtureRequest,
):
    rom: Rom = request.getfixturevalue(fixture)

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "extracted": ["disc - Track 02.flac", "disc - Track 03.flac"],
        "skipped": [],
    }
    metas = _soundtrack_metas(rom.id)
    second = metas["disc - Track 02.flac"]
    assert second is not None
    assert second.title == "Track 02"
    assert second.duration_seconds == pytest.approx(
        TRACK_2_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )
    third = metas["disc - Track 03.flac"]
    assert third is not None
    # The gap to where the next track would start isn't audio.
    assert third.duration_seconds == pytest.approx(
        TRACK_3_SECTORS / SECTORS_PER_SECOND, abs=0.01
    )


def test_names_the_tracks_of_discs_that_share_a_sheet_name(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    fs_path = f"{platform.slug}/roms/Disc Game"
    rom = _add_disc_rom(admin_user, platform, "Disc Game", {}, fs_path)
    for disc in ("Disc 1", "Disc 2"):
        for name, data in write_gdi_disc(real_library / fs_path / disc).items():
            db_rom_handler.add_rom_file(
                RomFile(
                    rom_id=rom.id,
                    file_name=name,
                    file_path=f"{fs_path}/{disc}",
                    file_size_bytes=len(data),
                    category=RomFileCategory.GAME,
                )
            )
    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert sorted(response.json()["extracted"]) == [
        "Disc 1 - disc - Track 02.flac",
        "Disc 1 - disc - Track 03.flac",
        "Disc 2 - disc - Track 02.flac",
        "Disc 2 - disc - Track 03.flac",
    ]
    # The folder order numbers the discs when their names don't.
    second_disc = _soundtrack_metas(rom.id)["Disc 2 - disc - Track 02.flac"]
    assert second_disc is not None
    assert second_disc.title == "Track 02 (Disc 2)"
    assert second_disc.disc == 2


def test_extracts_every_disc_of_a_set(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
    tmp_path: Path,
):
    fs_path = f"{platform.slug}/roms/Disc Game"
    folder = real_library / fs_path
    folder.mkdir(parents=True)
    write_cue_disc(tmp_path / "source")
    discs = ["Disc Game (Disc 1).chd", "Disc Game (Disc 2).chd"]
    for disc in discs:
        _create_chd(tmp_path / "source" / "Disc.cue", folder / disc)
    (folder / "Disc Game.m3u").write_text("\n".join(discs))
    rom = _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {name: (folder / name).stat().st_size for name in [*discs, "Disc Game.m3u"]},
        fs_path,
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert sorted(response.json()["extracted"]) == [
        "Disc Game (Disc 1) - Track 02.flac",
        "Disc Game (Disc 1) - Track 03.flac",
        "Disc Game (Disc 2) - Track 02.flac",
        "Disc Game (Disc 2) - Track 03.flac",
    ]
    first_disc = _soundtrack_metas(rom.id)["Disc Game (Disc 1) - Track 03.flac"]
    assert first_disc is not None
    assert first_disc.title == "Track 03 (Disc 1)"
    assert first_disc.disc == 1


def test_refuses_to_move_a_lone_disc_a_playlist_lists(
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
    chd = real_library / fs_path / "Disc Game (Disc 1).chd"
    _create_chd(tmp_path / "source" / "Disc.cue", chd)
    (real_library / fs_path / "Disc Game.m3u").write_text(
        "Disc Game (Disc 1).chd\nDisc Game (Disc 2).chd\n"
    )
    rom = _add_disc_rom(
        admin_user, platform, chd.name, {chd.name: chd.stat().st_size}, fs_path
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Disc Game.m3u" in response.json()["detail"]
    assert chd.is_file()


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


@pytest.mark.parametrize("sheet", ["Loose.cue", "Loose.gdi"])
def test_refuses_a_sheet_loose_in_the_platform_folder(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    sheet: str,
):
    fs_path = f"{platform.slug}/roms"
    rom = _add_disc_rom(admin_user, platform, sheet, {sheet: 10}, fs_path)

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

    async def fail_on_third(
        source: cd_audio.AudioSource, output: Path, album: str | None
    ) -> None:
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
    async def unreadable(stdin: asyncio.StreamWriter, pcm: cd_audio.PcmChunks) -> None:
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


@pytest.mark.parametrize("disc", ["cd_rom", "gdi_rom", "chd_rom", "gdrom_chd_rom"])
def test_counts_the_audio_tracks_before_and_after_extraction(
    client: TestClient,
    access_token: str,
    disc: str,
    request: pytest.FixtureRequest,
):
    rom: Rom = request.getfixturevalue(disc)
    url = f"/api/roms/{rom.id}/soundtracks/cd-audio"

    before = client.get(url, headers=_auth(access_token))
    client.post(url, headers=_auth(access_token))
    after = client.get(url, headers=_auth(access_token))

    assert before.status_code == status.HTTP_200_OK
    assert before.json() == {"tracks": 2, "extracted": 0}
    assert after.json() == {"tracks": 2, "extracted": 2}


def test_counts_no_tracks_on_a_data_only_disc(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    fs_path = f"{platform.slug}/roms/Data Game"
    folder = real_library / fs_path
    folder.mkdir(parents=True)
    (folder / "Data.cue").write_text(
        'FILE "Data.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
    )
    (folder / "Data.bin").write_bytes(b"\x01" * AUDIO_SECTOR * 4)
    rom = _add_disc_rom(
        admin_user,
        platform,
        "Data Game",
        {"Data.cue": 60, "Data.bin": AUDIO_SECTOR * 4},
        fs_path,
    )

    response = client.get(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracks": 0, "extracted": 0}


def test_counts_no_tracks_without_a_disc_image(
    client: TestClient, access_token: str, game_folder_rom: Rom, game_folder_on_disk
):
    response = client.get(
        f"/api/roms/{game_folder_rom.id}/soundtracks/cd-audio",
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"tracks": 0, "extracted": 0}


def test_counting_reports_missing_chd_support(
    client: TestClient,
    access_token: str,
    chd_rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(cd_audio, "load_libchdr", lambda: None)

    response = client.get(
        f"/api/roms/{chd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_counting_reports_an_unreadable_chd(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    fs_path = f"{platform.slug}/roms/Disc Game"
    (real_library / fs_path).mkdir(parents=True)
    (real_library / fs_path / "Disc.chd").write_bytes(b"not a chd")
    rom = _add_disc_rom(admin_user, platform, "Disc Game", {"Disc.chd": 9}, fs_path)

    response = client.get(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_counting_needs_only_the_roms_read_scope(
    client: TestClient, viewer_access_token: str, cd_rom: Rom
):
    response = client.get(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio",
        headers=_auth(viewer_access_token),
    )

    assert response.status_code == status.HTTP_200_OK


def test_extracts_a_disc_kept_as_both_a_sheet_and_a_chd_once(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    fs_path = f"{platform.slug}/roms/Disc Game"
    contents = write_cue_disc(real_library / fs_path)
    chd = real_library / fs_path / "Disc.chd"
    _create_chd(real_library / fs_path / "Disc.cue", chd)
    sizes = {name: len(data) for name, data in contents.items()}
    rom = _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {**sizes, "Disc.chd": chd.stat().st_size},
        fs_path,
    )
    url = f"/api/roms/{rom.id}/soundtracks/cd-audio"

    extracted = client.post(url, headers=_auth(access_token))
    counted = client.get(url, headers=_auth(access_token))

    assert extracted.json() == {
        "extracted": ["Disc - Track 02.flac", "Disc - Track 03.flac"],
        "skipped": [],
    }
    # The sheet's CD-Text title shows it was read rather than the CHD.
    metas = _soundtrack_metas(rom.id)
    assert metas["Disc - Track 02.flac"] is not None
    assert metas["Disc - Track 02.flac"].title == "Opening"
    assert counted.json() == {"tracks": 2, "extracted": 2}


def test_skips_a_track_a_concurrent_extraction_finished_first(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    real_encode = cd_audio.encode_track
    soundtrack = real_library / cd_rom.full_path / "soundtrack"

    async def race_on_third(
        source: cd_audio.AudioSource, output: Path, album: str | None
    ) -> None:
        await real_encode(source, output, album)
        if source.number == 3:
            (soundtrack / "Disc - Track 03.flac").write_bytes(b"theirs")

    monkeypatch.setattr(cd_audio, "encode_track", race_on_third)

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "extracted": ["Disc - Track 02.flac"],
        "skipped": ["Disc - Track 03.flac"],
    }
    assert (soundtrack / "Disc - Track 03.flac").read_bytes() == b"theirs"
    assert sorted(p.name for p in soundtrack.iterdir()) == [
        "Disc - Track 02.flac",
        "Disc - Track 03.flac",
    ]


async def test_cancelling_mid_read_closes_the_image_and_cleans_up(tmp_path: Path):
    reading = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    def slow_pcm() -> Generator[bytes, None, None]:
        try:
            reading.set()
            release.wait(5)
            yield b"\0" * 4
        finally:
            closed.set()

    source = cd_audio.AudioSource(
        number=2, big_endian=False, title=None, performer=None, pcm=slow_pcm
    )
    output = tmp_path / "Track 02.flac"
    task = asyncio.create_task(cd_audio.encode_track(source, output, None))
    await asyncio.to_thread(reading.wait, 5)

    task.cancel()
    await asyncio.sleep(0.05)
    release.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
    assert not output.exists()


def test_falls_back_to_the_chd_when_the_sheet_lost_its_tracks(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
    tmp_path: Path,
):
    fs_path = f"{platform.slug}/roms/Disc Game"
    folder = real_library / fs_path
    folder.mkdir(parents=True)
    write_cue_disc(tmp_path / "source")
    _create_chd(tmp_path / "source" / "Disc.cue", folder / "Disc.chd")
    (folder / "Disc.cue").write_text(CUE_SHEET)
    rom = _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {"Disc.cue": len(CUE_SHEET), "Disc.chd": (folder / "Disc.chd").stat().st_size},
        fs_path,
    )
    url = f"/api/roms/{rom.id}/soundtracks/cd-audio"

    counted = client.get(url, headers=_auth(access_token))
    extracted = client.post(url, headers=_auth(access_token))

    assert counted.json() == {"tracks": 2, "extracted": 0}
    assert extracted.json()["extracted"] == [
        "Disc - Track 02.flac",
        "Disc - Track 03.flac",
    ]


def _add_sheet_rom(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    contents: dict[str, bytes],
) -> Rom:
    fs_path = f"{platform.slug}/roms/Disc Game"
    folder = real_library / fs_path
    folder.mkdir(parents=True)
    for name, data in contents.items():
        (folder / name).write_bytes(data)
    return _add_disc_rom(
        admin_user,
        platform,
        "Disc Game",
        {name: len(data) for name, data in contents.items()},
        fs_path,
    )


def test_reads_a_file_named_in_several_cases_once(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    names = ["Track.bin", "TRACK.BIN", "track.bin"]
    sheet = "".join(
        f'FILE "{name}" BINARY\n  TRACK {number:02d} AUDIO\n'
        f"    INDEX 01 00:00:{(number - 2) * 25:02d}\n"
        for number, name in enumerate(names, 2)
    )
    rom = _add_sheet_rom(
        admin_user,
        platform,
        real_library,
        {"Disc.cue": sheet.encode(), "Track.bin": _tone(TRACK_2_SECTORS)},
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    durations = [
        meta.duration_seconds
        for meta in _soundtrack_metas(rom.id).values()
        if meta is not None and meta.duration_seconds is not None
    ]
    # Split three ways rather than each spanning the whole file.
    assert sum(durations) == pytest.approx(
        TRACK_2_SECTORS / SECTORS_PER_SECOND, abs=0.02
    )


def test_takes_each_gdi_track_file_and_number_once(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    sheet = (
        "5\n2 150 0 2352 track02.raw 0\n3 300 0 2352 TRACK02.RAW 0\n"
        "4 450 0 2352 track02.raw 0\n0 600 0 2352 track05.raw 0\n"
        "100 750 0 2352 track06.raw 0\n"
    )
    tone = _tone(TRACK_3_SECTORS)
    rom = _add_sheet_rom(
        admin_user,
        platform,
        real_library,
        {
            "disc.gdi": sheet.encode(),
            "track02.raw": tone,
            "track05.raw": tone,
            "track06.raw": tone,
        },
    )

    response = client.get(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.json() == {"tracks": 1, "extracted": 0}


def test_refuses_a_sheet_too_large_to_be_one(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
):
    rom = _add_sheet_rom(
        admin_user,
        platform,
        real_library,
        {"Disc.cue": b"REM" + b" " * cd_audio.MAX_SHEET_BYTES},
    )

    response = client.get(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_reports_a_track_name_the_scanner_would_ignore(
    client: TestClient,
    access_token: str,
    cd_rom: Rom,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        fs_rom_handler,
        "is_excluded_multi_part",
        lambda file_name, cnfg=None: file_name.endswith(".flac"),
    )

    response = client.post(
        f"/api/roms/{cd_rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not (real_library / cd_rom.full_path / "soundtrack").exists()


def test_leaves_a_lone_disc_without_audio_where_it_is(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    real_library: Path,
    tmp_path: Path,
):
    fs_path = f"{platform.slug}/roms"
    (real_library / fs_path).mkdir(parents=True)
    (tmp_path / "Data.cue").write_text(
        'FILE "Data.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
    )
    # libchdr can't open a CHD of a single hunk, so the track spans several.
    (tmp_path / "Data.bin").write_bytes(b"\x01" * AUDIO_SECTOR * 300)
    chd = real_library / fs_path / "Data Game.chd"
    _create_chd(tmp_path / "Data.cue", chd)
    rom = _add_disc_rom(
        admin_user, platform, chd.name, {chd.name: chd.stat().st_size}, fs_path
    )

    response = client.post(
        f"/api/roms/{rom.id}/soundtracks/cd-audio", headers=_auth(access_token)
    )

    assert response.json() == {"extracted": [], "skipped": []}
    assert chd.is_file()
    assert not (real_library / fs_path / "Data Game").exists()


async def test_reports_a_track_flac_cannot_be_started_for(tmp_path: Path):
    def silence() -> Generator[bytes, None, None]:
        yield b"\0" * 4

    source = cd_audio.AudioSource(
        number=2, big_endian=False, title="Open\0ing", performer=None, pcm=silence
    )

    with pytest.raises(cd_audio.CdAudioEncodeException):
        await cd_audio.encode_track(source, tmp_path / "Track 02.flac", None)
