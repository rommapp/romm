import base64
import io
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import mutagen
import pytest
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TPOS, TRCK
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image
from pytest_mock import MockerFixture

import config
from utils import audio_tags
from utils.audio_tags import (
    _allowed_mime_types,
    _extract_picture_from_mp4,
    _parse_leading_int,
    _parse_year,
    extract_audio_meta,
    extract_embedded_cover,
    guess_audio_media_type,
    is_allowed_audio_file,
    is_chiptune_file,
    persist_embedded_cover,
    remove_persisted_cover,
    track_meta_columns,
)


class TestIsChiptuneFile:
    @pytest.mark.parametrize("name", ["Stage 1.SPC", "intro.vgz", "Theme.vgm"])
    def test_chiptune(self, name):
        assert is_chiptune_file(name)

    @pytest.mark.parametrize("name", ["Theme.mp3", "Theme.nsf", "spc"])
    def test_other(self, name):
        assert not is_chiptune_file(name)

    def test_served_as_binary(self):
        assert guess_audio_media_type("Stage 1.spc") == "application/octet-stream"


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
        cover_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        audio = self._mp4_with_covers(
            [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
        )
        assert _extract_picture_from_mp4(audio) == (cover_data, "image/jpeg")

    def test_png_cover(self):
        cover_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
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

    def test_unknown_format_sniffs_jpeg(self):
        cover_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        audio = self._mp4_with_covers([MP4Cover(cover_data)])
        assert _extract_picture_from_mp4(audio) == (cover_data, "image/jpeg")

    def test_rejects_gif_labeled_as_jpeg(self):
        cover_data = b"GIF89a\x00\x00\x01\x00\x01"
        audio = self._mp4_with_covers(
            [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
        )
        with pytest.raises(ValueError, match="JPEG or PNG"):
            _extract_picture_from_mp4(audio)


class TestAllowedMimeTypes:
    def test_sniffs_png(self):
        data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        assert _allowed_mime_types(data) == "image/png"

    def test_sniffs_jpeg(self):
        data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        assert _allowed_mime_types(data) == "image/jpeg"

    def test_rejects_gif(self):
        with pytest.raises(ValueError, match="JPEG or PNG"):
            _allowed_mime_types(b"GIF89a")


class TestPersistEmbeddedCover:
    def test_extraction_failure_returns_none_without_raising(self):
        """A cover that fails to extract (e.g. unsupported format) must not
        raise out of persist_embedded_cover, and must not be written to disk."""
        with (
            patch(
                "utils.audio_tags.extract_embedded_cover",
                side_effect=ValueError("embedded cover is not JPEG or PNG"),
            ),
            patch("builtins.open") as mock_open,
        ):
            result = persist_embedded_cover(
                audio_full_path="/fake/track.m4a",
                platform_id=1,
                rom_id=1,
                file_id=1,
            )
        assert result is None
        mock_open.assert_not_called()


# Silent, untagged files from ffmpeg (8 kHz mono); each test writes the tags it needs.
FIXTURES = Path(__file__).parent / "fixtures" / "audio"
FORMATS = ["mp3", "flac", "ogg", "opus", "m4a"]

TAGS = {
    "title": "Green Hill Zone",
    "artist": "Masato Nakamura",
    "album": "Sonic OST",
    "year": "1991",
    "genre": "Chiptune",
    "track": "3",
    "disc": "1",
}


def _image(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(buffer, format=fmt)
    return buffer.getvalue()


PNG = _image("PNG")
JPEG = _image("JPEG")
GIF = _image("GIF")
MIME = {PNG: "image/png", JPEG: "image/jpeg", GIF: "image/gif"}
MP4_FORMAT = {PNG: MP4Cover.FORMAT_PNG, JPEG: MP4Cover.FORMAT_JPEG}


def _copy(tmp_path: Path, ext: str) -> Path:
    path = tmp_path / f"track.{ext}"
    shutil.copyfile(FIXTURES / f"silence.{ext}", path)
    return path


def _flac_picture(data: bytes) -> Picture:
    picture = Picture()
    picture.type = 3
    picture.mime = MIME[data]
    picture.data = data
    return picture


def _tag(path: Path, cover: bytes | None = None) -> Path:
    """Write TAGS, and a cover when given, the way each format stores them."""
    ext = path.suffix[1:]
    if ext == "mp3":
        id3 = ID3()
        for frame, key in [
            (TIT2, "title"),
            (TPE1, "artist"),
            (TALB, "album"),
            (TDRC, "year"),
            (TCON, "genre"),
            (TRCK, "track"),
            (TPOS, "disc"),
        ]:
            id3.add(frame(encoding=3, text=TAGS[key]))
        if cover:
            id3.add(APIC(encoding=3, mime=MIME[cover], type=3, data=cover))
        id3.save(path)
    elif ext == "m4a":
        mp4 = MP4(path)
        mp4["\xa9nam"] = TAGS["title"]
        mp4["\xa9ART"] = TAGS["artist"]
        mp4["\xa9alb"] = TAGS["album"]
        mp4["\xa9day"] = TAGS["year"]
        mp4["\xa9gen"] = TAGS["genre"]
        mp4["trkn"] = [(3, 12)]
        mp4["disk"] = [(1, 2)]
        if cover:
            # MP4 has no GIF format, so a GIF is labelled JPEG, as taggers do.
            mp4["covr"] = [
                MP4Cover(cover, imageformat=MP4_FORMAT.get(cover, MP4Cover.FORMAT_JPEG))
            ]
        mp4.save()
    else:
        audio = FLAC(path) if ext == "flac" else mutagen.File(path)
        assert audio is not None
        for key, tag in [
            ("title", "title"),
            ("artist", "artist"),
            ("album", "album"),
            ("year", "date"),
            ("genre", "genre"),
            ("track", "tracknumber"),
            ("disc", "discnumber"),
        ]:
            audio[tag] = TAGS[key]
        if cover and isinstance(audio, FLAC):
            audio.add_picture(_flac_picture(cover))
        elif cover:
            audio["metadata_block_picture"] = [
                base64.b64encode(_flac_picture(cover).write()).decode()
            ]
        audio.save()
    return path


class TestExtractAudioMeta:
    @pytest.mark.parametrize("ext", FORMATS)
    def test_reads_the_tags_and_duration(self, tmp_path: Path, ext: str):
        path = _tag(_copy(tmp_path, ext))

        meta = extract_audio_meta(str(path))

        assert meta is not None
        assert {key: meta.get(key) for key in TAGS} == TAGS
        duration = meta.get("duration_seconds")
        assert duration is not None and 0 < duration < 1
        assert meta.get("has_embedded_cover") is False
        assert meta.get("file_size") == path.stat().st_size
        assert meta.get("file_mtime") == path.stat().st_mtime

    @pytest.mark.parametrize("ext", FORMATS)
    def test_notices_an_embedded_cover(self, tmp_path: Path, ext: str):
        path = _tag(_copy(tmp_path, ext), cover=PNG)

        meta = extract_audio_meta(str(path))

        assert meta is not None
        assert meta.get("has_embedded_cover") is True

    @pytest.mark.parametrize("ext", FORMATS)
    def test_an_untagged_file_has_no_tags(self, tmp_path: Path, ext: str):
        meta = extract_audio_meta(str(_copy(tmp_path, ext)))

        assert meta is not None
        assert all(meta.get(key) is None for key in TAGS)
        assert meta.get("has_embedded_cover") is False

    def test_a_missing_file_is_none(self, tmp_path: Path):
        assert extract_audio_meta(str(tmp_path / "gone.mp3")) is None

    def test_a_file_that_is_not_audio_is_none(self, tmp_path: Path):
        path = tmp_path / "track.mp3"
        path.write_bytes(b"\x00" * 64)

        assert extract_audio_meta(str(path)) is None

    def test_an_oversized_file_is_not_parsed(
        self, tmp_path: Path, mocker: MockerFixture
    ):
        path = _tag(_copy(tmp_path, "mp3"))
        mocker.patch.object(audio_tags, "MAX_AUDIO_PARSE_BYTES", 10)
        parse = mocker.spy(mutagen, "File")

        assert extract_audio_meta(str(path)) is None
        parse.assert_not_called()


class TestExtractEmbeddedCover:
    @pytest.mark.parametrize("ext", FORMATS)
    @pytest.mark.parametrize(
        ("cover", "mime"), [(PNG, "image/png"), (JPEG, "image/jpeg")]
    )
    def test_returns_the_cover_and_its_type(
        self, tmp_path: Path, ext: str, cover: bytes, mime: str
    ):
        path = _tag(_copy(tmp_path, ext), cover=cover)

        assert extract_embedded_cover(str(path)) == (cover, mime)

    @pytest.mark.parametrize("ext", FORMATS)
    def test_no_cover_is_none(self, tmp_path: Path, ext: str):
        path = _tag(_copy(tmp_path, ext))

        assert extract_embedded_cover(str(path)) is None

    @pytest.mark.parametrize("ext", FORMATS)
    def test_a_cover_that_is_not_jpeg_or_png_raises(self, tmp_path: Path, ext: str):
        path = _tag(_copy(tmp_path, ext), cover=GIF)

        with pytest.raises(ValueError, match="JPEG or PNG"):
            extract_embedded_cover(str(path))

    @pytest.mark.parametrize("ext", ["ogg", "opus"])
    def test_an_undecodable_ogg_picture_is_skipped(self, tmp_path: Path, ext: str):
        path = _copy(tmp_path, ext)
        audio = mutagen.File(path)
        assert audio is not None
        audio["metadata_block_picture"] = ["not a picture block"]
        audio.save()

        assert extract_embedded_cover(str(path)) is None

    def test_a_file_that_is_not_audio_is_none(self, tmp_path: Path):
        path = tmp_path / "track.mp3"
        path.write_bytes(b"\x00" * 64)

        assert extract_embedded_cover(str(path)) is None


class TestPersistedCover:
    @pytest.fixture
    def resources(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        root = tmp_path / "resources"
        monkeypatch.setattr(config, "RESOURCES_BASE_PATH", str(root))
        return root

    def test_writes_the_cover_under_the_rom(self, tmp_path: Path, resources: Path):
        audio = _tag(_copy(tmp_path, "flac"), cover=JPEG)

        rel_path = persist_embedded_cover(
            str(audio), platform_id=4, rom_id=7, file_id=12
        )

        assert rel_path == "roms/4/7/soundtracks/12.jpg"
        assert (resources / rel_path).read_bytes() == JPEG

    def test_writes_nothing_without_a_cover(self, tmp_path: Path, resources: Path):
        audio = _tag(_copy(tmp_path, "mp3"))

        assert persist_embedded_cover(str(audio), 4, 7, 12) is None
        assert not resources.exists()

    def test_a_failed_write_is_none(self, tmp_path: Path, resources: Path):
        audio = _tag(_copy(tmp_path, "mp3"), cover=PNG)
        resources.mkdir()
        (resources / "roms").write_text("a file where the folder should be")

        assert persist_embedded_cover(str(audio), 4, 7, 12) is None

    def test_removes_a_persisted_cover(self, tmp_path: Path, resources: Path):
        audio = _tag(_copy(tmp_path, "mp3"), cover=PNG)
        rel_path = persist_embedded_cover(str(audio), 4, 7, 12)
        assert rel_path

        assert remove_persisted_cover(rel_path)
        assert not (resources / rel_path).exists()

    @pytest.mark.parametrize("cover_path", [None, "", "roms/4/7/soundtracks/9.png"])
    def test_nothing_to_remove_counts_as_removed(
        self, resources: Path, cover_path: str | None
    ):
        assert remove_persisted_cover(cover_path)

    def test_a_cover_that_cannot_be_removed_is_reported(self, resources: Path):
        stuck = resources / "roms" / "4" / "7" / "soundtracks" / "12.png"
        stuck.mkdir(parents=True)

        assert not remove_persisted_cover("roms/4/7/soundtracks/12.png")
        assert stuck.exists()


class TestAudioFileTypes:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Theme.FLAC", "audio/flac"),
            ("Theme.opus", "audio/ogg"),
            ("Theme.m4a", "audio/mp4"),
            ("Theme.mp3", "audio/mpeg"),
            ("Theme", "application/octet-stream"),
        ],
    )
    def test_guesses_the_media_type(self, name: str, expected: str):
        assert guess_audio_media_type(name) == expected

    @pytest.mark.parametrize("name", ["a.MP3", "b.flac", "c.opus", "d.wav"])
    def test_audio_files_are_allowed(self, name: str):
        assert is_allowed_audio_file(name)

    @pytest.mark.parametrize("name", ["a.spc", "b.txt", "mp3"])
    def test_other_files_are_not(self, name: str):
        assert not is_allowed_audio_file(name)
