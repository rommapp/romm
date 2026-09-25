from utils.cue_sheet import (
    AudioTrackRange,
    audio_track_ranges,
    parse_cue_sheet,
)

AUDIO_SECTOR = 2352
SECOND = 75  # frames


def test_parses_per_track_files_with_cd_text():
    tracks = parse_cue_sheet(
        'TITLE "Some Disc"\n'
        'FILE "C:\\Rips\\Game (Track 1).bin" BINARY\n'
        "  TRACK 01 MODE2/2352\n"
        "    INDEX 01 00:00:00\n"
        'FILE "Game (Track 2).bin" BINARY\n'
        "  TRACK 02 AUDIO\n"
        '    TITLE "Opening"\n'
        '    PERFORMER "Composer"\n'
        "    INDEX 00 00:00:00\n"
        "    INDEX 01 00:02:00\n"
    )

    assert [(t.number, t.mode, t.file_name) for t in tracks] == [
        (1, "MODE2/2352", "Game (Track 1).bin"),
        (2, "AUDIO", "Game (Track 2).bin"),
    ]
    assert tracks[1].indexes == {0: 0, 1: 2 * SECOND}
    assert tracks[1].title == "Opening"
    assert tracks[1].performer == "Composer"
    assert tracks[0].title is None


def test_skips_the_pregap_of_a_per_track_file():
    tracks = parse_cue_sheet(
        'FILE "Track 2.bin" BINARY\n'
        "  TRACK 02 AUDIO\n"
        "    INDEX 00 00:00:00\n"
        "    INDEX 01 00:02:00\n"
    )
    size = 10 * SECOND * AUDIO_SECTOR

    [track] = audio_track_ranges(tracks, {"Track 2.bin": size})

    assert track.offset == 2 * SECOND * AUDIO_SECTOR
    assert track.length == size - track.offset
    assert track.big_endian is False


def test_splits_a_single_image_at_each_pregap():
    tracks = parse_cue_sheet(
        'FILE "Game.bin" BINARY\n'
        "  TRACK 01 MODE1/2352\n"
        "    INDEX 01 00:00:00\n"
        "  TRACK 02 AUDIO\n"
        "    INDEX 00 01:00:00\n"
        "    INDEX 01 01:02:00\n"
        "  TRACK 03 AUDIO\n"
        "    INDEX 01 02:00:00\n"
    )
    size = 3 * 60 * SECOND * AUDIO_SECTOR

    second, third = audio_track_ranges(tracks, {"Game.bin": size})

    assert second == AudioTrackRange(
        number=2,
        file_name="Game.bin",
        offset=62 * SECOND * AUDIO_SECTOR,
        length=58 * SECOND * AUDIO_SECTOR,
        big_endian=False,
        title=None,
        performer=None,
    )
    assert third.offset == 120 * SECOND * AUDIO_SECTOR
    assert third.length == size - third.offset


def test_measures_a_cooked_data_track_in_its_own_sector_size():
    tracks = parse_cue_sheet(
        'FILE "Game.bin" BINARY\n'
        "  TRACK 01 MODE1/2048\n"
        "    INDEX 01 00:00:00\n"
        "  TRACK 02 AUDIO\n"
        "    INDEX 01 00:10:00\n"
    )
    data_bytes = 10 * SECOND * 2048

    [track] = audio_track_ranges(tracks, {"Game.bin": data_bytes + AUDIO_SECTOR})

    assert track.offset == data_bytes
    assert track.length == AUDIO_SECTOR


def test_marks_motorola_files_big_endian_and_leaves_wave_files_alone():
    tracks = parse_cue_sheet(
        "FILE Track2.bin MOTOROLA\n"
        "  TRACK 02 AUDIO\n"
        "    INDEX 01 00:00:00\n"
        'FILE "Track3.wav" WAVE\n'
        "  TRACK 03 AUDIO\n"
        "    INDEX 01 00:00:00\n"
    )

    ranges = audio_track_ranges(tracks, {"Track2.bin": 4096, "Track3.wav": 4096})

    assert [(r.number, r.big_endian) for r in ranges] == [(2, True)]


def test_skips_files_missing_from_disk():
    tracks = parse_cue_sheet(
        'FILE "Gone.bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 01 00:00:00\n'
    )

    assert audio_track_ranges(tracks, {}) == []


def test_stops_measuring_at_a_track_of_unknown_mode():
    tracks = parse_cue_sheet(
        'FILE "Game.bin" BINARY\n'
        "  TRACK 01 AUDIO\n"
        "    INDEX 01 00:00:00\n"
        "  TRACK 02 MODE9/9999\n"
        "    INDEX 01 00:01:00\n"
        "  TRACK 03 AUDIO\n"
        "    INDEX 01 00:02:00\n"
    )

    ranges = audio_track_ranges(tracks, {"Game.bin": 10 * SECOND * AUDIO_SECTOR})

    assert [(r.number, r.length) for r in ranges] == [(1, SECOND * AUDIO_SECTOR)]


def test_trims_a_ragged_file_to_whole_samples():
    tracks = parse_cue_sheet(
        'FILE "Track.bin" BINARY\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
    )

    [track] = audio_track_ranges(tracks, {"Track.bin": 4099})

    assert track.length == 4096


def test_ignores_malformed_lines():
    tracks = parse_cue_sheet(
        "REM GENRE Game\n"
        "FILE\n"
        "  TRACK 01 AUDIO\n"
        'FILE "Track.bin" BINARY\n'
        "  TRACK xx AUDIO\n"
        "  TRACK 02 AUDIO\n"
        "    INDEX 01 not-a-time\n"
        "    INDEX 01 00:01:00\n"
    )

    assert [(t.number, t.indexes) for t in tracks] == [(2, {1: SECOND})]
