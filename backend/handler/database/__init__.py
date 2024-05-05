from .firmware_handler import DBFirmwareHandler
from .platforms_handler import DBPlatformsHandler
from .roms_handler import DBRomsHandler
from .saves_handler import DBSavesHandler
from .screenshots_handler import DBScreenshotsHandler
from .states_handler import DBStatesHandler
from .stats_handler import DBStatsHandler
from .users_handler import DBUsersHandler

db_firmware_handler = DBFirmwareHandler()
db_platforms_handler = DBPlatformsHandler()
db_roms_handler = DBRomsHandler()
db_saves_handler = DBSavesHandler()
db_screenshots_handler = DBScreenshotsHandler()
db_states_handler = DBStatesHandler()
db_stats_handler = DBStatsHandler()
db_users_handler = DBUsersHandler()
