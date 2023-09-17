from fastapi import APIRouter, Request
from pydantic import BaseModel, BaseConfig

from handler import dbh
from utils.oauth import protected_route
from config import ROMM_HOST

router = APIRouter()

SUPPORTED_PLATFORM_SLUGS = [
    "3do",
    "arcade",
    "atari2600",
    "atari5200",
    "atari7800",
    "lynx",
    "wonderswan",
    "wonderswan-color",
    "colecovision",
    "turbografx16--1",
    "turbografx-16-slash-pc-engine-cd",
    "supergrafx",
    "pc-fx",
    "nes",
    "n64",
    "snes",
    "gb",
    "gba",
    "gbc",
    "virtualboy",
    "sg1000",
    "sms",
    "genesis-slash-megadrive",
    "segacd",
    "gamegear",
    "neo-geo-cd",
    "neogeoaes",
    "neogeomvs",
    "neo-geo-pocket",
    "neo-geo-pocket-color",
    "ps",
]

SLUG_TO_TYPE_MAP = {
    "neogeoaes": "neogeo",
    "neogeomvs": "neogeo",
}


class PlatformSchema(BaseModel):
    igdb_id: str
    sgdb_id: str

    slug: str
    name: str

    logo_path: str
    fs_slug: str

    n_roms: int

    class Config(BaseConfig):
        orm_mode = True


@protected_route(router.get, "/platforms", ["platforms.read"])
def platforms(request: Request) -> list[PlatformSchema]:
    """Returns platforms data"""
    return dbh.get_platforms()


@protected_route(router.get, "/platforms/feed", [])
def platforms_feed(request: Request):
    """Returns platforms data"""
    platforms = dbh.get_platforms()

    with dbh.session.begin() as session:
        return {
            "title": "RomM Feed",
            "longTitle": "Custom RomM Feed",
            "description": "Custom feed from your RomM library",
            "thumbnail": "https://raw.githubusercontent.com/zurdi15/romm/f2dd425d87ad8e21bf47f8258ae5dcf90f56fbc2/frontend/assets/isotipo.svg",
            "background": "https://raw.githubusercontent.com/zurdi15/romm/release/.github/screenshots/gallery.png",
            "categories": [
                {
                    "title": p.name,
                    "longTitle": f"{p.name} Games",
                    "background": f"{ROMM_HOST}/assets/feed/{p.slug.lower()}-background.png",
                    "thumbnail": f"{ROMM_HOST}/assets/feed/{p.slug.lower()}-thumb.png",
                    "description": "",
                    "items": [
                        {
                            "title": rom.r_name,
                            "description": rom.summary,
                            "type": SLUG_TO_TYPE_MAP.get(p.slug, p.slug),
                            "thumbnail": f"{ROMM_HOST}/assets/romm/resources/{rom.path_cover_s}",
                            "background": f"{ROMM_HOST}/assets/romm/resources/{rom.path_cover_l}",
                            "props": {"rom": f"{ROMM_HOST}{rom.download_path}"},
                        }
                        for rom in session.scalars(dbh.get_roms(p.slug)).all()
                    ],
                }
                for p in platforms
                if p.slug in SUPPORTED_PLATFORM_SLUGS
            ],
        }
