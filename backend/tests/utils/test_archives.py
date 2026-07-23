import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import archives


def _fake_7z_listing(names: list[str]) -> str:
    """Build a `7zz l -slt -ba` style listing for the given member names."""
    return "\n".join(f"Path = {name}\nSize = 10\nAttributes = A\n" for name in names)


def _fake_7z_listing_sized(
    entries: list[tuple[str, int]], attributes: bool = True
) -> str:
    """Build a `7zz l -slt -ba` style listing with explicit member sizes.

    Single-stream formats (.gz/.xz) list no Attributes line at all, which
    `attributes=False` reproduces.
    """
    blocks = []
    for name, size in entries:
        block = f"Path = {name}\nSize = {size}\n"
        if attributes:
            block += "Attributes = A -rw-rw-r--\n"
        blocks.append(block)
    return "\n".join(blocks)


def _fake_mtree_listing(lines: list[str]) -> bytes:
    """Build a `bsdtar --format=mtree` style listing (always bytes, ASCII-only:
    libarchive octal-escapes every other byte)."""
    return ("#mtree\n" + "\n".join(lines) + "\n").encode()


def _mock_popen_streaming(
    chunk_streams: list[list[bytes]],
    returncodes: list[int],
    stderr: bytes = b"",
):
    """Build a subprocess.Popen mock whose consecutive context-managed calls
    stream the given chunk lists and finish with the given return codes.

    `stderr` bytes are written into the file object the caller passes as the
    `stderr` argument, mirroring 7zz writing diagnostics to a file-backed
    stderr."""
    popen = MagicMock()
    processes = []
    for chunks, returncode in zip(chunk_streams, returncodes, strict=True):
        process = MagicMock()
        process.stdout.read.side_effect = [*chunks, b""]
        process.returncode = returncode
        processes.append(process)
    process_iter = iter(processes)

    def _popen_call(*args, **kwargs):
        stderr_target = kwargs.get("stderr")
        if stderr and stderr_target is not None:
            stderr_target.write(stderr)
        context = MagicMock()
        context.__enter__.return_value = next(process_iter)
        return context

    popen.side_effect = _popen_call
    return popen


def test_stream_7z_chunks_yields_until_eof():
    process = MagicMock()
    process.stdout.read.side_effect = [b"abc", b"def", b""]
    on_timeout = MagicMock()

    chunks = list(
        archives._stream_7z_chunks(
            process, deadline=time.monotonic() + 1000, on_timeout=on_timeout
        )
    )

    assert chunks == [b"abc", b"def"]
    on_timeout.assert_not_called()
    process.terminate.assert_not_called()


def test_stream_7z_chunks_timeout_terminates_and_signals_once():
    process = MagicMock()
    process.stdout.read.side_effect = [b"abc", b"def", b""]
    on_timeout = MagicMock()

    # A deadline in the past trips on the first chunk.
    chunks = list(
        archives._stream_7z_chunks(process, deadline=0.0, on_timeout=on_timeout)
    )

    assert chunks == []
    on_timeout.assert_called_once()
    process.terminate.assert_called_once()


def test_read_7z_archive_files_timeout_raises_without_spawning_per_member(monkeypatch):
    """Once the shared budget is spent, no subprocess is spawned per remaining
    member and the caller is told the archive was not read in full."""
    names = [f"file{i:02d}.bin" for i in range(20)]
    listing = MagicMock(stdout=_fake_7z_listing(names))

    # Force the per-archive deadline to be already in the past.
    monkeypatch.setattr(archives, "SEVEN_ZIP_TIMEOUT", -1)

    with (
        patch.object(archives.subprocess, "run", return_value=listing),
        patch.object(archives.subprocess, "Popen") as popen_patch,
        pytest.raises(archives.ArchiveReadError),
    ):
        list(archives.read_7z_archive_files(Path("/fake.7z"), [], []))

    popen_patch.assert_not_called()


def test_read_7z_archive_files_raises_when_a_member_fails_midway():
    """A member that fails after earlier ones streamed must not leave the
    caller with a usable-looking partial result."""
    listing = MagicMock(stdout=_fake_7z_listing(["a.bin", "b.bin"]))

    popen = _mock_popen_streaming([[b"aaa"], [b"bbb"]], [0, 2])

    with (
        patch.object(archives.subprocess, "run", return_value=listing),
        patch.object(archives.subprocess, "Popen", popen),
        pytest.raises(archives.ArchiveReadError),
    ):
        for _name, _size, chunks in archives.read_7z_archive_files(
            Path("/fake.7z"), [], []
        ):
            list(chunks)


class TestExtractLargestArchiveMember:
    """Extraction of an archive's largest member to a destination directory,
    used to feed RAHasher a real ROM file instead of raw container bytes
    (GitHub issue #3808)."""

    def test_extracts_largest_member_to_dest_dir(self, tmp_path):
        listing = MagicMock(
            stdout=_fake_7z_listing_sized([("small.txt", 10), ("game.gba", 500)])
        )
        popen = _mock_popen_streaming([[b"abc", b"def"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result is not None
        assert result == tmp_path / "game.gba"
        assert result.read_bytes() == b"abcdef"
        # The largest member, not the first, must be requested from 7zz, with
        # wildcard matching disabled so a member name containing "*" or "?"
        # can't select (and concatenate) other members.
        extract_args = popen.call_args[0][0]
        assert "game.gba" in extract_args
        assert "-spd" in extract_args

    def test_member_folder_prefix_is_stripped_from_dest_name(self, tmp_path):
        """Members nested in archive folders extract to a flat file name."""
        listing = MagicMock(stdout=_fake_7z_listing_sized([("subdir/game.gba", 500)]))
        popen = _mock_popen_streaming([[b"abc"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result == tmp_path / "game.gba"

    def test_listing_without_attributes_still_finds_member(self, tmp_path):
        """Single-stream formats (.gz/.xz) list no Attributes line; the member
        must still be found (7zz omits it for them)."""
        listing = MagicMock(
            stdout=_fake_7z_listing_sized([("game.gba", 500)], attributes=False)
        )
        popen = _mock_popen_streaming([[b"abc"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.gba.gz"), tmp_path
            )

        assert result == tmp_path / "game.gba"

    def test_directory_members_are_ignored(self, tmp_path):
        listing = MagicMock(
            stdout=(
                "Path = folder\nSize = 0\nAttributes = D drwxr-xr-x\n\n"
                + _fake_7z_listing_sized([("game.gba", 500)])
            )
        )
        popen = _mock_popen_streaming([[b"abc"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result == tmp_path / "game.gba"

    def test_nested_archive_is_extracted_once_more(self, tmp_path):
        """A .tgz lists only its inner .tar; the ROM inside the tar must be
        reached through a second extraction pass."""
        listings = [
            MagicMock(stdout=_fake_7z_listing_sized([("game.tar", 600)])),
            MagicMock(stdout=_fake_7z_listing_sized([("game.gba", 500)])),
        ]
        popen = _mock_popen_streaming([[b"tarbytes"], [b"rombytes"]], [0, 0])

        with (
            patch.object(archives.subprocess, "run", side_effect=listings),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.tgz"), tmp_path
            )

        assert result is not None
        assert result == tmp_path / "game.gba"
        assert result.read_bytes() == b"rombytes"
        # The intermediate tar must not be left behind.
        assert not (tmp_path / "game.tar").exists()

    def test_gives_up_on_doubly_nested_archives(self, tmp_path):
        """Two levels of nesting is the limit; deeper nesting returns None
        and leaves no partial files behind."""
        listings = [
            MagicMock(stdout=_fake_7z_listing_sized([("inner.tar", 600)])),
            MagicMock(stdout=_fake_7z_listing_sized([("innermost.7z", 500)])),
        ]
        popen = _mock_popen_streaming([[b"tarbytes"], [b"7zbytes"]], [0, 0])

        with (
            patch.object(archives.subprocess, "run", side_effect=listings),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.tgz"), tmp_path
            )

        assert result is None
        assert list(tmp_path.iterdir()) == []

    def test_returns_none_when_listing_fails(self, tmp_path):
        with patch.object(
            archives.subprocess,
            "run",
            side_effect=archives.subprocess.CalledProcessError(2, "7zz"),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result is None

    def test_returns_none_when_archive_has_no_members(self, tmp_path):
        listing = MagicMock(stdout="")

        with patch.object(archives.subprocess, "run", return_value=listing):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result is None

    def test_returns_none_and_cleans_up_on_extract_failure(self, tmp_path):
        """A codec the extractor can't decompress streams nothing and exits
        non-zero; no partial file may be left behind, and the reason must reach
        the error log so scans explain the missing hash."""
        listing = MagicMock(stdout=_fake_7z_listing_sized([("game.gba", 500)]))
        popen = _mock_popen_streaming(
            [[]], [2], stderr=b"ERROR: Unsupported Method : game.gba"
        )

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
            patch.object(archives.log, "error") as log_error,
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result is None
        assert list(tmp_path.iterdir()) == []
        assert "Unsupported Method" in log_error.call_args[0][0]

    def test_returns_none_and_cleans_up_on_timeout(self, tmp_path, monkeypatch):
        monkeypatch.setattr(archives, "SEVEN_ZIP_TIMEOUT", -1)
        listing = MagicMock(stdout=_fake_7z_listing_sized([("game.gba", 500)]))
        popen = _mock_popen_streaming([[b"abc", b"def"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.7z"), tmp_path
            )

        assert result is None
        assert list(tmp_path.iterdir()) == []


class TestRarArchives:
    """RAR reading through bsdtar/libarchive: the bundled 7zz is built without
    the RAR codec, so it can neither list nor extract RAR members (GitHub issue
    #3884)."""

    def test_lists_file_members_with_sizes(self):
        listing = MagicMock(
            stdout=_fake_mtree_listing(
                [
                    "./game.gba type=file size=500",
                    "./readme.txt type=file size=12",
                ]
            )
        )

        with patch.object(archives.subprocess, "run", return_value=listing) as run:
            members = archives._list_rar_file_members(Path("/fake/game.rar"))

        # The archive-root "./" prefix is not part of the stored member name.
        assert members == [("game.gba", 500), ("readme.txt", 12)]
        assert run.call_args[0][0][0] == archives.BSDTAR_PATH
        assert "@/fake/game.rar" in run.call_args[0][0]

    def test_directories_and_links_are_ignored(self):
        listing = MagicMock(
            stdout=_fake_mtree_listing(
                [
                    "./subdir type=dir",
                    "./subdir/link type=link",
                    "./subdir/game.gba type=file size=500",
                ]
            )
        )

        with patch.object(archives.subprocess, "run", return_value=listing):
            members = archives._list_rar_file_members(Path("/fake/game.rar"))

        assert members == [("subdir/game.gba", 500)]

    def test_escaped_member_names_are_decoded(self):
        """libarchive octal-escapes the backslash and every byte outside
        printable ASCII, so a UTF-8 name comes back byte by byte."""
        listing = MagicMock(
            stdout=_fake_mtree_listing(
                [r"./caf\303\251\040\0431\134x.gba type=file size=500"]
            )
        )

        with patch.object(archives.subprocess, "run", return_value=listing):
            members = archives._list_rar_file_members(Path("/fake/game.rar"))

        assert members == [("café #1\\x.gba", 500)]

    def test_returns_no_members_when_listing_fails(self):
        """Encrypted headers and corrupt archives make bsdtar exit non-zero."""
        with (
            patch.object(
                archives.subprocess,
                "run",
                side_effect=archives.subprocess.CalledProcessError(1, "bsdtar"),
            ),
            patch.object(archives.log, "error") as log_error,
        ):
            members = archives._list_rar_file_members(Path("/fake/game.rar"))

        assert members == []
        log_error.assert_called_once()

    def test_member_pattern_escapes_glob_metacharacters(self):
        """bsdtar matches member arguments as globs, so a stored name holding
        "*" or "?" would otherwise select (and concatenate) other members."""
        assert archives._bsdtar_member_pattern("g*me?[1].gba") == r"g\*me\?\[1\].gba"
        assert archives._bsdtar_member_pattern("back\\slash.gba") == r"back\\slash.gba"

    def test_extraction_command_is_chosen_by_extension(self):
        rar_command = archives._archive_member_command(Path("/fake/GAME.RAR"), "a.gba")
        assert rar_command == [archives.BSDTAR_PATH, "-xOf", "/fake/GAME.RAR", "a.gba"]

        seven_zip_command = archives._archive_member_command(
            Path("/fake/game.7z"), "a.gba"
        )
        assert seven_zip_command[0] == archives.SEVEN_ZIP_PATH

    def test_read_rar_archive_files_streams_members_in_ascii_order(self):
        listing = MagicMock(
            stdout=_fake_mtree_listing(
                [
                    "./b.gba type=file size=3",
                    "./a.gba type=file size=3",
                    "./skip.nfo type=file size=3",
                    "./cover.jpg type=file size=3",
                ]
            )
        )
        popen = _mock_popen_streaming([[b"aaa"], [b"bbb"]], [0, 0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            results = [
                (name, size, b"".join(chunks))
                for name, size, chunks in archives.read_rar_archive_files(
                    Path("/fake/game.rar"), ["cover.jpg"], ["nfo"]
                )
            ]

        assert results == [("a.gba", 3, b"aaa"), ("b.gba", 3, b"bbb")]
        assert popen.call_args_list[0][0][0][:3] == [
            archives.BSDTAR_PATH,
            "-xOf",
            "/fake/game.rar",
        ]

    def test_largest_member_is_extracted_through_bsdtar(self, tmp_path):
        """RAHasher is fed a real ROM extracted from the RAR (GitHub issue
        #3808 left this broken for RAR only)."""
        listing = MagicMock(
            stdout=_fake_mtree_listing(
                [
                    "./readme.txt type=file size=12",
                    "./game.gba type=file size=500",
                ]
            )
        )
        popen = _mock_popen_streaming([[b"abc", b"def"]], [0])

        with (
            patch.object(archives.subprocess, "run", return_value=listing),
            patch.object(archives.subprocess, "Popen", popen),
        ):
            result = archives.extract_largest_archive_member(
                Path("/fake/game.rar"), tmp_path
            )

        assert result is not None
        assert result == tmp_path / "game.gba"
        assert result.read_bytes() == b"abcdef"
        assert popen.call_args[0][0] == [
            archives.BSDTAR_PATH,
            "-xOf",
            "/fake/game.rar",
            "game.gba",
        ]
