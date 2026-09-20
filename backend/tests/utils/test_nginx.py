"""Tests for the nginx response helpers."""

import pytest

from utils.nginx import ZipContentLine, ZipResponse


class TestZipContentLine:
    """The manifest is line-oriented, so a line must render as exactly one record."""

    def test_renders_the_mod_zip_field_order(self):
        line = ZipContentLine(
            crc32="deadbeef",
            size_bytes=42,
            encoded_location="/library/roms/gc/game/disc.iso",
            filename="roms/gc/game/disc.iso",
        )

        assert (
            str(line)
            == "deadbeef 42 /library/roms/gc/game/disc.iso roms/gc/game/disc.iso"
        )

    def test_renders_a_missing_crc32_as_a_hyphen(self):
        line = ZipContentLine(
            crc32=None,
            size_bytes=42,
            encoded_location="/library/rom.iso",
            filename="rom.iso",
        )

        assert str(line).startswith("- 42 ")

    @pytest.mark.parametrize("control", ["\n", "\r", "\t", "\0", "\x7f"])
    def test_replaces_control_characters_in_the_filename(self, control: str):
        line = ZipContentLine(
            crc32=None,
            size_bytes=3,
            encoded_location="/library/rom.iso",
            filename=f"a{control}b",
        )

        assert line.filename == "a_b"
        assert str(line).count("\n") == 0

    def test_a_forged_filename_stays_one_record(self):
        """A folder named on disk to look like a second manifest entry."""
        line = ZipContentLine(
            crc32=None,
            size_bytes=8,
            encoded_location="/library/roms/gc/game/disc.iso",
            filename="roms/gc/a\n- 3 /decode?value=cG5n pwned/disc.iso",
        )

        assert "\n" not in str(line)

    @pytest.mark.parametrize(
        "location",
        ["/library/a b.iso", "/library/a\nb.iso", "/decode?value=cG5n\x7f"],
    )
    def test_rejects_an_unencoded_location(self, location: str):
        with pytest.raises(ValueError, match="URL-encoded"):
            ZipContentLine(
                crc32=None,
                size_bytes=1,
                encoded_location=location,
                filename="rom.iso",
            )

    def test_accepts_the_m3u_decode_location(self):
        line = ZipContentLine(
            crc32="deadbeef",
            size_bytes=4,
            encoded_location="/decode?value=YS9iCg==",
            filename="game.m3u",
        )

        assert line.encoded_location == "/decode?value=YS9iCg=="


class TestZipResponse:
    def test_body_holds_one_line_per_entry(self):
        lines = [
            ZipContentLine(
                crc32=None,
                size_bytes=3,
                encoded_location=f"/library/rom{i}.iso",
                filename=f"a\nrom{i}.iso",
            )
            for i in range(3)
        ]

        response = ZipResponse(content_lines=lines, filename="roms.zip")

        assert len(response.body.decode().splitlines()) == 3
        assert response.headers["x-archive-files"] == "zip"

    def test_rejects_a_caller_supplied_body(self):
        with pytest.raises(ValueError, match="must not be provided"):
            ZipResponse(content_lines=[], filename="roms.zip", content="whatever")
