"""Which roms, and which of their files, a user may push to a device."""

from collections.abc import Sequence
from typing import Final

from config import DEVICE_INSTALL_EXCLUDED_PLATFORM_SLUGS
from models.rom import RomFile, RomFileCategory

# None is an uncategorized root file. Documents reach a device through its own
# manual/walkthrough download.
INSTALLABLE_FILE_CATEGORIES: Final = frozenset(
    {None, RomFileCategory.GAME, RomFileCategory.UPDATE, RomFileCategory.DLC}
)
REMOTE_INSTALL_CAPABILITY: Final = "remote_install"


class InstallNotAllowedError(Exception):
    """The rom has nothing that can be pushed to a device."""


def is_installable_platform(platform_slug: str) -> bool:
    return platform_slug.lower() not in DEVICE_INSTALL_EXCLUDED_PLATFORM_SLUGS


def accepts_remote_install(capabilities: dict[str, bool] | None) -> bool:
    return (capabilities or {}).get(REMOTE_INSTALL_CAPABILITY) is True


def select_install_files(files: Sequence[RomFile]) -> list[int]:
    """The ids of the rom's game, update and DLC files on disk, ascending.

    Raises:
        InstallNotAllowedError: None of the rom's files qualify.
    """
    selected = sorted(
        f.id
        for f in files
        if f.category in INSTALLABLE_FILE_CATEGORIES and not f.missing_from_fs
    )
    if not selected:
        raise InstallNotAllowedError("This rom has no installable files")
    return selected
