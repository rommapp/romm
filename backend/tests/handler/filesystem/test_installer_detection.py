from handler.filesystem.installer_detection import (
    ARCHIVE_SOURCE_KINDS,
    RANK_ARCHIVE,
    RANK_DISC_IMAGE,
    RANK_KNOWN_INSTALLER,
    RANK_LINUX_INSTALLER,
    RANK_NESTED_EXECUTABLE,
    RANK_TOP_LEVEL_EXECUTABLE,
    DetectedFile,
    detect_installer_candidates,
    pick_default_installer,
)


def _paths(candidates):
    return [c.path for c in candidates]


class TestDetectInstallerCandidates:
    def test_empty_listing_yields_no_candidates(self):
        assert detect_installer_candidates([]) == []

    def test_ignores_non_installer_files(self):
        files = [
            DetectedFile("readme.txt", 10),
            DetectedFile("image.png", 20),
            DetectedFile("data/config.ini", 5),
        ]
        assert detect_installer_candidates(files) == []

    def test_known_installer_names_rank_highest(self):
        files = [
            DetectedFile("gog-12345.exe", 100),
            DetectedFile("setup.exe", 100),
            DetectedFile("install.exe", 100),
            DetectedFile("setup_english.exe", 100),
        ]
        result = detect_installer_candidates(files)
        assert all(c.rank == RANK_KNOWN_INSTALLER for c in result)
        assert len(result) == 4

    def test_top_level_executable_ranks_above_nested(self):
        files = [
            DetectedFile("game.exe", 100),
            DetectedFile("bin/game.exe", 100),
        ]
        result = detect_installer_candidates(files)
        assert result[0].path == "game.exe"
        assert result[0].rank == RANK_TOP_LEVEL_EXECUTABLE
        assert result[1].path == "bin/game.exe"
        assert result[1].rank == RANK_NESTED_EXECUTABLE

    def test_msi_and_bat_are_executables(self):
        files = [
            DetectedFile("thing.msi", 1),
            DetectedFile("run.bat", 1),
        ]
        result = detect_installer_candidates(files)
        assert {c.path for c in result} == {"thing.msi", "run.bat"}

    def test_disc_images_detected(self):
        files = [DetectedFile("disc.iso", 1), DetectedFile("game.chd", 1)]
        result = detect_installer_candidates(files)
        assert all(c.rank == RANK_DISC_IMAGE for c in result)

    def test_archives_detected(self):
        files = [DetectedFile("pack.zip", 1), DetectedFile("data.tar.gz", 1)]
        result = detect_installer_candidates(files)
        assert all(c.rank == RANK_ARCHIVE for c in result)

    def test_linux_installers_detected(self):
        files = [DetectedFile("start.sh", 1), DetectedFile("app.AppImage", 1)]
        result = detect_installer_candidates(files)
        assert all(c.rank == RANK_LINUX_INSTALLER for c in result)

    def test_full_priority_ordering(self):
        files = [
            DetectedFile("run.sh", 1),
            DetectedFile("pack.zip", 1),
            DetectedFile("disc.iso", 1),
            DetectedFile("nested/other.exe", 1),
            DetectedFile("setup.exe", 1),
        ]
        result = detect_installer_candidates(files)
        assert _paths(result) == [
            "setup.exe",
            "nested/other.exe",
            "disc.iso",
            "pack.zip",
            "run.sh",
        ]

    def test_within_bucket_larger_files_first(self):
        files = [
            DetectedFile("a/small.exe", 10),
            DetectedFile("b/big.exe", 9000),
        ]
        result = detect_installer_candidates(files)
        assert _paths(result) == ["b/big.exe", "a/small.exe"]

    def test_case_insensitive_extensions_and_names(self):
        files = [
            DetectedFile("SETUP.EXE", 1),
            DetectedFile("Disc.ISO", 1),
        ]
        result = detect_installer_candidates(files)
        ranks = {c.path: c.rank for c in result}
        assert ranks["SETUP.EXE"] == RANK_KNOWN_INSTALLER
        assert ranks["Disc.ISO"] == RANK_DISC_IMAGE


class TestPickDefaultInstaller:
    def test_no_candidates_returns_none(self):
        assert pick_default_installer([]) is None

    def test_top_ranked_known_installer_is_picked(self):
        candidates = detect_installer_candidates(
            [DetectedFile("setup.exe", 100), DetectedFile("readme.txt", 1)]
        )
        picked = pick_default_installer(candidates)
        assert picked is not None
        assert picked.path == "setup.exe"

    def test_plain_executable_is_picked_too(self):
        candidates = detect_installer_candidates([DetectedFile("Game Title.exe", 100)])
        picked = pick_default_installer(candidates)
        assert picked is not None
        assert picked.path == "Game Title.exe"

    def test_archive_or_disc_image_is_picked_when_nothing_runs_directly(self):
        candidates = detect_installer_candidates(
            [DetectedFile("game.zip", 100), DetectedFile("disc.iso", 50)]
        )
        picked = pick_default_installer(candidates)
        assert picked is not None
        assert picked.path == "disc.iso"
        assert picked.kind in ARCHIVE_SOURCE_KINDS

    def test_ties_break_biggest_first(self):
        candidates = detect_installer_candidates(
            [
                DetectedFile("setup_v1.exe", 100),
                DetectedFile("setup_v2.exe", 200),
                DetectedFile("gog-installer.exe", 50),
            ]
        )
        picked = pick_default_installer(candidates)
        assert picked is not None
        assert picked.path == "setup_v2.exe"
