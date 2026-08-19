from .flashpoint_handler import FlashpointHandler
from .gamelist_handler import GamelistHandler
from .hasheous_handler import HasheousHandler
from .demozoo_handler import DemozooHandler
from .hltb_handler import HLTBHandler
from .igdb_handler import IGDBHandler
from .launchbox_handler import LaunchboxHandler
from .libretro_handler import LibretroHandler
from .moby_handler import MobyGamesHandler
from .playmatch_handler import PlaymatchHandler
from .csdb_handler import CsdbHandler
from .pouet_handler import PouetHandler
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
meta_libretro_handler = LibretroHandler()
meta_hasheous_handler = HasheousHandler()
meta_tgdb_handler = TGDBHandler()
meta_flashpoint_handler = FlashpointHandler()
meta_gamelist_handler = GamelistHandler()
meta_hltb_handler = HLTBHandler()
meta_demozoo_handler = DemozooHandler()
meta_pouet_handler = PouetHandler()
meta_csdb_handler = CsdbHandler()
