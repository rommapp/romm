import emoji
from decorators.auth import protected_route
from endpoints.responses.search import SearchCoverSchema, SearchRomSchema
from fastapi import HTTPException, Request, status
from handler.auth.base_handler import Scope
from handler.database import db_rom_handler
from handler.metadata import meta_igdb_handler, meta_moby_handler, meta_sgdb_handler
from handler.metadata.igdb_handler import IGDB_API_ENABLED
from handler.metadata.moby_handler import MOBY_API_ENABLED
from handler.metadata.sgdb_handler import STEAMGRIDDB_API_ENABLED
from handler.scan_handler import _get_main_platform_igdb_id
from logger.logger import log
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.get, "/search/roms", [Scope.ROMS_READ])
async def search_rom(
    request: Request,
    rom_id: int,
    search_term: str | None = None,
    search_by: str = "name",
) -> list[SearchRomSchema]:
    """Search for rom in metadata providers

    Args:
        request (Request): FastAPI request
        rom_id (int): Rom ID
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

    rom = db_rom_handler.get_rom(rom_id)
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

    igdb_matched_roms = []
    moby_matched_roms = []

    if search_by.lower() == "id":
        try:
            igdb_rom = await meta_igdb_handler.get_matched_rom_by_id(int(search_term))
            moby_rom = await meta_moby_handler.get_matched_rom_by_id(int(search_term))
        except ValueError as exc:
            log.error(f"Search error: invalid ID '{search_term}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tried searching by ID, but '{search_term}' is not a valid ID",
            ) from exc
        else:
            igdb_matched_roms = [igdb_rom] if igdb_rom else []
            moby_matched_roms = [moby_rom] if moby_rom else []
    elif search_by.lower() == "name":
        igdb_matched_roms = await meta_igdb_handler.get_matched_roms_by_name(
            search_term, (await _get_main_platform_igdb_id(rom.platform))
        )
        moby_matched_roms = await meta_moby_handler.get_matched_roms_by_name(
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
                "platform_id": rom.platform_id,
            },
            **item,
        }
        for item in list(merged_dict.values())
    ]

    log.info("Results:")
    for m_rom in matched_roms:
        log.info(f"\t - {m_rom['name']}")

    return matched_roms


@protected_route(router.get, "/search/cover", [Scope.ROMS_READ])
async def search_cover(
    request: Request,
    search_term: str = "",
) -> list[SearchCoverSchema]:

    if not STEAMGRIDDB_API_ENABLED:
        log.error("Search error: No SteamGridDB enabled")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No SteamGridDB enabled",
        )

    covers = await meta_sgdb_handler.get_details(search_term=search_term)

    return [SearchCoverSchema.model_validate(cover) for cover in covers]
