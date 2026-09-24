import struct
import zipfile

import pytest

from handler.cloud_sync_psp import (
    _BUNDLE_MAX_MEMBERS,
    PspFilePath,
    _bundle_folder,
    _load_bundle_entries,
    _write_bundle,
    is_psp_bundle_file_name,
    parse_sfo,
    resolve_psp_path,
)


def _build_fake_sfo(fields: dict[str, str | int]) -> bytes:
    """Builds a minimal valid PARAM.SFO buffer for the given fields, to
    round-trip against `parse_sfo` without needing a real PPSSPP capture."""
    key_table = bytearray()
    data_table = bytearray()
    entries = []

    for key, value in fields.items():
        key_offset = len(key_table)
        key_table += key.encode("ascii") + b"\x00"

        data_offset = len(data_table)
        if isinstance(value, int):
            data_fmt = 0x0404
            data_bytes = struct.pack("<i", value)
        else:
            data_fmt = 0x0204
            data_bytes = value.encode("utf-8") + b"\x00"
        data_table += data_bytes

        entries.append((key_offset, data_fmt, len(data_bytes), data_offset))

    header_size = 20
    index_table_size = len(entries) * 16
    key_table_offset = header_size + index_table_size
    data_table_offset = key_table_offset + len(key_table)

    header = b"\x00PSF" + struct.pack(
        "<IIII", 0x0101, key_table_offset, data_table_offset, len(entries)
    )
    index_table = b"".join(
        struct.pack("<HHIII", key_offset, data_fmt, data_len, data_len, data_offset)
        for key_offset, data_fmt, data_len, data_offset in entries
    )

    return header + index_table + bytes(key_table) + bytes(data_table)


class TestResolvePspPath:
    def test_parses_a_savedata_file(self):
        assert resolve_psp_path(
            "saves/PPSSPP/PSP/SAVEDATA/ULUS10336DATA0/PARAM.SFO"
        ) == PspFilePath(
            emulator="ppsspp", save_folder="ULUS10336DATA0", file_name="PARAM.SFO"
        )

    def test_parses_a_savedata_file_without_a_core_folder(self):
        assert resolve_psp_path(
            "saves/PSP/SAVEDATA/ULUS10336DATA0/PARAM.SFO"
        ) == PspFilePath(
            emulator=None, save_folder="ULUS10336DATA0", file_name="PARAM.SFO"
        )
        assert resolve_psp_path("saves/PSP/SYSTEM/CACHE/shader.bin") == "ignore"

    @pytest.mark.parametrize(
        "path",
        [
            "saves/PPSSPP/PSP/SAVEDATA/../PARAM.SFO",
            "saves/PPSSPP/PSP/SAVEDATA/ULUS10336DATA0/..",
            "saves/PPSSPP/PSP/SAVEDATA/./PARAM.SFO",
        ],
    )
    def test_rejects_traversal_segments(self, path):
        assert resolve_psp_path(path) is None

    def test_ignores_system_cache_files(self):
        assert resolve_psp_path("saves/PPSSPP/PSP/SYSTEM/CACHE/shader.bin") == "ignore"

    def test_non_psp_save_is_none(self):
        assert resolve_psp_path("saves/Snes9x/test_rom.srm") is None

    def test_psp_path_missing_savedata_segment_is_none(self):
        assert resolve_psp_path("saves/PPSSPP/PSP/SAVEDATA") is None

    def test_unrelated_category_is_none(self):
        assert resolve_psp_path("saves/PPSSPP/PSP/OTHER/foo") is None


class TestIsPspBundleFileName:
    def test_matches_bundle_names(self):
        assert is_psp_bundle_file_name("PSP-ULUS10336DATA0.zip")

    def test_rejects_normal_saves(self):
        assert not is_psp_bundle_file_name("test_rom.srm")


class TestBundleFolder:
    def test_parses_the_folder_and_its_tagged_names(self):
        assert _bundle_folder("PSP-ULUS10336DATA0.zip") == "ULUS10336DATA0"
        assert (
            _bundle_folder("PSP-ULUS10336DATA0 [2026-01-01 00-00-00].zip")
            == "ULUS10336DATA0"
        )

    def test_keeps_a_longer_folder_name_whole(self):
        assert _bundle_folder("PSP-FOO-BAR.zip") == "FOO-BAR"
        assert _bundle_folder("PSP-FOO.BAR.zip") == "FOO.BAR"

    def test_rejects_non_bundles(self):
        assert _bundle_folder("test_rom.srm") is None


class TestLoadBundleEntries:
    def test_round_trips_members(self):
        entries = {"PARAM.SFO": b"sfo", "DATA.BIN": b"data"}
        assert _load_bundle_entries(_write_bundle(entries)) == entries

    def test_rejects_too_many_members(self):
        entries = {f"{i}.BIN": b"" for i in range(_BUNDLE_MAX_MEMBERS + 1)}
        with pytest.raises(zipfile.BadZipFile):
            _load_bundle_entries(_write_bundle(entries))


class TestParseSfo:
    def test_rejects_bad_magic(self):
        with pytest.raises(ValueError):
            parse_sfo(b"not an sfo file at all")

    def test_parses_title_and_serial(self):
        sfo = _build_fake_sfo(
            {"DISC_ID": "ULUS10336", "TITLE": "CRISIS CORE -FINAL FANTASY VII-"}
        )
        parsed = parse_sfo(sfo)
        assert parsed["DISC_ID"] == "ULUS10336"
        assert parsed["TITLE"] == "CRISIS CORE -FINAL FANTASY VII-"

    def test_parses_integer_fields(self):
        sfo = _build_fake_sfo({"SAVEDATA_FILE_LIST": 0, "PARENTAL_LEVEL": 3})
        parsed = parse_sfo(sfo)
        assert parsed["PARENTAL_LEVEL"] == 3

    def test_truncated_index_table_is_a_value_error(self):
        header = b"\x00PSF" + struct.pack("<IIII", 0x0101, 20, 20, 1000)
        with pytest.raises(ValueError):
            parse_sfo(header)
