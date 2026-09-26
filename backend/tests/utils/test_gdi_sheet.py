from utils.cue_sheet import AudioTrackRange
from utils.gdi_sheet import GdiTrack, gdi_audio_ranges, parse_gdi_sheet

GDI_SHEET = """3
1 0 4 2352 track01.bin 0
2 450 0 2352 "Track 02 (Audio).raw" 0
3 45000 4 2048 C:\\Rips\\track03.iso 0
"""


def test_parses_bare_quoted_and_windows_paths():
    assert parse_gdi_sheet(GDI_SHEET) == [
        GdiTrack(number=1, type=4, sector_size=2352, file_name="track01.bin"),
        GdiTrack(
            number=2,
            type=0,
            sector_size=2352,
            file_name="Track 02 (Audio).raw",
        ),
        GdiTrack(number=3, type=4, sector_size=2048, file_name="track03.iso"),
    ]


def test_skips_malformed_lines():
    tracks = parse_gdi_sheet("2\n1 0 4 2352\nnot a track\n2 450 0 2352 t.raw 0\n")

    assert [t.number for t in tracks] == [2]


def test_takes_each_audio_track_as_its_whole_file():
    tracks = parse_gdi_sheet(GDI_SHEET)

    ranges = gdi_audio_ranges(
        tracks,
        {"track01.bin": 4096, "Track 02 (Audio).raw": 4099, "track03.iso": 4096},
    )

    assert ranges == [
        AudioTrackRange(
            number=2,
            file_name="Track 02 (Audio).raw",
            offset=0,
            length=4096,
            big_endian=False,
            title=None,
            performer=None,
        )
    ]


def test_skips_audio_tracks_missing_from_disk():
    assert gdi_audio_ranges(parse_gdi_sheet(GDI_SHEET), {}) == []


def test_skips_a_line_with_a_number_int_cannot_take():
    tracks = parse_gdi_sheet(
        f"2\n{'1' * 5000} 0 0 2352 a.raw 0\n2 450 0 2352 t.raw 0\n"
    )

    assert [t.number for t in tracks] == [2]
