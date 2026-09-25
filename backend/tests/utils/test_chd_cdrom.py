import shutil
import subprocess
from pathlib import Path

import pytest

from utils.chd_cdrom import (
    SECTOR_BYTES,
    ChdAudioTrack,
    ChdError,
    ChdImage,
    ChdTrack,
    audio_tracks,
    load_libchdr,
    parse_track_metadata,
)


def test_parses_a_current_track_entry():
    track = parse_track_metadata(
        "TRACK:2 TYPE:AUDIO SUBTYPE:NONE FRAMES:225 PREGAP:150 PGTYPE:VAUDIO "
        "PGSUB:NONE POSTGAP:0\0"
    )

    assert track == ChdTrack(
        number=2, type="AUDIO", frames=225, pregap=150, pregap_stored=True
    )


def test_parses_a_legacy_track_entry():
    track = parse_track_metadata("TRACK:1 TYPE:MODE1_RAW SUBTYPE:NONE FRAMES:300")

    assert track == ChdTrack(
        number=1, type="MODE1_RAW", frames=300, pregap=0, pregap_stored=False
    )


@pytest.mark.parametrize("text", ["", "TRACK:x TYPE:AUDIO FRAMES:1", "TYPE:AUDIO"])
def test_rejects_a_malformed_entry(text):
    assert parse_track_metadata(text) is None


def test_pads_each_track_to_four_frames_and_skips_stored_pregaps():
    tracks = [
        ChdTrack(number=1, type="MODE2_RAW", frames=10, pregap=0, pregap_stored=False),
        ChdTrack(number=2, type="AUDIO", frames=225, pregap=150, pregap_stored=True),
        ChdTrack(number=3, type="AUDIO", frames=37, pregap=150, pregap_stored=False),
    ]

    assert audio_tracks(tracks) == [
        ChdAudioTrack(number=2, first_frame=12 + 150, frame_count=75),
        ChdAudioTrack(number=3, first_frame=12 + 228, frame_count=37),
    ]


def test_parses_a_gdrom_track_entry():
    track = parse_track_metadata(
        "TRACK:2 TYPE:AUDIO SUBTYPE:NONE FRAMES:44550 PAD:44325 PREGAP:0 "
        "PGTYPE:MODE1 PGSUB:NONE POSTGAP:0"
    )

    assert track == ChdTrack(
        number=2, type="AUDIO", frames=44550, pregap=0, pregap_stored=False, pad=44325
    )


def test_skips_the_padding_a_gdrom_track_counts_to_the_next_one():
    # The layout chdman writes for a .gdi with its high-density area at 45000.
    tracks = [
        ChdTrack(1, "MODE1_RAW", frames=450, pregap=0, pregap_stored=False, pad=150),
        ChdTrack(2, "AUDIO", frames=44550, pregap=0, pregap_stored=False, pad=44325),
        ChdTrack(3, "MODE1_RAW", frames=160, pregap=0, pregap_stored=False, pad=150),
        ChdTrack(4, "AUDIO", frames=187, pregap=0, pregap_stored=False, pad=150),
        ChdTrack(5, "MODE1_RAW", frames=10, pregap=0, pregap_stored=False, pad=0),
    ]

    assert audio_tracks(tracks) == [
        ChdAudioTrack(number=2, first_frame=452, frame_count=225),
        ChdAudioTrack(number=4, first_frame=452 + 44552 + 160, frame_count=37),
    ]


def _swapped(pcm: bytes) -> bytes:
    swapped = bytearray(len(pcm))
    swapped[0::2], swapped[1::2] = pcm[1::2], pcm[0::2]
    return bytes(swapped)


def _chdman_createcd(source: Path, output: Path) -> None:
    chdman = shutil.which("chdman")
    assert chdman, "chdman (mame-tools) is needed to build CHD fixtures"
    subprocess.run(
        [chdman, "createcd", "-i", str(source), "-o", str(output)],
        check=True,
        capture_output=True,
    )


def test_reads_gdrom_audio_back_without_its_padding(tmp_path: Path):
    lib = load_libchdr()
    assert lib is not None, "libchdr is needed to read CHD images"
    second = bytes((i * 7) & 0xFF for i in range(37 * SECTOR_BYTES))
    third = bytes((i * 13) & 0xFF for i in range(20 * SECTOR_BYTES))
    (tmp_path / "track01.bin").write_bytes(b"\x11" * 4 * SECTOR_BYTES)
    (tmp_path / "track02.raw").write_bytes(second)
    (tmp_path / "track03.raw").write_bytes(third)
    # Gaps between the LBAs become padding in the CHD.
    (tmp_path / "disc.gdi").write_text(
        "3\n1 0 4 2352 track01.bin 0\n2 154 0 2352 track02.raw 0\n"
        "3 341 0 2352 track03.raw 0\n"
    )
    _chdman_createcd(tmp_path / "disc.gdi", tmp_path / "disc.chd")

    with ChdImage(lib, tmp_path / "disc.chd") as image:
        read = [b"".join(image.audio_pcm(t)) for t in audio_tracks(image.tracks())]

    assert read == [_swapped(second), _swapped(third)]


def test_reads_audio_back_as_stored_big_endian(tmp_path: Path):
    lib = load_libchdr()
    assert lib is not None, "libchdr is needed to read CHD images"

    # 37 sectors of a rising ramp, so any misplaced or swapped byte shows.
    pcm = bytes((i * 7) & 0xFF for i in range(37 * SECTOR_BYTES))
    (tmp_path / "Track 1.bin").write_bytes(pcm)
    (tmp_path / "Disc.cue").write_text(
        'FILE "Track 1.bin" BINARY\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
    )
    _chdman_createcd(tmp_path / "Disc.cue", tmp_path / "Disc.chd")

    with ChdImage(lib, tmp_path / "Disc.chd") as image:
        [track] = audio_tracks(image.tracks())
        read = b"".join(image.audio_pcm(track))

    assert read == _swapped(pcm)


def test_refuses_a_file_that_is_not_a_chd(tmp_path: Path):
    lib = load_libchdr()
    assert lib is not None, "libchdr is needed to read CHD images"
    bogus = tmp_path / "Disc.chd"
    bogus.write_bytes(b"not a chd")

    with pytest.raises(ChdError):
        ChdImage(lib, bogus)
