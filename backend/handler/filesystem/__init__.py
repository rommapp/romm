from .assets_handler import FSAssetsHandler
from .firmware_handler import FSFirmwareHandler
from .launchbox_handler import FSLaunchboxHandler
from .platforms_handler import FSPlatformsHandler
from .resources_handler import FSResourcesHandler
from .roms_handler import FSRomsHandler
from .sync_handler import FSSyncHandler

fs_asset_handler = FSAssetsHandler()
fs_firmware_handler = FSFirmwareHandler()
fs_platform_handler = FSPlatformsHandler()
fs_rom_handler = FSRomsHandler()
fs_resource_handler = FSResourcesHandler()
fs_sync_handler = FSSyncHandler()
fs_launchbox_handler = FSLaunchboxHandler()
