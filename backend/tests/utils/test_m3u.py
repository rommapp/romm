from unittest.mock import MagicMock

from utils.m3u import generate_m3u_content


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
