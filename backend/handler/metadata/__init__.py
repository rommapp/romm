from .flashpoint_handler import FlashpointHandler
from .gamelist_handler import GamelistHandler
from .hasheous_handler import HasheousHandler
from .hltb_handler import HLTBHandler
from .igdb_handler import IGDBHandler
from .launchbox_handler import LaunchboxHandler
from .libretro_handler import LibretroHandler
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
meta_libretro_handler = LibretroHandler()
meta_hasheous_handler = HasheousHandler()
meta_tgdb_handler = TGDBHandler()
meta_flashpoint_handler = FlashpointHandler()
meta_gamelist_handler = GamelistHandler()
meta_hltb_handler = HLTBHandler()

ALL_METADATA_HANDLERS = (
    meta_igdb_handler,
    meta_moby_handler,
    meta_ss_handler,
    meta_sgdb_handler,
    meta_ra_handler,
    meta_playmatch_handler,
    meta_launchbox_handler,
    meta_libretro_handler,
    meta_hasheous_handler,
    meta_tgdb_handler,
    meta_flashpoint_handler,
    meta_gamelist_handler,
    meta_hltb_handler,
)


def reset_metadata_handlers_scan_state() -> None:
    """Clear every provider's per-scan state at the start of a scan."""
    for handler in ALL_METADATA_HANDLERS:
        handler.reset_scan_state()
