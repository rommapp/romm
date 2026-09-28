from pathlib import Path

import pytest
from tests.chiptune_fixtures import hes_bytes, nsf_bytes

from utils import gme
from utils.gme import read_songs, sidecar_m3u_path


def _write(tmp_path: Path, name: str, data: bytes | str) -> str:
    path = tmp_path / name
    if isinstance(data, str):
        path.write_text(data)
    else:
        path.write_bytes(data)
    return str(path)


class TestReadSongs:
    def test_lists_every_song_of_annsf_bytes(self, tmp_path: Path):
        songs = read_songs(_write(tmp_path, "game.nsf", nsf_bytes(3)))

        assert songs is not None
        assert [song.index for song in songs] == [0, 1, 2]
        first = songs[0].tags
        assert first["album"] == "Mega Game"
        assert first["artist"] == "Composer"
        assert first["year"] == "1990 Maker"
        assert first["track"] == "1"
        # libgme's 2:30 default plus the player's fade.
        assert first["duration_seconds"] == 158.0

    def test_m3u_names_orders_and_times_the_songs(self, tmp_path: Path):
        path = _write(tmp_path, "game.nsf", nsf_bytes(3))
        m3u = _write(
            tmp_path,
            "game.m3u",
            "game.nsf::NSF,3,Boss Theme,1:02\ngame.nsf::NSF,1,Title,0:45\n",
        )

        songs = read_songs(path, m3u)

        assert songs is not None
        assert [song.tags["title"] for song in songs] == ["Boss Theme", "Title"]
        fade = gme.DEFAULT_FADE_MS / 1000
        assert [song.tags["duration_seconds"] for song in songs] == [
            62 + fade,
            45 + fade,
        ]

    def test_hes_stays_one_song_without_a_playlist(self, tmp_path: Path):
        songs = read_songs(_write(tmp_path, "game.hes", hes_bytes()))

        assert songs is not None
        assert [song.index for song in songs] == [0]
        assert songs[0].tags["track"] is None

    def test_hes_lists_its_playlist(self, tmp_path: Path):
        path = _write(tmp_path, "game.hes", hes_bytes())
        m3u = _write(
            tmp_path,
            "game.m3u",
            "game.hes::HES,$10,Stage 1,2:00\ngame.hes::HES,$11,Stage 2,1:30\n",
        )

        songs = read_songs(path, m3u)

        assert songs is not None
        assert [(song.index, song.tags["title"]) for song in songs] == [
            (0, "Stage 1"),
            (1, "Stage 2"),
        ]

    def test_unreadable_files(self, tmp_path: Path):
        assert read_songs(_write(tmp_path, "junk.nsf", b"garbage")) is None
        assert read_songs(str(tmp_path / "missing.nsf")) is None

    def test_skips_a_file_over_the_size_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        data = nsf_bytes(2)
        monkeypatch.setattr(gme, "MAX_CHIPTUNE_BYTES", len(data) - 1)

        assert read_songs(_write(tmp_path, "game.nsf", data)) is None

    def test_ignores_a_playlist_over_the_size_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        path = _write(tmp_path, "game.nsf", nsf_bytes(3))
        m3u = _write(tmp_path, "game.m3u", "game.nsf::NSF,2,Only Song\n")
        monkeypatch.setattr(gme, "MAX_M3U_BYTES", 4)

        songs = read_songs(path, m3u)

        assert songs is not None
        assert [song.tags["title"] for song in songs] == [None, None, None]

    def test_without_libgme(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(gme, "_libgme", lambda: None)

        assert read_songs(_write(tmp_path, "game.nsf", nsf_bytes(2))) is None


class TestSidecarM3uPath:
    def test_matches_the_stem_case_insensitively(self, tmp_path: Path):
        path = _write(tmp_path, "Game.nsf", b"")
        _write(tmp_path, "game.M3U", "")
        _write(tmp_path, "other.m3u", "")

        assert sidecar_m3u_path(path) == str(tmp_path / "game.M3U")

    def test_none_without_one(self, tmp_path: Path):
        assert sidecar_m3u_path(_write(tmp_path, "Game.nsf", b"")) is None
