from unittest.mock import MagicMock

from utils.m3u import generate_m3u_content, playlist_files


def _make_file(name: str, extension: str, download_name: str | None = None):
    f = MagicMock()
    f.file_extension = extension
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
