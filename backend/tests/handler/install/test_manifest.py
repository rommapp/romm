from handler.install.manifest import (
    LIVE_MANIFEST_FILENAME,
    MANIFEST_FILENAME,
    ManifestEntry,
    build_manifest,
    delete_live_manifest,
    find_manifest_entry,
    hash_file_sha1,
    hash_files,
    live_view_of_final_manifest,
    manifest_total_bytes,
    read_live_manifest,
    read_manifest,
    scan_live_manifest,
    write_live_manifest,
    write_manifest,
)


class TestHashFileSha1:
    def test_matches_known_sha1(self, tmp_path):
        path = tmp_path / "a.bin"
        path.write_bytes(b"hello world")
        # sha1("hello world")
        assert hash_file_sha1(path) == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"

    def test_large_file_hashes_in_chunks(self, tmp_path, monkeypatch):
        import handler.install.manifest as manifest_mod

        monkeypatch.setattr(manifest_mod, "CHUNK_SIZE", 4)
        path = tmp_path / "b.bin"
        path.write_bytes(b"x" * 100)
        # Should match whether read in one go or in 4-byte chunks.
        assert hash_file_sha1(path) == hash_file_sha1(path)


class TestHashFiles:
    def test_paths_relative_to_root(self, tmp_path):
        (tmp_path / "sub").mkdir()
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "sub" / "b.txt"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bb")

        entries = hash_files([f1, f2], root=tmp_path)
        by_path = {e.path: e for e in entries}
        assert by_path["a.txt"].size_bytes == 3
        assert by_path["sub/b.txt"].size_bytes == 2

    def test_reports_cumulative_progress(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"12345")
        f2.write_bytes(b"123")

        seen = []
        hash_files([f1, f2], root=tmp_path, on_progress=seen.append)
        assert seen == [5, 8]

    def test_skips_missing_file(self, tmp_path):
        missing = tmp_path / "gone.txt"
        entries = hash_files([missing], root=tmp_path)
        assert entries == []


class TestBuildManifest:
    def test_walks_directory_excluding_manifest_file(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"x")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_bytes(b"yy")
        (tmp_path / MANIFEST_FILENAME).write_text("{}")

        entries = build_manifest(tmp_path)
        paths = {e.path for e in entries}
        assert paths == {"a.txt", "sub/b.txt"}


class TestManifestRoundTrip:
    def test_write_then_read(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"content")
        entries = build_manifest(tmp_path)
        write_manifest(tmp_path, entries)

        read_back = read_manifest(tmp_path)
        assert read_back == entries

    def test_read_missing_manifest_returns_none(self, tmp_path):
        assert read_manifest(tmp_path) is None

    def test_total_bytes(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"12345")
        (tmp_path / "b.txt").write_bytes(b"123")
        entries = build_manifest(tmp_path)
        assert manifest_total_bytes(entries) == 8


class TestFindManifestEntry:
    def test_exact_match(self, tmp_path):
        (tmp_path / "game.exe").write_bytes(b"x")
        entries = build_manifest(tmp_path)
        found = find_manifest_entry(entries, "game.exe")
        assert found is not None
        assert found.path == "game.exe"

    def test_no_match_for_unlisted_path(self, tmp_path):
        (tmp_path / "game.exe").write_bytes(b"x")
        entries = build_manifest(tmp_path)
        assert find_manifest_entry(entries, "../../etc/passwd") is None
        assert find_manifest_entry(entries, "other.exe") is None


class TestScanLiveManifest:
    def test_first_scan_never_seals_anything(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"x" * 10)

        state = scan_live_manifest(tmp_path, [f])
        entry = state["a.bin"]
        assert entry.size_bytes == 10
        assert entry.sealed_bytes == 0
        assert entry.complete is False

    def test_seals_the_whole_file_once_size_is_confirmed_stable(self, tmp_path):
        # Not gated by any chunk-size boundary - a file (or a file's
        # trailing remainder) smaller than one CHUNK_SIZE must still fully
        # seal once it's stopped growing, not stay unstreamable forever
        # (the exact bug this replaced the old chunk-based version to fix).
        f = tmp_path / "a.bin"
        f.write_bytes(b"x" * 10)

        state = scan_live_manifest(tmp_path, [f])  # first sight: seals nothing
        state = scan_live_manifest(tmp_path, [f], state)  # unchanged: fully sealed

        entry = state["a.bin"]
        assert entry.sealed_bytes == 10

    def test_growth_needs_its_own_fresh_confirmation(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"x" * 10)
        state = scan_live_manifest(tmp_path, [f])
        state = scan_live_manifest(tmp_path, [f], state)
        assert state["a.bin"].sealed_bytes == 10

        f.write_bytes(b"x" * 20)  # grows further, mid-write
        state = scan_live_manifest(tmp_path, [f], state)
        # The newly-written bytes aren't trusted on the same scan they
        # appeared in; what was already sealed carries over unchanged.
        assert state["a.bin"].sealed_bytes == 10

        # Unchanged since the last scan again - the new size is now stable
        # too, so it seals in full.
        state = scan_live_manifest(tmp_path, [f], state)
        assert state["a.bin"].sealed_bytes == 20

    def test_sealed_bytes_never_regresses(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"x" * 10)
        state = scan_live_manifest(tmp_path, [f])
        state = scan_live_manifest(tmp_path, [f], state)
        assert state["a.bin"].sealed_bytes == 10

        # A shrink shouldn't happen in practice, but sealed_bytes must not
        # go backwards even if one somehow did.
        f.write_bytes(b"x" * 3)
        state = scan_live_manifest(tmp_path, [f], state)
        assert state["a.bin"].sealed_bytes == 10

    def test_missing_file_is_skipped(self, tmp_path):
        missing = tmp_path / "gone.bin"
        state = scan_live_manifest(tmp_path, [missing])
        assert state == {}


class TestLiveViewOfFinalManifest:
    def test_marks_every_entry_complete(self):
        entries = [ManifestEntry(path="a.exe", size_bytes=5, sha1="deadbeef")]
        live = live_view_of_final_manifest(entries)
        assert live["a.exe"].complete is True
        assert live["a.exe"].sealed_bytes == 5


class TestLiveManifestRoundTrip:
    def test_write_then_read(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"abcdefgh")
        state = scan_live_manifest(tmp_path, [f])
        state = scan_live_manifest(tmp_path, [f], state)

        write_live_manifest(tmp_path, state)
        read_back = read_live_manifest(tmp_path)
        assert read_back == state

    def test_read_missing_returns_none(self, tmp_path):
        assert read_live_manifest(tmp_path) is None

    def test_read_survives_a_corrupt_file(self, tmp_path):
        (tmp_path / LIVE_MANIFEST_FILENAME).write_text("not json")
        assert read_live_manifest(tmp_path) is None

    def test_delete_removes_the_file_and_its_tmp_sibling(self, tmp_path):
        (tmp_path / LIVE_MANIFEST_FILENAME).write_text("{}")
        (tmp_path / f"{LIVE_MANIFEST_FILENAME}.tmp").write_text("{}")
        delete_live_manifest(tmp_path)
        assert not (tmp_path / LIVE_MANIFEST_FILENAME).exists()
        assert not (tmp_path / f"{LIVE_MANIFEST_FILENAME}.tmp").exists()

    def test_delete_is_a_noop_when_nothing_is_there(self, tmp_path):
        delete_live_manifest(tmp_path)  # must not raise
