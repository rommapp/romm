from .igdb_handler import IGDBBaseHandler
from .moby_handler import MobyGamesHandler
from .sgdb_handler import SGDBBaseHandler
from .ss_handler import SSBaseHandler

meta_igdb_handler = IGDBBaseHandler()
meta_ss_handler = SSBaseHandler()
meta_moby_handler = MobyGamesHandler()
meta_sgdb_handler = SGDBBaseHandler()
