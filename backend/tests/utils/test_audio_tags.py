from unittest.mock import MagicMock

from mutagen.mp4 import MP4, MP4Cover

from utils.audio_tags import (
    _extract_picture_from_mp4,
    _parse_leading_int,
    _parse_year,
    track_meta_columns,
)


class TestParseYear:
    def test_clean(self):
        assert _parse_year("1992") == 1992

    def test_iso_date(self):
        assert _parse_year("1992-03-01") == 1992

    def test_suffixed(self):
        assert _parse_year("1992 (Remaster)") == 1992

    def test_no_digits(self):
        assert _parse_year("unknown") is None

    def test_none(self):
        assert _parse_year(None) is None

    def test_empty(self):
        assert _parse_year("") is None


class TestParseLeadingInt:
    def test_plain(self):
        assert _parse_leading_int("5") == 5

    def test_track_of_total(self):
        assert _parse_leading_int("3/12") == 3

    def test_leading_zero(self):
        assert _parse_leading_int("01") == 1

    def test_non_numeric_prefix(self):
        assert _parse_leading_int("A3") is None

    def test_none(self):
        assert _parse_leading_int(None) is None

    def test_over_smallint(self):
        assert _parse_leading_int("99999") is None


class TestTrackMetaColumns:
    def test_full_parse(self):
        cols = track_meta_columns(
            {
                "title": "Theme",
                "artist": "X",
                "album": "OST",
                "genre": "Chiptune",
                "year": "1992-03",
                "track": "3/12",
                "disc": "1",
                "duration_seconds": 90.5,
                "has_embedded_cover": True,
                "cover_path": "covers/1.jpg",
            }
        )
        assert cols == {
            "title": "Theme",
            "artist": "X",
            "album": "OST",
            "genre": "Chiptune",
            "year": 1992,
            "track": 3,
            "disc": 1,
            "duration_seconds": 90.5,
            "has_embedded_cover": True,
            "cover_path": "covers/1.jpg",
        }

    def test_drops_transient_keys(self):
        cols = track_meta_columns({"title": "T", "file_mtime": 123.0, "file_size": 999})
        assert "file_mtime" not in cols
        assert "file_size" not in cols

    def test_empty_defaults(self):
        cols = track_meta_columns({})
        assert cols["title"] is None
        assert cols["year"] is None
        assert cols["track"] is None
        assert cols["has_embedded_cover"] is False
        assert cols["cover_path"] is None

    def test_truncates_overlong_text(self):
        cols = track_meta_columns({"title": "x" * 1000, "genre": "y" * 1000})
        assert len(cols["title"]) == 512
        assert len(cols["genre"]) == 255


class TestExtractPictureFromMp4:
    def _mp4_with_covers(self, covers: list[MP4Cover] | None) -> MP4:
        audio = MagicMock(spec=MP4)
        audio.tags = {"covr": covers} if covers is not None else None
        return audio

    def test_jpeg_cover(self):
        cover_data = b"\xff\xd8\xff fake jpeg"
        audio = self._mp4_with_covers(
            [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
        )
        assert _extract_picture_from_mp4(audio) == (cover_data, "image/jpeg")

    def test_png_cover(self):
        cover_data = b"\x89PNG fake png"
        audio = self._mp4_with_covers(
            [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_PNG)]
        )
        assert _extract_picture_from_mp4(audio) == (cover_data, "image/png")

    def test_no_covr_tag(self):
        audio = MagicMock(spec=MP4)
        audio.tags = None
        assert _extract_picture_from_mp4(audio) is None

    def test_empty_covr_list(self):
        audio = self._mp4_with_covers([])
        assert _extract_picture_from_mp4(audio) is None
