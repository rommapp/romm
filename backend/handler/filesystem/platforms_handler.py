import os
from pathlib import Path

from config import LIBRARY_BASE_PATH
from config.config_manager import Config
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    PlatformAlreadyExistsException,
)

from .base_handler import FSHandler


class FSPlatformsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def _exclude_platforms(self, config: Config, platforms: list):
        return [
            platform
            for platform in platforms
            if platform not in config.EXCLUDED_PLATFORMS
        ]

    def add_platforms(self, fs_slug: str) -> None:
        cnfg = cm.get_config()
        try:
            (
                os.mkdir(f"{cnfg.HIGH_PRIO_STRUCTURE_PATH}/{fs_slug}")
                if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
                else Path(os.path.join(LIBRARY_BASE_PATH, fs_slug, "roms")).mkdir(
                    parents=True
                )
            )
        except FileExistsError:
            raise PlatformAlreadyExistsException(fs_slug)

    def get_platforms(self) -> list[str]:
        """Gets all filesystem platforms

        Returns list with all the filesystem platforms found in the LIBRARY_BASE_PATH.
        Automatically exclude folders defined in user config.
        """
        cnfg = cm.get_config()

        try:
            platforms: list[str] = (
                list(os.walk(cnfg.HIGH_PRIO_STRUCTURE_PATH))[0][1]
                if os.path.exists(cnfg.HIGH_PRIO_STRUCTURE_PATH)
                else list(os.walk(LIBRARY_BASE_PATH))[0][1]
            )
            return self._exclude_platforms(cnfg, platforms)
        except IndexError as exc:
            raise FolderStructureNotMatchException from exc
