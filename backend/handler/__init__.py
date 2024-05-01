from handler.auth_handler import AuthHandler, OAuthHandler
from handler.db_handler.db_platforms_handler import DBPlatformsHandler
from handler.db_handler.db_roms_handler import DBRomsHandler
from handler.db_handler.db_saves_handler import DBSavesHandler
from handler.db_handler.db_states_handler import DBStatesHandler
from handler.db_handler.db_users_handler import DBUsersHandler
from handler.db_handler.db_stats_handler import DBStatsHandler
from handler.db_handler.db_screenshots_handler import DBScreenshotsHandler
from handler.db_handler.db_firmware_handler import DBFirmwareHandler
from handler.fs_handler.fs_assets_handler import FSAssetsHandler
from handler.fs_handler.fs_platforms_handler import FSPlatformsHandler
from handler.fs_handler.fs_resources_handler import FSResourceHandler
from handler.fs_handler.fs_roms_handler import FSRomsHandler
from handler.fs_handler.fs_firmware_handler import FSFirmwareHandler
from handler.gh_handler import GHHandler
from handler.metadata_handler.igdb_handler import IGDBHandler
from handler.metadata_handler.moby_handler import MobyGamesHandler
from handler.metadata_handler.sgdb_handler import SGDBHandler
from handler.socket_handler import SocketHandler

igdb_handler = IGDBHandler()
sgdb_handler = SGDBHandler()
moby_handler = MobyGamesHandler()
github_handler = GHHandler()
auth_handler = AuthHandler()
oauth_handler = OAuthHandler()
socket_handler = SocketHandler()
db_platform_handler = DBPlatformsHandler()
db_rom_handler = DBRomsHandler()
db_save_handler = DBSavesHandler()
db_state_handler = DBStatesHandler()
db_screenshot_handler = DBScreenshotsHandler()
db_user_handler = DBUsersHandler()
db_stats_handler = DBStatsHandler()
db_firmware_handler = DBFirmwareHandler()
fs_platform_handler = FSPlatformsHandler()
fs_rom_handler = FSRomsHandler()
fs_asset_handler = FSAssetsHandler()
fs_resource_handler = FSResourceHandler()
fs_firmware_handler = FSFirmwareHandler()
