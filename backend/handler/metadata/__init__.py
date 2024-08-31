from .igdb_handler import IGDBBaseHandler
from .moby_handler import MobyGamesHandler
from .ra_handler import RetroAchievementsHandler
from .sgdb_handler import SGDBBaseHandler

meta_igdb_handler = IGDBBaseHandler()
meta_moby_handler = MobyGamesHandler()
meta_sgdb_handler = SGDBBaseHandler()
meta_ra_handler = RetroAchievementsHandler()
