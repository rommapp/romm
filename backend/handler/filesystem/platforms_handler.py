import os

from config import LIBRARY_BASE_PATH
from config.config_manager import Config
from config.config_manager import config_manager as cm

from .base_handler import FSHandler

# from exceptions.fs_exceptions import (
#     FolderStructureNotMatchException,
#     PlatformAlreadyExistsException,
# )


class FSPlatformsHandler(FSHandler):
    def __init__(self) -> None:
        super().__init__(base_path=LIBRARY_BASE_PATH)

    def _exclude_platforms(self, config: Config, platforms: list):
        return [
            platform
            for platform in platforms
            if platform not in config.EXCLUDED_PLATFORMS
        ]

    def get_plaform_fs_structure(self, fs_slug: str) -> str:
        cnfg = cm.get_config()
        return (
            f"{cnfg.ROMS_FOLDER_NAME}/{fs_slug}"
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cnfg.ROMS_FOLDER_NAME}"
        )

    def add_platforms(self, fs_slug: str) -> None:
        """Adds platform to the filesystem

        Args:
            fs_slug: platform slug
        """
        platform_path = self.get_plaform_fs_structure(fs_slug)
        self.make_directory(platform_path)

    def get_platforms(self) -> list[str]:
        """Retrieves all platforms from the filesystem.

        Returns:
            List of platform slugs.
        """
        cnfg = cm.get_config()
        platforms_dir = (
            cnfg.ROMS_FOLDER_NAME
            if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
            else ""
        )
        platforms = self.list_directories(path=platforms_dir)

        return self._exclude_platforms(cnfg, platforms)
