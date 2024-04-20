import emoji
from handler.scan_handler import _get_main_platform_igdb_id
from decorators.auth import protected_route
from endpoints.responses.search import SearchRomSchema
from fastapi import APIRouter, Request, HTTPException, status
from handler import db_rom_handler, igdb_handler, moby_handler
from handler.metadata_handler.igdb_handler import IGDB_API_ENABLED
from handler.metadata_handler.moby_handler import MOBY_API_ENABLED
from logger.logger import log

router = APIRouter()


@protected_route(router.get, "/search/roms", ["roms.read"])
async def search_rom(
    request: Request,
    rom_id: str,
    search_term: str = None,
    search_by: str = "name",
    search_extended: bool = False,
) -> list[SearchRomSchema]:
    """Search for rom in metadata providers

    Args:
        request (Request): FastAPI request
        rom_id (str): Rom ID
        source (str): Source of the rom
        search_term (str, optional): Search term. Defaults to None.
        search_by (str, optional): Search by name or ID. Defaults to "name".
        search_extended (bool, optional): Search extended info. Defaults to False.

    Returns:
        list[SearchRomSchema]: List of matched roms
    """

    if not IGDB_API_ENABLED and not MOBY_API_ENABLED:
        log.error("Search error: No metadata providers enabled")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No metadata providers enabled",
        )

    rom = db_rom_handler.get_roms(rom_id)
    if not rom:
        return []

    search_term = search_term or rom.file_name_no_tags
    if not search_term:
        return []

    log.info(
        emoji.emojize(":magnifying_glass_tilted_right: Searching metadata providers...")
    )
    matched_roms: list = []

    log.info(f"Searching by {search_by.lower()}: {search_term}")
    log.info(emoji.emojize(f":video_game: {rom.platform_slug}: {rom.file_name}"))
    if search_by.lower() == "id":
        try:
            igdb_matched_roms = igdb_handler.get_matched_roms_by_id(int(search_term))
            moby_matched_roms = moby_handler.get_matched_roms_by_id(int(search_term))
        except ValueError:
            log.error(f"Search error: invalid ID '{search_term}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tried searching by ID, but '{search_term}' is not a valid ID",
            )
    elif search_by.lower() == "name":
        igdb_matched_roms = igdb_handler.get_matched_roms_by_name(
            search_term, _get_main_platform_igdb_id(rom.platform), search_extended
        )
        moby_matched_roms = moby_handler.get_matched_roms_by_name(
            search_term, rom.platform.moby_id
        )

    merged_dict = {
        item["name"]: {**item, "igdb_url_cover": item.pop("url_cover", "")}
        for item in igdb_matched_roms
    }
    for item in moby_matched_roms:
        merged_dict[item["name"]] = {
            **item,
            "moby_url_cover": item.pop("url_cover", ""),
            **merged_dict.get(item.get("name", ""), {}),
        }

    matched_roms = [
        {
            **{
                "slug": "",
                "name": "",
                "summary": "",
                "igdb_url_cover": "",
                "moby_url_cover": "",
                "url_screenshots": [],
            },
            **item,
        }
        for item in list(merged_dict.values())
    ]

    log.info("Results:")
    for m_rom in matched_roms:
        log.info(f"\t - {m_rom['name']}")

    return matched_roms
