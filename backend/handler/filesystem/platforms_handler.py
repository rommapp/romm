import fnmatch
import os

from anyio import Path as AnyioPath

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    PlatformAlreadyExistsException,
)

from .base_handler import FSHandler, LibraryStructure


class FSPlatformsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LIBRARY_BASE_PATH)

    def _exclude_platforms(self, platforms: list):
        cnfg = cm.get_config()
        return [
            platform
            for platform in platforms
            if not any(
                platform == excluded or fnmatch.fnmatch(platform, excluded)
                for excluded in cnfg.EXCLUDED_PLATFORMS
            )
        ]

    def create_library_structure(self) -> None:
        """Creates the library structure with a roms folder."""
        cnfg = cm.get_config()
        roms_path = os.path.join(LIBRARY_BASE_PATH, cnfg.ROMS_FOLDER_NAME)
        os.makedirs(roms_path, exist_ok=True)

    def detect_library_structure(self) -> LibraryStructure | None:
        """Detects the library structure type.

        Returns:
            "LibraryStructure.A" for Structure A (roms/{platform})
            "LibraryStructure.B" for Structure B ({platform}/roms)
            None if no structure detected
        """
        cnfg = cm.get_config()

        # Check if the roms directory exists (Structure A indicator)
        roms_path = os.path.join(LIBRARY_BASE_PATH, cnfg.ROMS_FOLDER_NAME)
        if os.path.isdir(roms_path):
            return LibraryStructure.A

        # Check if any platform folders with roms subfolders exist (Structure B)
        try:
            library_contents = os.listdir(LIBRARY_BASE_PATH)
            for item in library_contents:
                item_path = os.path.join(LIBRARY_BASE_PATH, item)
                roms_subfolder = os.path.join(item_path, cnfg.ROMS_FOLDER_NAME)
                if os.path.isdir(item_path) and os.path.isdir(roms_subfolder):
                    return LibraryStructure.B
        except (OSError, FileNotFoundError):
            pass

        return None

    def get_platforms_directory(self) -> str:
        cnfg = cm.get_config()

        # Fallback to config hint when detection is inconclusive
        return (
            cnfg.ROMS_FOLDER_NAME
            if os.path.isdir(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else ""
        )

    def get_platform_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()

        # Fallback to config hint when detection is inconclusive
        return (
            f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
            if os.path.isdir(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
        )

    async def add_platform(self, fs_slug: str) -> None:
        """Adds platform to the filesystem

        Args:
            fs_slug: platform slug
        """
        cnfg = cm.get_config()
        platform_path = self.get_platform_fs_structure(fs_slug)

        # For Structure B (or None), check if the base platform directory already
        # exists to prevent inadvertently creating roms subfolders inside existing
        # platform directories that were set up without a roms subfolder.
        # Note: this is a best-effort check; concurrent directory creation between
        # this check and make_directory() is unlikely in normal single-user usage.
        if not os.path.isdir(cnfg.HIGH_PRIO_STRUCTURE_PATH):
            base_platform_dir = self.validate_path(fs_slug)
            if base_platform_dir.exists():
                raise PlatformAlreadyExistsException(fs_slug)

        try:
            await self.make_directory(platform_path)
        except FileNotFoundError as e:
            raise PlatformAlreadyExistsException(fs_slug) from e

    async def get_platforms(self) -> list[str]:
        """Retrieves all platforms from the filesystem.

        Returns:
            List of platform slugs.
        """
        cnfg = cm.get_config()

        try:
            platforms = await self.list_directories(path=self.get_platforms_directory())
        except FileNotFoundError as e:
            raise FolderStructureNotMatchException() from e

        # For Structure B, only include directories that have a roms subfolder
        structure = self.detect_library_structure()
        if structure == LibraryStructure.B:
            filtered_platforms: list[str] = []
            for platform in platforms:
                roms_path = AnyioPath(
                    os.path.join(LIBRARY_BASE_PATH, platform, cnfg.ROMS_FOLDER_NAME)
                )
                if await roms_path.is_dir():
                    filtered_platforms.append(platform)
            platforms = filtered_platforms

        return self._exclude_platforms(platforms)
