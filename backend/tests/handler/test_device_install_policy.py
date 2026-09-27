import pytest

from handler import device_install_policy as policy_module
from handler.device_install_policy import (
    InstallNotAllowedError,
    is_installable_platform,
    select_install_files,
)
from models.rom import RomFile, RomFileCategory


def _file(file_id: int, category: RomFileCategory | None, missing: bool = False):
    return RomFile(
        id=file_id,
        file_name=f"f{file_id}",
        file_path="p",
        category=category,
        missing_from_fs=missing,
    )


FILES = [
    _file(4, RomFileCategory.DLC),
    _file(1, None),
    _file(2, RomFileCategory.GAME),
    _file(3, RomFileCategory.UPDATE),
    _file(5, RomFileCategory.PATCH),
    _file(6, RomFileCategory.SOUNDTRACK),
    _file(7, RomFileCategory.SCREENSHOT),
    _file(8, RomFileCategory.CHEAT),
    _file(9, RomFileCategory.MANUAL),
    _file(10, RomFileCategory.WALKTHROUGH),
    _file(11, RomFileCategory.GAME, missing=True),
]


class TestFileSelection:
    def test_takes_the_game_update_and_dlc_files_on_disk_in_order(self):
        assert select_install_files(FILES) == [1, 2, 3, 4]

    def test_rejects_a_rom_with_nothing_installable(self):
        with pytest.raises(InstallNotAllowedError):
            select_install_files(
                [
                    _file(6, RomFileCategory.SOUNDTRACK),
                    _file(11, RomFileCategory.GAME, missing=True),
                ]
            )


class TestPlatformExclusion:
    @pytest.mark.parametrize("slug", ["win", "win3x", "win9x", "windows-apps", "WIN"])
    def test_windows_platforms_are_excluded_by_default(self, slug):
        assert not is_installable_platform(slug)

    def test_other_platforms_are_installable(self):
        assert is_installable_platform("n64")

    def test_the_configured_slugs_decide(self, monkeypatch):
        monkeypatch.setattr(
            policy_module, "DEVICE_INSTALL_EXCLUDED_PLATFORM_SLUGS", frozenset({"n64"})
        )

        assert not is_installable_platform("n64")
        assert is_installable_platform("win")
