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


def test_reads_audio_back_as_stored_big_endian(tmp_path: Path):
    lib = load_libchdr()
    chdman = shutil.which("chdman")
    assert lib is not None, "libchdr is needed to read CHD images"
    assert chdman, "chdman (mame-tools) is needed to build CHD fixtures"

    # 37 sectors of a rising ramp, so any misplaced or swapped byte shows.
    pcm = bytes((i * 7) & 0xFF for i in range(37 * SECTOR_BYTES))
    (tmp_path / "Track 1.bin").write_bytes(pcm)
    (tmp_path / "Disc.cue").write_text(
        'FILE "Track 1.bin" BINARY\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
    )
    subprocess.run(
        [
            chdman,
            "createcd",
            "-i",
            str(tmp_path / "Disc.cue"),
            "-o",
            str(tmp_path / "Disc.chd"),
        ],
        check=True,
        capture_output=True,
    )

    with ChdImage(lib, tmp_path / "Disc.chd") as image:
        [track] = audio_tracks(image.tracks())
        read = b"".join(image.audio_pcm(track))

    swapped = bytearray(len(pcm))
    swapped[0::2], swapped[1::2] = pcm[1::2], pcm[0::2]
    assert read == bytes(swapped)


def test_refuses_a_file_that_is_not_a_chd(tmp_path: Path):
    lib = load_libchdr()
    assert lib is not None, "libchdr is needed to read CHD images"
    bogus = tmp_path / "Disc.chd"
    bogus.write_bytes(b"not a chd")

    with pytest.raises(ChdError):
        ChdImage(lib, bogus)
