import os

from anyio import Path as AnyioPath

from config import LIBRARY_BASE_PATH, SYNC_ONLY_MODE
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from logger.logger import log

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

        Structure A ({roms_folder}/{platform}) takes priority over Structure B
        ({platform}/{roms_folder}) so that existing libraries are not broken when a
        stray {platform}/{roms_folder} directory happens to exist alongside them.

        Returns:
            "LibraryStructure.A" for Structure A (roms/{platform}) when the
                top-level roms folder exists.
            "LibraryStructure.B" for Structure B ({platform}/roms) when no
                top-level roms folder exists but at least one platform has a
                roms subfolder.
            None if no structure detected.
        """
        cnfg = cm.get_config()

        if cnfg.has_structure_path_a:
            return LibraryStructure.A

        if cnfg.has_structure_path_b:
            return LibraryStructure.B

        return None

    def get_platforms_directory(self) -> str:
        cnfg = cm.get_config()

        # Fallback to config hint when detection is inconclusive: default to
        # Structure A (roms/{platform}) so the bare library root is not treated
        # as a flat list of platforms. When the roms folder is missing entirely,
        # get_platforms() bootstraps it instead of failing.
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
        # Platforms are DB-only rows in sync-only mode; nothing to create on disk.
        if SYNC_ONLY_MODE:
            return

        platform_path = self.get_platform_fs_structure(fs_slug)

        try:
            await self.make_directory(platform_path)
        except FileNotFoundError as e:
            raise PlatformAlreadyExistsException(fs_slug) from e

    async def get_platforms(self) -> list[str]:
        """Retrieves all platforms from the filesystem.

        If no library structure exists yet (neither Structure A's top-level roms
        folder nor a Structure B {platform}/roms folder), defaults to Structure A
        by creating the roms folder and returns an empty list, so RomM starts
        cleanly with an empty library instead of failing.

        Returns:
            List of platform slugs.
        """
        cnfg = cm.get_config()

        try:
            platforms = await self.list_directories(path=self.get_platforms_directory())
        except FileNotFoundError:
            # The platforms directory does not exist, which means no library
            # structure has been set up yet. Bootstrap Structure A so the
            # filesystem is in a valid state and report an empty library.
            log.warning(
                "No library structure found; creating default Structure A "
                "(roms folder) and starting with an empty library."
            )
            try:
                self.create_library_structure()
            except OSError:
                log.error("Failed to create default library structure", exc_info=True)
            return []

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
