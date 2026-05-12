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
            if platform not in cnfg.EXCLUDED_PLATFORMS
        ]

    def create_library_structure(self) -> None:
        """Creates the library structure with a roms folder."""
        cnfg = cm.get_config()
        roms_path = os.path.join(LIBRARY_BASE_PATH, cnfg.ROMS_FOLDER_NAME)
        os.makedirs(roms_path, exist_ok=True)

    def detect_library_structure(self) -> LibraryStructure | None:
        """Detects the library structure type.

        Returns:
            "LibraryStructure.B" for Structure B ({platform}/roms) when any
                platform has a roms subfolder.
            "LibraryStructure.A" for Structure A (roms/{platform}) when the
                top-level roms folder exists.
            None if no structure detected.
        """
        cnfg = cm.get_config()

        if cnfg.has_structure_path_b:
            return LibraryStructure.B

        roms_path = os.path.join(LIBRARY_BASE_PATH, cnfg.ROMS_FOLDER_NAME)
        if os.path.exists(roms_path):
            return LibraryStructure.A

        return None

    def get_platforms_directory(self) -> str:
        cnfg = cm.get_config()

        # Fallback to config hint when detection is inconclusive
        return "" if cnfg.has_structure_path_b else cnfg.ROMS_FOLDER_NAME

    def get_platform_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()

        # Fallback to config hint when detection is inconclusive
        return (
            f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
            if cnfg.has_structure_path_b
            else f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
        )

    async def add_platform(self, fs_slug: str) -> None:
        """Adds platform to the filesystem

        Args:
            fs_slug: platform slug
        """
        platform_path = self.get_platform_fs_structure(fs_slug)

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
                if await roms_path.exists():
                    filtered_platforms.append(platform)
            platforms = filtered_platforms

        return self._exclude_platforms(platforms)
