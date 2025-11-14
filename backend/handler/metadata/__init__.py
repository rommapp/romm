from .flashpoint_handler import FlashpointHandler
from .gamelist_handler import GamelistHandler
from .hasheous_handler import HasheousHandler
from .hltb_handler import HLTBHandler
from .igdb_handler import IGDBHandler
from .launchbox_handler import LaunchboxHandler
from .moby_handler import MobyGamesHandler
from .playmatch_handler import PlaymatchHandler
from .ra_handler import RAHandler
from .sgdb_handler import SGDBBaseHandler
from .ss_handler import SSHandler
from .tgdb_handler import TGDBHandler

meta_igdb_handler = IGDBHandler()
meta_moby_handler = MobyGamesHandler()
meta_ss_handler = SSHandler()
meta_sgdb_handler = SGDBBaseHandler()
meta_ra_handler = RAHandler()
meta_playmatch_handler = PlaymatchHandler()
meta_launchbox_handler = LaunchboxHandler()
meta_hasheous_handler = HasheousHandler()
meta_tgdb_handler = TGDBHandler()
meta_flashpoint_handler = FlashpointHandler()
meta_gamelist_handler = GamelistHandler()
meta_hltb_handler = HLTBHandler()
