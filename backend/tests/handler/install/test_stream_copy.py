from unittest.mock import Mock

from handler.filesystem.installer_detection import DetectedFile
from handler.install.stream_copy import _rom_copy_pairs


class TestRomCopyPairs:
    def test_single_file_rom(self, tmp_path):
        rom_file = tmp_path / "game.zip"
        rom_file.write_bytes(b"x")
        rom = Mock(fs_name="game.zip")
        work_dir = tmp_path / "work"

        pairs = _rom_copy_pairs(rom, rom_file, work_dir)

        assert pairs == [(rom_file, work_dir / "game.zip")]

    def test_directory_rom_mirrors_relative_paths(self, tmp_path, monkeypatch):
        import handler.install.stream_copy as stream_copy_mod

        rom_root = tmp_path / "game"
        rom_root.mkdir()
        work_dir = tmp_path / "work"
        rom = Mock()

        files = [
            DetectedFile(path="disc1.bin", size_bytes=10),
            DetectedFile(path="sub/disc2.bin", size_bytes=20),
        ]
        monkeypatch.setattr(
            stream_copy_mod.fs_rom_handler,
            "list_rom_files_flat",
            lambda r: files,
        )

        pairs = _rom_copy_pairs(rom, rom_root, work_dir)

        assert pairs == [
            (rom_root / "disc1.bin", work_dir / "disc1.bin"),
            (rom_root / "sub" / "disc2.bin", work_dir / "sub" / "disc2.bin"),
        ]
