import os

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    PlatformAlreadyExistsException,
)

from .base_handler import FSHandler


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

    def get_platforms_directory(self) -> str:
        cnfg = cm.get_config()

        return (
            cnfg.ROMS_FOLDER_NAME
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else ""
        )

    def get_plaform_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()
        return (
            f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
        )

    async def add_platform(self, fs_slug: str) -> None:
        """Adds platform to the filesystem

        Args:
            fs_slug: platform slug
        """
        platform_path = self.get_plaform_fs_structure(fs_slug)

        try:
            await self.make_directory(platform_path)
        except FileNotFoundError as e:
            raise PlatformAlreadyExistsException(fs_slug) from e

    async def get_platforms(self) -> list[str]:
        """Retrieves all platforms from the filesystem.

        Returns:
            List of platform slugs.
        """
        try:
            platforms = await self.list_directories(path=self.get_platforms_directory())
        except FileNotFoundError as e:
            raise FolderStructureNotMatchException() from e

        return self._exclude_platforms(platforms)
