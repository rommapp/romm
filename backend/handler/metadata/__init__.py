from typing import Any, Callable, Final

from utils import int_or_none

from .csdb_handler import CsdbHandler, csdb_id_from_url
from .demozoo_handler import DemozooHandler, demozoo_id_from_url
from .flashpoint_handler import FlashpointHandler
from .gamelist_handler import GamelistHandler
from .hasheous_handler import HasheousHandler
from .hltb_handler import HLTBHandler
from .igdb_handler import IGDBHandler
from .launchbox_handler import LaunchboxHandler
from .libretro_handler import LibretroHandler
from .moby_handler import MobyGamesHandler
from .playmatch_handler import PlaymatchHandler
from .pouet_handler import PouetHandler, pouet_id_from_location
from .ra_handler import RAHandler
from .sgdb_handler import SGDBBaseHandler
from .ss_handler import SSHandler
from .tgdb_handler import TGDBHandler
from .upc_handler import UPCHandler

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
meta_upc_handler = UPCHandler()

_SCENE_ID_PARSERS: Final[dict[str, Callable[[str], int | None]]] = {
    "demozoo": demozoo_id_from_url,
    "pouet": pouet_id_from_location,
    "csdb": csdb_id_from_url,
}


def scene_id_or_none(value: Any, kind: str) -> int | None:
    """Accept a bare id or a Demozoo / Pouët / CSDb production URL.

    ``safe_int`` would turn a pasted URL into 0. Empty / unparseable → None.
    """
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.isdigit():
        # isdigit() also accepts superscripts and other digits int() rejects.
        return int_or_none(text)
    parser = _SCENE_ID_PARSERS.get(kind)
    return parser(text) if parser else None
