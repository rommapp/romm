from unittest.mock import MagicMock

from utils.m3u import (
    disc_number,
    first_playlist_entry,
    generate_m3u_content,
    playlist_files,
)


class TestFirstPlaylistEntry:
    def test_returns_first_entry_relative_to_playlist_folder(self, tmp_path):
        disc1 = tmp_path / "game (Disc 1).rvz"
        disc1.write_bytes(b"x" * 100)
        (tmp_path / "game (Disc 2).rvz").write_bytes(b"x" * 100)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).rvz\ngame (Disc 2).rvz\n")

        assert first_playlist_entry(m3u) == disc1

    def test_skips_comments_and_blank_lines(self, tmp_path):
        disc = tmp_path / "disc.cue"
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("#EXTM3U\n\n# a comment\ndisc.cue\n")

        assert first_playlist_entry(m3u) == disc

    def test_handles_utf8_bom_and_crlf(self, tmp_path):
        disc = tmp_path / "disc.rvz"
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_bytes(b"\xef\xbb\xbfdisc.rvz\r\n")

        assert first_playlist_entry(m3u) == disc

    def test_resolves_windows_separators(self, tmp_path):
        disc = tmp_path / "Multi Disc" / "D2 (USA) (Disc 1).chd"
        disc.parent.mkdir()
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "D2 (USA) (Disc 1).m3u"
        m3u.write_text("Multi Disc\\D2 (USA) (Disc 1).chd\r\n")

        assert first_playlist_entry(m3u) == disc

    def test_prefers_a_literal_backslash_in_the_file_name(self, tmp_path):
        literal = tmp_path / "Game\\Disc 1.chd"
        literal.write_bytes(b"x" * 10)
        nested = tmp_path / "Game" / "Disc 1.chd"
        nested.parent.mkdir()
        nested.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("Game\\Disc 1.chd\n")

        assert first_playlist_entry(m3u) == literal

    def test_resolves_absolute_entry_as_is(self, tmp_path):
        disc = tmp_path / "elsewhere" / "disc.rvz"
        disc.parent.mkdir()
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text(f"{disc}\n")

        assert first_playlist_entry(m3u) == disc

    def test_returns_none_when_first_entry_missing(self, tmp_path):
        (tmp_path / "game (Disc 2).rvz").write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).rvz\ngame (Disc 2).rvz\n")

        assert first_playlist_entry(m3u) is None

    def test_returns_none_for_unreadable_playlist(self, tmp_path):
        assert first_playlist_entry(tmp_path / "missing.m3u") is None

    def test_returns_none_for_empty_playlist(self, tmp_path):
        m3u = tmp_path / "game.m3u"
        m3u.write_text("#EXTM3U\n\n")

        assert first_playlist_entry(m3u) is None


def _make_file(name: str, extension: str, download_name: str | None = None):
    f = MagicMock()
    f.file_extension = extension
    f.file_name = name
    f.file_name_for_download.return_value = download_name or name
    return f


class TestGenerateM3uContent:
    def test_single_file(self):
        files = [_make_file("game.bin", "bin")]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.bin"
        files[0].file_name_for_download.assert_called_once_with(False)

    def test_multiple_files(self):
        files = [
            _make_file("disc1.chd", "chd"),
            _make_file("disc2.chd", "chd"),
            _make_file("disc3.chd", "chd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"disc1.chd\ndisc2.chd\ndisc3.chd"

    def test_cue_files_preferred_over_bin(self):
        files = [
            _make_file("track01.bin", "bin"),
            _make_file("track02.bin", "bin"),
            _make_file("game.cue", "cue"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.cue"

    def test_cue_case_insensitive(self):
        files = [
            _make_file("track.bin", "bin"),
            _make_file("game.CUE", "CUE", download_name="game.CUE"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.CUE"

    def test_hidden_folder_passed_through(self):
        files = [_make_file("game.chd", "chd", download_name=".hidden/game.chd")]
        result = generate_m3u_content(files, hidden_folder=True)
        assert result == b".hidden/game.chd"
        files[0].file_name_for_download.assert_called_once_with(True)

    def test_no_descriptor_files_lists_all(self):
        files = [
            _make_file("disc1.chd", "chd"),
            _make_file("disc2.chd", "chd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"disc1.chd\ndisc2.chd"

    def test_gdi_preferred_over_raw_tracks(self):
        files = [
            _make_file("track01.bin", "bin"),
            _make_file("track02.raw", "raw"),
            _make_file("game.gdi", "gdi"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.gdi"

    def test_ccd_preferred_over_img_and_sub(self):
        files = [
            _make_file("game.img", "img"),
            _make_file("game.sub", "sub"),
            _make_file("game.ccd", "ccd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.ccd"

    def test_mds_preferred_over_mdf(self):
        files = [
            _make_file("game.mdf", "mdf"),
            _make_file("game.mds", "mds"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.mds"

    def test_descriptor_case_insensitive(self):
        files = [
            _make_file("track01.bin", "bin"),
            _make_file("game.GDI", "GDI", download_name="game.GDI"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.GDI"

    def test_every_disc_descriptor_listed(self):
        files = [
            _make_file("disc1/track01.bin", "bin"),
            _make_file("disc1.gdi", "gdi"),
            _make_file("disc2/track01.bin", "bin"),
            _make_file("disc2.gdi", "gdi"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"disc1.gdi\ndisc2.gdi"

    def test_standalone_disc_kept_beside_a_descriptor(self):
        # A set is not required to be all one format. The .gdi's tracks are
        # data, but the .chd is a disc that boots on its own.
        files = [
            _make_file("disc1.gdi", "gdi"),
            _make_file("track01.bin", "bin"),
            _make_file("disc2.chd", "chd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"disc1.gdi\ndisc2.chd"

    def test_standalone_disc_kept_beside_a_cue(self):
        files = [
            _make_file("disc1.cue", "cue"),
            _make_file("disc1.bin", "bin"),
            _make_file("disc2.chd", "chd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"disc1.cue\ndisc2.chd"

    def test_audio_tracks_are_not_discs(self):
        # A cue's CDDA tracks are data the sheet names, not discs beside it.
        files = [
            _make_file("game.cue", "cue"),
            _make_file("track01.bin", "bin"),
            _make_file("track02.wav", "wav"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        assert result == b"game.cue"


class TestPlaylistFiles:
    """The disc swapper reads this directly, so the files themselves matter."""

    def test_m3u_is_never_a_disc(self):
        m3u = _make_file("game.m3u", "m3u")
        disc = _make_file("game.chd", "chd")
        assert playlist_files([m3u, disc]) == [disc]

    def test_raw_tracks_are_not_discs(self):
        track = _make_file("track01.bin", "bin")
        gdi = _make_file("game.gdi", "gdi")
        assert playlist_files([track, gdi]) == [gdi]

    def test_bare_files_are_all_discs(self):
        discs = [_make_file("disc1.chd", "chd"), _make_file("disc2.chd", "chd")]
        assert playlist_files(discs) == discs

    def test_standalone_disc_survives_a_descriptor(self):
        gdi = _make_file("disc1.gdi", "gdi")
        track = _make_file("track01.bin", "bin")
        chd = _make_file("disc2.chd", "chd")
        assert playlist_files([gdi, track, chd]) == [gdi, chd]

    def test_bare_tracks_without_a_descriptor_are_discs(self):
        # Nothing describes them, so they are all there is to play.
        tracks = [_make_file("track01.bin", "bin"), _make_file("track02.bin", "bin")]
        assert playlist_files(tracks) == tracks


class TestDiscNumber:
    def test_reads_the_spellings_a_dumper_uses(self):
        for name in (
            "G (Disc 2).chd",
            "G (disc2).chd",
            "G (CD 2).chd",
            "G (Disque 2).chd",
        ):
            assert disc_number(_make_file(name, "chd")) == 2

    def test_reads_the_tosec_of_form(self):
        assert disc_number(_make_file("G (Disk 1 of 2).adf", "adf")) == 1
        assert disc_number(_make_file("G (Disk 10 of 12).adf", "adf")) == 10

    def test_reads_a_number_of_any_length(self):
        # An unparsed number would sort as 0, ahead of disc 1.
        assert disc_number(_make_file("G (Disc 100).chd", "chd")) == 100

    def test_a_disc_count_is_not_a_disc_number(self):
        # "(2 CD)" says how many the release had, not which one this is.
        assert disc_number(_make_file("G (2 CD).pbp", "pbp")) is None

    def test_reads_a_split_disc(self):
        assert disc_number(_make_file("G (Disc 2A).chd", "chd")) == 2

    def test_reads_a_lettered_disc(self):
        assert disc_number(_make_file("G (Disc A).chd", "chd")) == 1
        assert disc_number(_make_file("G (disc c).chd", "chd")) == 3
        assert disc_number(_make_file("G (Disk B of 2).adf", "adf")) == 2

    def test_a_letter_needs_a_space_to_be_a_disc(self):
        # "(CDi)" names the platform, not disc I.
        assert disc_number(_make_file("G (CDi).chd", "chd")) is None

    def test_a_name_that_claims_no_disc(self):
        assert disc_number(_make_file("G (USA).chd", "chd")) is None

    def test_a_bare_word_is_not_a_disc_number(self):
        # The parentheses are what make it a tag rather than part of a title.
        assert disc_number(_make_file("Disc Jockey 2.chd", "chd")) is None


class TestPlaylistOrder:
    """The playlist, the download and the disc swapper all read this order."""

    def test_the_tenth_disc_follows_the_second(self):
        files = [
            _make_file("G (Disc 10).chd", "chd"),
            _make_file("G (Disc 2).chd", "chd"),
            _make_file("G (Disc 1).chd", "chd"),
        ]

        assert [f.file_name for f in playlist_files(files)] == [
            "G (Disc 1).chd",
            "G (Disc 2).chd",
            "G (Disc 10).chd",
        ]

    def test_a_set_that_mixes_spellings_still_orders(self):
        files = [
            _make_file("G (CD 2).chd", "chd"),
            _make_file("G (Disc 1).chd", "chd"),
        ]

        assert [f.file_name for f in playlist_files(files)] == [
            "G (Disc 1).chd",
            "G (CD 2).chd",
        ]

    def test_a_tosec_disk_set_orders_past_nine(self):
        files = [
            _make_file("G (Disk 10 of 12).adf", "adf"),
            _make_file("G (Disk 2 of 12).adf", "adf"),
        ]

        assert [f.file_name for f in playlist_files(files)] == [
            "G (Disk 2 of 12).adf",
            "G (Disk 10 of 12).adf",
        ]

    def test_an_unnumbered_disc_follows_the_numbered_ones(self):
        """The first entry is what boots, so a bonus disc cannot take it."""
        files = [
            _make_file("Bonus Disc.chd", "chd"),
            _make_file("G (Disc 2).chd", "chd"),
            _make_file("G (Disc 1).chd", "chd"),
        ]

        assert [f.file_name for f in playlist_files(files)] == [
            "G (Disc 1).chd",
            "G (Disc 2).chd",
            "Bonus Disc.chd",
        ]

    def test_a_lettered_set_boots_from_disc_a(self):
        files = [
            _make_file("A Making Of.chd", "chd"),
            _make_file("G (disc b).chd", "chd"),
            _make_file("G (Disc A).chd", "chd"),
        ]

        assert [f.file_name for f in playlist_files(files)] == [
            "G (Disc A).chd",
            "G (disc b).chd",
            "A Making Of.chd",
        ]

    def test_an_unnumbered_set_keeps_its_name_order(self):
        files = [
            _make_file("beta.chd", "chd"),
            _make_file("alpha.chd", "chd"),
        ]

        assert [f.file_name for f in playlist_files(files)] == ["alpha.chd", "beta.chd"]

    def test_the_playlist_lists_the_discs_in_order(self):
        files = [
            _make_file("G (Disc 10).chd", "chd"),
            _make_file("G (Disc 2).chd", "chd"),
        ]

        assert generate_m3u_content(files, hidden_folder=False) == (
            b"G (Disc 2).chd\nG (Disc 10).chd"
        )
