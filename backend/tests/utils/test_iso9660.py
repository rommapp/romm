import pytest
from tests.handler.sync.ps3.fakes import build_ps3_iso

from utils.iso9660 import Iso9660, Iso9660Error


class BytesReader:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read_at(self, offset: int, length: int) -> bytes:
        return self.data[offset : offset + length]


class TestIso9660:
    def test_reads_a_nested_file(self):
        iso = Iso9660(BytesReader(build_ps3_iso(b"sfo bytes")))
        assert iso.read_file("PS3_GAME/PARAM.SFO", 1024) == b"sfo bytes"

    def test_matches_names_case_insensitively(self):
        iso = Iso9660(BytesReader(build_ps3_iso(b"sfo bytes")))
        assert iso.read_file("ps3_game/param.sfo", 1024) == b"sfo bytes"

    def test_caps_the_read(self):
        iso = Iso9660(BytesReader(build_ps3_iso(b"sfo bytes")))
        assert iso.read_file("PS3_GAME/PARAM.SFO", 3) == b"sfo"

    def test_none_for_a_missing_file(self):
        iso = Iso9660(BytesReader(build_ps3_iso(b"sfo bytes")))
        assert iso.read_file("PS3_GAME/EBOOT.BIN", 1024) is None

    def test_rejects_an_image_that_is_not_iso9660(self):
        with pytest.raises(Iso9660Error):
            Iso9660(BytesReader(b"\x00" * 40000))
