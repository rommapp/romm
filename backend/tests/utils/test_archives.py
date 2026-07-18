import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _mock_popen_streaming(
    chunk_streams: list[list[bytes]],
    returncodes: list[int],
    stderr: bytes = b"",
):
    """Build a subprocess.Popen mock whose consecutive context-managed calls
    stream the given chunk lists and finish with the given return codes."""
    popen = MagicMock()
    processes = []
    for chunks, returncode in zip(chunk_streams, returncodes, strict=True):
        process = MagicMock()
        process.stdout.read.side_effect = [*chunks, b""]
        process.stderr.read.return_value = stderr
        process.returncode = returncode
        processes.append(process)
    popen.return_value.__enter__.side_effect = processes
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


def test_read_7z_archive_files_timeout_logs_once_without_spam(monkeypatch):
    """Once the shared budget is spent, no subprocess is spawned per remaining
    member and the timeout is logged a single time, not once per entry."""
    names = [f"file{i:02d}.bin" for i in range(20)]
    listing = MagicMock(stdout=_fake_7z_listing(names))

    # Force the per-archive deadline to be already in the past.
    monkeypatch.setattr(archives, "SEVEN_ZIP_TIMEOUT", -1)

    with (
        patch.object(archives.subprocess, "run", return_value=listing),
        patch.object(archives.subprocess, "Popen") as popen_patch,
        patch.object(archives.log, "error") as log_error,
    ):
        results = list(archives.read_7z_archive_files(Path("/fake.7z"), [], []))

    assert results == []
    popen_patch.assert_not_called()
    assert log_error.call_count == 1


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
        # The largest member, not the first, must be requested from 7zz.
        extract_args = popen.call_args[0][0]
        assert "game.gba" in extract_args

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
        """A codec the 7zz build can't decompress (e.g. RAR) streams nothing
        and exits non-zero; no partial file may be left behind, and the 7zz
        reason must reach the error log so scans explain the missing hash."""
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
                Path("/fake/game.rar"), tmp_path
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
