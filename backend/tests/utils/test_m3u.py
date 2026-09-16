from unittest.mock import MagicMock

from utils.m3u import first_playlist_entry, generate_m3u_content


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

    def test_no_cue_files_lists_all(self):
        files = [
            _make_file("disc1.chd", "chd"),
            _make_file("disc2.chd", "chd"),
        ]
        result = generate_m3u_content(files, hidden_folder=False)
        lines = result.decode().split("\n")
        assert len(lines) == 2
