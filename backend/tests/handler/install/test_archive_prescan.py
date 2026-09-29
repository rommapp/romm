from pathlib import Path

from handler.install import archive_prescan


class TestIsArchiveCandidate:
    def test_zip_is_an_archive_candidate(self):
        assert archive_prescan.is_archive_candidate(Path("GameSetup.zip")) is True

    def test_iso_is_an_archive_candidate(self):
        assert archive_prescan.is_archive_candidate(Path("game.iso")) is True

    def test_exe_is_not_an_archive_candidate(self):
        assert archive_prescan.is_archive_candidate(Path("setup.exe")) is False


class TestExtractAndRescan:
    def test_finds_and_returns_the_top_installer_candidate(self, tmp_path, monkeypatch):
        archive_path = tmp_path / "GameSetup.zip"
        archive_path.touch()

        def fake_extract(file_path, dest_dir):
            (dest_dir / "readme.txt").write_bytes(b"hi")
            (dest_dir / "setup.exe").write_bytes(b"x" * 10)
            return True

        monkeypatch.setattr(archive_prescan, "extract_archive_tree", fake_extract)

        result = archive_prescan.extract_and_rescan(archive_path)
        assert result is not None
        temp_dir, extract_root, top = result
        try:
            assert top.path == "setup.exe"
            assert (extract_root / top.path).read_bytes() == b"x" * 10
        finally:
            temp_dir.cleanup()
        assert not extract_root.exists()

    def test_extraction_failure_returns_none_and_cleans_up(self, tmp_path, monkeypatch):
        archive_path = tmp_path / "broken.zip"
        archive_path.touch()

        captured_dest = {}

        def fake_extract(file_path, dest_dir):
            captured_dest["dir"] = dest_dir
            return False

        monkeypatch.setattr(archive_prescan, "extract_archive_tree", fake_extract)

        result = archive_prescan.extract_and_rescan(archive_path)
        assert result is None
        assert not captured_dest["dir"].exists()

    def test_nothing_installer_like_inside_returns_none_and_cleans_up(
        self, tmp_path, monkeypatch
    ):
        archive_path = tmp_path / "just-docs.zip"
        archive_path.touch()

        def fake_extract(file_path, dest_dir):
            (dest_dir / "readme.txt").write_bytes(b"hi")
            return True

        monkeypatch.setattr(archive_prescan, "extract_archive_tree", fake_extract)

        result = archive_prescan.extract_and_rescan(archive_path)
        assert result is None


class TestExplicitInstallerInsideArchive:
    def test_the_named_installer_is_used_instead_of_the_top_one(
        self, tmp_path, monkeypatch
    ):
        archive_path = tmp_path / "GameSetup.zip"
        archive_path.touch()

        def fake_extract(file_path, dest_dir):
            (dest_dir / "setup.exe").write_bytes(b"x" * 10)
            (dest_dir / "tools").mkdir()
            (dest_dir / "tools" / "patch.exe").write_bytes(b"y")
            return True

        monkeypatch.setattr(archive_prescan, "extract_archive_tree", fake_extract)

        result = archive_prescan.extract_and_rescan(archive_path, "tools/patch.exe")
        assert result is not None
        temp_dir, _root, chosen = result
        temp_dir.cleanup()
        assert chosen.path == "tools/patch.exe"

    def test_unknown_installer_returns_none(self, tmp_path, monkeypatch):
        archive_path = tmp_path / "GameSetup.zip"
        archive_path.touch()

        def fake_extract(file_path, dest_dir):
            (dest_dir / "setup.exe").write_bytes(b"x")
            return True

        monkeypatch.setattr(archive_prescan, "extract_archive_tree", fake_extract)
        assert archive_prescan.extract_and_rescan(archive_path, "nope.exe") is None


class TestListSourceCandidates:
    def test_lists_only_executables_from_the_member_listing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            archive_prescan,
            "list_archive_members",
            lambda _p: [
                ("setup.exe", 10),
                ("docs/readme.txt", 1),
                ("nested.zip", 5),
                ("bin/game.exe", 20),
            ],
        )
        result = archive_prescan.list_source_candidates(tmp_path / "x.zip")
        assert [c.path for c in result] == ["setup.exe", "bin/game.exe"]


class TestSourcePhase:
    def test_disc_images_are_mounted(self):
        assert archive_prescan.source_phase(Path("cdrom.chd")).value == "mounting"

    def test_archives_are_extracted(self):
        assert archive_prescan.source_phase(Path("MyGame.zip")).value == "extracting"


class TestNestedArchives:
    def _fake_extract(self, tree):
        def fake(file_path, dest_dir):
            for rel, data in tree.get(file_path.name, {}).items():
                target = dest_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            return True

        return fake

    def test_a_nested_archive_is_unpacked_and_its_installer_picked(
        self, tmp_path, monkeypatch
    ):
        src = tmp_path / "Collection.zip"
        src.touch()
        monkeypatch.setattr(
            archive_prescan,
            "extract_archive_tree",
            self._fake_extract(
                {
                    "Collection.zip": {"1 - Game.zip": b"z", "readme.txt": b"t"},
                    "1 - Game.zip": {"Game/setup.exe": b"x"},
                }
            ),
        )
        result = archive_prescan.extract_and_rescan(src)
        assert result is not None
        temp_dir, root, chosen = result
        try:
            assert chosen.path == "1 - Game.zip.extracted/Game/setup.exe"
            assert (root / chosen.path).is_file()
        finally:
            temp_dir.cleanup()

    def test_nested_archive_without_an_installer_fails(self, tmp_path, monkeypatch):
        src = tmp_path / "Collection.zip"
        src.touch()
        monkeypatch.setattr(
            archive_prescan,
            "extract_archive_tree",
            self._fake_extract(
                {"Collection.zip": {"1.zip": b"z"}, "1.zip": {"notes.txt": b"t"}}
            ),
        )
        assert archive_prescan.extract_and_rescan(src) is None

    def test_listing_offers_nested_archives_when_nothing_is_runnable(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            archive_prescan,
            "list_archive_members",
            lambda _p: [("1.zip", 5), ("readme.txt", 1)],
        )
        result = archive_prescan.list_source_candidates(tmp_path / "x.zip")
        assert [c.path for c in result] == ["1.zip"]
