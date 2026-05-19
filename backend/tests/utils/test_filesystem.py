"""Tests for utils.filesystem helpers."""

import errno
import os
from unittest.mock import patch

import pytest

from utils.filesystem import link_or_copy_file


class TestLinkOrCopyFile:
    """Test the hardlink-with-copy-fallback helper used by importers and exporters."""

    def test_same_filesystem_creates_hardlink(self, tmp_path):
        """When source and dest are on the same filesystem, the helper creates a
        hardlink — source and dest share an inode and st_nlink reflects both."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        link_or_copy_file(source, dest)

        assert dest.read_bytes() == b"payload"
        # Hardlink: shared inode, link count >= 2
        assert source.stat().st_ino == dest.stat().st_ino
        assert source.stat().st_nlink >= 2

    def test_falls_back_to_copy_on_exdev(self, tmp_path):
        """When os.link raises EXDEV (cross-device), the helper falls back to
        shutil.copy2 — content matches but inodes differ."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        exdev = OSError(errno.EXDEV, "Cross-device link")

        with patch("utils.filesystem.os.link", side_effect=exdev):
            link_or_copy_file(source, dest)

        assert dest.read_bytes() == b"payload"
        # Real copy: separate inodes
        assert source.stat().st_ino != dest.stat().st_ino

    def test_falls_back_to_copy_on_eperm(self, tmp_path):
        """EPERM (filesystem doesn't permit hardlinks, e.g. FAT32) must also
        trigger the copy fallback."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        eperm = OSError(errno.EPERM, "Operation not permitted")

        with patch("utils.filesystem.os.link", side_effect=eperm):
            link_or_copy_file(source, dest)

        assert dest.read_bytes() == b"payload"
        assert source.stat().st_ino != dest.stat().st_ino

    def test_reraises_non_fallback_oserror(self, tmp_path):
        """An OSError that isn't in the fallback set (e.g. ENOSPC — disk full)
        must propagate; we don't want to mask real disk errors."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        enospc = OSError(errno.ENOSPC, "No space left on device")

        with patch("utils.filesystem.os.link", side_effect=enospc):
            with pytest.raises(OSError) as excinfo:
                link_or_copy_file(source, dest)

        assert excinfo.value.errno == errno.ENOSPC
        assert not dest.exists()

    def test_mutation_after_link_affects_source(self, tmp_path):
        """Document hardlink semantics: writing through the dest path with
        O_TRUNC truncates the shared inode and therefore mutates the source.
        This is why callers that mutate dest in place (e.g. PIL resize) must
        not opt into hardlinking — copy_file defaults to allow_link=False to
        keep this hazard from being the easy path."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"original")
        dest = tmp_path / "dest.bin"

        link_or_copy_file(source, dest)

        # Truncating-write through dest affects source (same inode).
        with open(dest, "wb") as f:
            f.write(b"mutated")

        assert source.read_bytes() == b"mutated"

    def test_mutation_after_copy_does_not_affect_source(self, tmp_path):
        """When the helper falls back to copy, the inodes are independent —
        mutation through dest leaves the source untouched."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"original")
        dest = tmp_path / "dest.bin"

        with patch(
            "utils.filesystem.os.link",
            side_effect=OSError(errno.EXDEV, "Cross-device link"),
        ):
            link_or_copy_file(source, dest)

        with open(dest, "wb") as f:
            f.write(b"mutated")

        assert source.read_bytes() == b"original"

    def test_dest_already_exists_is_overwritten(self, tmp_path):
        """When dest already exists, link_or_copy_file atomically replaces it.
        This mirrors shutil.copy2's overwrite-on-exists semantics so callers
        re-fetching a resource don't have to pre-unlink to avoid EEXIST."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"new payload")
        dest = tmp_path / "dest.bin"
        dest.write_bytes(b"old payload")

        link_or_copy_file(source, dest)

        assert dest.read_bytes() == b"new payload"
        # Same-fs: dest is now a hardlink to source.
        assert source.stat().st_ino == dest.stat().st_ino

    def test_dest_already_exists_is_overwritten_on_copy_fallback(self, tmp_path):
        """Overwrite semantics also hold when the link fails and we fall back
        to copy — replace happens after the tempfile is populated either way."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"new payload")
        dest = tmp_path / "dest.bin"
        dest.write_bytes(b"old payload")

        with patch(
            "utils.filesystem.os.link",
            side_effect=OSError(errno.EXDEV, "Cross-device link"),
        ):
            link_or_copy_file(source, dest)

        assert dest.read_bytes() == b"new payload"
        # Fell back to copy: separate inodes.
        assert source.stat().st_ino != dest.stat().st_ino

    def test_tempfile_cleaned_up_on_failure(self, tmp_path):
        """If linking and the copy fallback both fail (e.g. ENOSPC), the helper
        must not leave a stray tempfile behind in dest's directory."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        enospc = OSError(errno.ENOSPC, "No space left on device")

        with patch("utils.filesystem.os.link", side_effect=enospc):
            with pytest.raises(OSError) as excinfo:
                link_or_copy_file(source, dest)

        assert excinfo.value.errno == errno.ENOSPC
        assert not dest.exists()
        # No leftover .romm_link_tmp_* file in the directory.
        leftovers = [
            p for p in tmp_path.iterdir() if p.name.startswith(".romm_link_tmp_")
        ]
        assert leftovers == []

    def test_helper_uses_os_link_first(self, tmp_path):
        """Sanity-check that the helper calls os.link before any copy logic —
        guards against a future refactor regressing to copy-only. The second
        arg is a tempfile in dest's parent (not dest itself), since we
        link-then-replace for atomic overwrite."""
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload")
        dest = tmp_path / "dest.bin"

        with patch("utils.filesystem.os.link", wraps=os.link) as link_spy:
            link_or_copy_file(source, dest)

        link_spy.assert_called_once()
        args = link_spy.call_args.args
        assert args[0] == source
        assert args[1].parent == dest.parent
        assert args[1].name.startswith(".romm_link_tmp_")
