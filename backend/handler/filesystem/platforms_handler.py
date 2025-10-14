import os

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import (
    FolderStructureNotMatchException,
    PlatformAlreadyExistsException,
)
from utils.structure_parser import LibraryStructure

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

    def get_plaforms_structure(self) -> LibraryStructure:
        cnfg = cm.get_config()
        return LibraryStructure(cnfg.LIBRARY_STRUCTURE, "roms")

    async def add_platform(self, fs_slug: str) -> None:
        """Adds platform to the filesystem

        Args:
            fs_slug: platform slug
        """
        platform_path = self.get_plaforms_structure().resolve_path(platform=fs_slug)

        try:
            await self.make_directory(platform_path)
        except FileNotFoundError as e:
            raise PlatformAlreadyExistsException(fs_slug) from e

    async def get_platforms(self) -> list[str]:
        """Retrieves all platforms from the filesystem.

        Returns:
            List of platform slugs.
        """
        structure = self.get_plaforms_structure()
        platforms = []

        platforms_dir = structure.get_platforms_directory()
        platform_position = structure.get_platform_position()

        print(f"DEBUG: Platforms dir: {platforms_dir}")
        print(f"DEBUG: Platform position: {platform_position}")

        directories = await self.list_directories(path=platforms_dir)
        for directory in directories:
            if directory == platform_position:
                platforms.append(directory)
            else:
                nested_platforms = await self._find_platforms_recursively(
                    structure, directory
                )
                platforms.extend(nested_platforms)

        print(f"DEBUG: Directories: {directories}")

        return self._exclude_platforms(platforms)

    # async def _find_platforms_recursively(self, structure: LibraryStructure, current_path: str = "") -> list[str]:
    #     # Get the platform position in the structure
    #     platform_position = structure.get_platform_position()

    #     try:
    #         # Get directories to explore
    #         directories = await self.list_directories(path=current_path)

    #         for item in directories:
    #             item_path = os.path.join(current_path, item)

    #             # Check if we're at the platform level (accounting for depth offset)
    #             if depth + depth_offset == platform_position:
    #                 # We're at the platform level, this is a platform directory
    #                 platforms.append(item)
    #             else:
    #                 # We're not at the platform level yet, continue exploring
    #                 nested_platforms = await self._find_platforms_recursively(structure, item_path, depth + 1)
    #                 platforms.extend(nested_platforms)

    #     except FileNotFoundError:
    #         # Directory doesn't exist, continue
    #         pass
    #     return platforms

    # async def _contains_games(self, directory_path: str) -> bool:
    #     """Check if a directory contains games (files or subdirectories that could be games).

    #     Args:
    #         directory_path: Path to check

    #     Returns:
    #         True if directory contains games, False otherwise
    #     """
    #     try:
    #         # Check for files first - if there are files, this is likely a platform
    #         files = await self.list_files(path=directory_path)
    #         print(f"DEBUG: {directory_path} has {len(files)} files: {files}")
    #         if len(files) > 0:
    #             return True

    #         # Check for directories - only consider it a platform if directories contain files
    #         directories = await self.list_directories(path=directory_path)
    #         print(f"DEBUG: {directory_path} has {len(directories)} directories: {directories}")
    #         if len(directories) > 0:
    #             # Check if any subdirectory contains files (indicating games)
    #             for subdir in directories:
    #                 subdir_path = os.path.join(directory_path, subdir)
    #                 subdir_files = await self.list_files(path=subdir_path)
    #                 print(f"DEBUG: {subdir} has {len(subdir_files)} files: {subdir_files}")
    #                 if len(subdir_files) > 0:
    #                     return True

    #         return False

    #     except FileNotFoundError as e:
    #         print(f"DEBUG: FileNotFoundError in _contains_games for {directory_path}: {e}")
    #         return False
