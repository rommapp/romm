import os

from config import LIBRARY_BASE_PATH
from config.config_loader import config
from exceptions.fs_exceptions import FolderStructureNotMatchException
from handler.fs_handler.fs_handler import FSHandler


class PlatformsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def _exclude_platforms(platforms: list):
        return [
            platform
            for platform in platforms
            if platform not in config.EXCLUDED_PLATFORMS
        ]

    def get_platforms(self) -> list[str]:
        """Gets all filesystem platforms

        Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
        Automatically exclude folders defined in user config.
        """
        try:
            platforms: list[str] = (
                list(os.walk(config.HIGH_PRIO_STRUCTURE_PATH))[0][1]
                if os.path.exists(config.HIGH_PRIO_STRUCTURE_PATH)
                else list(os.walk(LIBRARY_BASE_PATH))[0][1]
            )
            return self._exclude_platforms(platforms)
        except IndexError as exc:
            raise FolderStructureNotMatchException from exc
