import hashlib
import struct
from pathlib import Path
from typing import Any

import pytest
from tests.utils.nup_builder import (
    FLAG_STANDALONE_UPDATE,
    KIND_ADDON,
    KIND_BASE,
    KIND_SYSTEM,
    KIND_UPDATE,
    Corruption,
    Pkg,
    build_nup,
)

from utils.nup import (
    MAX_TOC_SIZE,
    NupError,
    NupHeader,
    NupPackage,
    looks_like_nup,
    read_header,
)

GOLDEN = Path(__file__).parent / "fixtures" / "nup" / "reference_s2.nup"

S1_BASE = 0x0100ABCD12340000
S2_BASE = 0x040074A01BF12000
S2_DLC = 0x040074A01BF13001

S2_FULL = (
    Pkg(S2_BASE, KIND_BASE, 0),
    Pkg(S2_BASE, KIND_UPDATE, 0x70000),
    Pkg(S2_DLC, KIND_ADDON, 0),
)
NPDM = (("main.npdm", b"META" + b"\0" * 60), ("hello.bin", b"hello nup"))


def write(tmp_path: Path, data: bytes, name: str = "game.nup") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def superblock(data: bytes) -> tuple[Any, ...]:
    return struct.unpack_from("<4sHHQQ32sQQII16s32s", data, 0)


class TestByteLevelSanity:
    @pytest.mark.parametrize(
        "data",
        [build_nup(S2_FULL, files=NPDM), GOLDEN.read_bytes()],
        ids=["builder", "golden"],
    )
    def test_superblock_matches_the_bytes(self, data: bytes):
        magic, header_size, _, toc_offset, toc_size, toc_sha, blob_offset, size = (
            superblock(data)[:8]
        )

        assert magic == b"NUP\x01"
        assert header_size == toc_offset == 0x80
        assert size == len(data)
        assert blob_offset % 16 == 0
        assert blob_offset >= toc_offset + toc_size
        assert hashlib.sha256(data[toc_offset : toc_offset + toc_size]).digest() == (
            toc_sha
        )

    def test_golden_fixture_is_the_recorded_file(self):
        assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == (
            "2b71d2724390546e57f60da321305824b04b6df6057cad5ce96d4a203a313aaf"
        )


class TestReadHeader:
    def test_golden_fixture_from_the_reference_tool(self):
        header = read_header(GOLDEN)

        assert header.packages == (
            NupPackage("040074A01BF12000", "base", 0, False),
            NupPackage("040074A01BF12000", "update", 0x70000, False),
            NupPackage("040074A01BF13001", "addon", 0, False),
        )
        assert header.primary == header.packages[0]
        assert header.effective_version == 0x70000
        assert header.role == "base"
        assert header.is_switch2

    def test_switch_1_base(self, tmp_path: Path):
        header = read_header(write(tmp_path, build_nup([Pkg(S1_BASE, version=0)])))

        assert header.packages == (NupPackage("0100ABCD12340000", "base", 0, False),)
        assert header.role == "base"
        assert header.effective_version == 0
        assert not header.is_switch2

    def test_switch_2_base_update_and_dlc(self, tmp_path: Path):
        header = read_header(write(tmp_path, build_nup(S2_FULL, files=NPDM)))

        assert [p.kind for p in header.packages] == ["base", "update", "addon"]
        assert header.primary.title_id == "040074A01BF12000"
        assert header.effective_version == 0x70000
        assert header.role == "base"
        assert header.is_switch2

    def test_standalone_update(self, tmp_path: Path):
        data = build_nup([Pkg(S1_BASE, KIND_UPDATE, 0x10000, FLAG_STANDALONE_UPDATE)])

        header = read_header(write(tmp_path, data))

        assert header.primary == NupPackage("0100ABCD12340000", "update", 0x10000, True)
        assert header.effective_version == 0x10000
        assert header.role == "update"

    def test_dlc_only(self, tmp_path: Path):
        header = read_header(
            write(tmp_path, build_nup([Pkg(0x0100ABCD12341001, KIND_ADDON, 0x30000)]))
        )

        assert header.primary.title_id == "0100ABCD12341001"
        assert header.effective_version == 0x30000
        assert header.role == "dlc"

    def test_switch_2_edition_keeps_a_switch_1_id(self, tmp_path: Path):
        data = build_nup([Pkg(S1_BASE), Pkg(0x0100ABCD12341001, KIND_ADDON)])

        header = read_header(write(tmp_path, data))

        assert header.role == "base"
        assert not header.is_switch2

    def test_system_only_has_no_role(self, tmp_path: Path):
        header = read_header(
            write(tmp_path, build_nup([Pkg(0x0100000000000809, KIND_SYSTEM)]))
        )

        assert header.role == "unknown"

    def test_primary_is_the_first_base_in_any_position(self, tmp_path: Path):
        data = build_nup([Pkg(S2_DLC, KIND_ADDON, 0x50000), Pkg(S2_BASE, version=0)])

        header = read_header(write(tmp_path, data))

        assert header.primary.kind == "base"
        assert header.effective_version == 0

    def test_never_reads_past_the_toc(self, tmp_path: Path):
        data = bytearray(build_nup(S2_FULL, files=NPDM))
        blob_offset = superblock(bytes(data))[6]
        data[blob_offset:] = b"\xaa" * (len(data) - blob_offset)

        header = read_header(write(tmp_path, bytes(data)))

        assert header.role == "base"

    def test_accepts_a_path_string(self, tmp_path: Path):
        path = write(tmp_path, build_nup([Pkg(S1_BASE)]))

        assert isinstance(read_header(str(path)), NupHeader)


class TestRejects:
    @pytest.mark.parametrize(
        ("corrupt", "reason"),
        [
            ("magic", "not a NUP"),
            ("major", "major version 2"),
            ("toc_hash", "hash mismatch"),
            ("file_size", "actual size"),
            ("toc_size_cap", f"exceeds {MAX_TOC_SIZE}"),
            ("meta_oob", "meta block"),
        ],
    )
    def test_corruption(self, tmp_path: Path, corrupt: Corruption, reason: str):
        data = build_nup(S2_FULL, files=NPDM, corrupt=corrupt)

        with pytest.raises(NupError, match=reason):
            read_header(write(tmp_path, data))

    @pytest.mark.parametrize(
        ("packages", "reason"),
        [
            ([Pkg(S1_BASE, kind=5)], "unknown kind 5"),
            ([Pkg(S1_BASE, flags=0x02)], "unknown flags"),
            ([Pkg(S1_BASE, KIND_UPDATE, 0x10000)], "standalone"),
        ],
        ids=["kind", "flag", "update-without-base"],
    )
    def test_invalid_package(self, tmp_path: Path, packages: list[Pkg], reason: str):
        with pytest.raises(NupError, match=reason):
            read_header(write(tmp_path, build_nup(packages)))

    def test_zero_byte_file(self, tmp_path: Path):
        with pytest.raises(NupError, match="truncated superblock"):
            read_header(write(tmp_path, b""))

    def test_truncated_download(self, tmp_path: Path):
        data = build_nup(S2_FULL, files=NPDM)

        with pytest.raises(NupError, match="actual size"):
            read_header(write(tmp_path, data[:-4]))

    def test_missing_file_raises_os_error(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_header(tmp_path / "missing.nup")


class TestLooksLikeNup:
    def test_magic(self):
        assert looks_like_nup(build_nup([Pkg(S1_BASE)])[:16])

    @pytest.mark.parametrize("head", [b"", b"NUP", b"NUP\x02", b"PFS0\0\0\0\0"])
    def test_other_bytes(self, head: bytes):
        assert not looks_like_nup(head)
