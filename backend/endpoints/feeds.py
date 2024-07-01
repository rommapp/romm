from config import DISABLE_DOWNLOAD_ENDPOINT_AUTH, ROMM_HOST
from decorators.auth import protected_route
from endpoints.responses.feeds import (
    WEBRCADE_SLUG_TO_TYPE_MAP,
    WEBRCADE_SUPPORTED_PLATFORM_SLUGS,
    TinfoilFeedSchema,
    WebrcadeFeedSchema,
)
from fastapi import APIRouter, Request
from handler.database import db_platform_handler, db_rom_handler
from models.rom import Rom

router = APIRouter()


@protected_route(
    router.get,
    "/webrcade/feed",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["roms.read"],
)
def platforms_webrcade_feed(request: Request) -> WebrcadeFeedSchema:
    """Get webrcade feed endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        WebrcadeFeedSchema: Webrcade feed object schema
    """

    platforms = db_platform_handler.get_platforms()

    return {
        "title": "RomM Feed",
        "longTitle": "Custom RomM Feed",
        "description": "Custom feed from your RomM library",
        "thumbnail": "https://raw.githubusercontent.com/rommapp/romm/f2dd425d87ad8e21bf47f8258ae5dcf90f56fbc2/frontend/assets/isotipo.svg",
        "background": "https://raw.githubusercontent.com/rommapp/romm/release/.github/screenshots/gallery.png",
        "categories": [
            {
                "title": p.name,
                "longTitle": f"{p.name} Games",
                "background": f"{ROMM_HOST}/assets/webrcade/feed/{p.slug.lower()}-background.png",
                "thumbnail": f"{ROMM_HOST}/assets/webrcade/feed/{p.slug.lower()}-thumb.png",
                "description": "",
                "items": [
                    {
                        "title": rom.name,
                        "description": rom.summary,
                        "type": WEBRCADE_SLUG_TO_TYPE_MAP.get(p.slug, p.slug),
                        "thumbnail": f"{ROMM_HOST}/assets/romm/resources/{rom.path_cover_s}",
                        "background": f"{ROMM_HOST}/assets/romm/resources/{rom.path_cover_l}",
                        "props": {
                            "rom": f"{ROMM_HOST}/api/roms/{rom.id}/content/{rom.file_name}"
                        },
                    }
                    for rom in db_rom_handler.get_roms(platform_id=p.id)
                ],
            }
            for p in platforms
            if p.slug in WEBRCADE_SUPPORTED_PLATFORM_SLUGS
        ],
    }


@protected_route(router.get, "/tinfoil/feed", ["roms.read"])
def tinfoil_index_feed(request: Request, slug: str = "switch") -> TinfoilFeedSchema:
    """Get tinfoil custom index feed endpoint
    https://blawar.github.io/tinfoil/custom_index/

    Args:
        request (Request): Fastapi Request object
        slug (str, optional): Platform slug. Defaults to "switch".

    Returns:
        TinfoilFeedSchema: Tinfoil feed object schema
    """
    switch = db_platform_handler.get_platform_by_fs_slug(slug)
    files: list[Rom] = db_rom_handler.get_roms(platform_id=switch.id)

    return {
        "files": [
            {
                "url": f"{ROMM_HOST}/api/roms/{file.id}/content/{file.file_name}",
                "size": file.file_size_bytes,
            }
            for file in files
        ],
        "directories": [],
        "success": "RomM Switch Library",
    }
