import fnmatch
import os

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from logger.logger import log

from .base_handler import FSHandler


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
        """Creates the folder the configured structure enumerates platforms in."""
        os.makedirs(
            os.path.join(LIBRARY_BASE_PATH, self.get_platforms_directory()),
            exist_ok=True,
        )

    def library_structure_exists(self) -> bool:
        """Whether the folder platforms are enumerated in exists."""
        return os.path.isdir(
            os.path.join(LIBRARY_BASE_PATH, self.get_platforms_directory())
        )

    def get_platforms_directory(self) -> str:
        return cm.get_config().platforms_dir

    def get_platform_fs_structure(self, fs_slug: str) -> str:
        return cm.get_config().default_structure.games_dir(fs_slug)

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
        try:
            platforms = await self.list_directories(path=self.get_platforms_directory())
        except FileNotFoundError:
            # Bootstrap the configured folder so the filesystem is in a valid
            # state and report an empty library, rather than failing.
            log.warning(
                "No library structure found; creating the configured platforms "
                "folder and starting with an empty library."
            )
            try:
                self.create_library_structure()
            except OSError:
                log.error("Failed to create default library structure", exc_info=True)
            return []

        # Exclude before touching the directories so unreadable system folders
        # (e.g. Synology's #recycle) are never stat'ed
        platforms = self._exclude_platforms(platforms)

        return platforms
