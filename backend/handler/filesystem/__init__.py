from .assets_handler import FSAssetsHandler
from .firmware_handler import FSFirmwareHandler
from .launchbox_handler import FSLaunchboxHandler, get_fs_launchbox_handler
from .platforms_handler import FSPlatformsHandler
from .resources_handler import FSResourcesHandler
from .roms_handler import FSRomsHandler
from .sync_handler import FSSyncHandler, get_fs_sync_handler

fs_asset_handler = FSAssetsHandler()
fs_firmware_handler = FSFirmwareHandler()
fs_platform_handler = FSPlatformsHandler()
fs_rom_handler = FSRomsHandler()
fs_resource_handler = FSResourcesHandler()

__all__ = [
    "FSAssetsHandler",
    "FSFirmwareHandler",
    "FSLaunchboxHandler",
    "FSPlatformsHandler",
    "FSResourcesHandler",
    "FSRomsHandler",
    "FSSyncHandler",
    "fs_asset_handler",
    "fs_firmware_handler",
    "fs_platform_handler",
    "fs_resource_handler",
    "fs_rom_handler",
    "get_fs_launchbox_handler",
    "get_fs_sync_handler",
]
