from .igdb_handler import IGDBHandler
from .moby_handler import MobyGamesHandler
from .ra_handler import RAHandler
from .sgdb_handler import SGDBBaseHandler
from .ss_handler import SSHandler

meta_igdb_handler = IGDBHandler()
meta_moby_handler = MobyGamesHandler()
meta_ss_handler = SSHandler()
meta_sgdb_handler = SGDBBaseHandler()
meta_ra_handler = RAHandler()
