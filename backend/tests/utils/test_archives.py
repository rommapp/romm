import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils import archives


def _fake_7z_listing(names: list[str]) -> str:
    """Build a `7zz l -slt -ba` style listing for the given member names."""
    return "\n".join(f"Path = {name}\nSize = 10\nAttributes = A\n" for name in names)


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
