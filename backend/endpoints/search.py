import asyncio

import emoji
from decorators.auth import protected_route
from endpoints.responses.search import SearchCoverSchema, SearchRomSchema
from exceptions.endpoint_exceptions import SGDBInvalidAPIKeyException
from fastapi import HTTPException, Request, status
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.metadata import (
    meta_igdb_handler,
    meta_moby_handler,
    meta_sgdb_handler,
    meta_ss_handler,
)
from handler.metadata.igdb_handler import IGDB_API_ENABLED, IGDBRom
from handler.metadata.moby_handler import MOBY_API_ENABLED, MobyGamesRom
from handler.metadata.sgdb_handler import STEAMGRIDDB_API_ENABLED
from handler.metadata.ss_handler import SS_API_ENABLED, SSRom
from handler.scan_handler import _get_main_platform_igdb_id
from logger.formatter import BLUE, CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/search",
    tags=["search"],
)


@protected_route(router.get, "/roms", [Scope.ROMS_READ])
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

    if not IGDB_API_ENABLED and not SS_API_ENABLED and not MOBY_API_ENABLED:
        log.error("Search error: No metadata providers enabled")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No metadata providers enabled",
        )

    rom = db_rom_handler.get_rom(rom_id)
    if not rom:
        return []

    search_term = search_term or rom.fs_name_no_tags
    if not search_term:
        return []

    log.info(
        emoji.emojize(":magnifying_glass_tilted_right: Searching metadata providers...")
    )
    matched_roms: list = []

    log.info(f"Searching by {hl(search_by.lower(), color=CYAN)}:")
    log.info(
        emoji.emojize(
            f":video_game: {hl(rom.platform_display_name, color=BLUE)} [{rom.platform_fs_slug}]: {hl(search_term)}[{rom.fs_name}]"
        )
    )

    igdb_matched_roms: list[IGDBRom] = []
    moby_matched_roms: list[MobyGamesRom] = []
    ss_matched_roms: list[SSRom] = []

    if search_by.lower() == "id":
        try:
            igdb_rom, moby_rom, ss_rom = await asyncio.gather(
                meta_igdb_handler.get_matched_rom_by_id(int(search_term)),
                meta_moby_handler.get_matched_rom_by_id(int(search_term)),
                meta_ss_handler.get_matched_rom_by_id(int(search_term)),
            )
        except ValueError as exc:
            log.error(f"Search error: invalid ID '{search_term}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tried searching by ID, but '{search_term}' is not a valid ID",
            ) from exc
        else:
            igdb_matched_roms = [igdb_rom] if igdb_rom else []
            moby_matched_roms = [moby_rom] if moby_rom else []
            ss_matched_roms = [ss_rom] if ss_rom else []
    elif search_by.lower() == "name":
        igdb_matched_roms, moby_matched_roms, ss_matched_roms = await asyncio.gather(
            meta_igdb_handler.get_matched_roms_by_name(
                search_term, (await _get_main_platform_igdb_id(rom.platform))
            ),
            meta_moby_handler.get_matched_roms_by_name(
                search_term, rom.platform.moby_id
            ),
            meta_ss_handler.get_matched_roms_by_name(search_term, rom.platform.ss_id),
        )

    merged_dict: dict[str, dict] = {}

    for igdb_rom in igdb_matched_roms:
        merged_dict[igdb_rom["name"]] = {
            **igdb_rom,
            "igdb_url_cover": igdb_rom.pop("url_cover", ""),
            **merged_dict.get(igdb_rom.get("name", ""), {}),
        }

    for moby_rom in moby_matched_roms:
        merged_dict[moby_rom["name"]] = {  # type: ignore
            **moby_rom,
            "moby_url_cover": moby_rom.pop("url_cover", ""),
            **merged_dict.get(moby_rom.get("name", ""), {}),
        }

    for ss_rom in ss_matched_roms:
        merged_dict[ss_rom["name"]] = {
            **ss_rom,
            "ss_url_cover": ss_rom.pop("url_cover", ""),
            **merged_dict.get(ss_rom.get("name", ""), {}),
        }

    matched_roms = [
        {
            **{
                "slug": "",
                "name": "",
                "summary": "",
                "igdb_url_cover": "",
                "moby_url_cover": "",
                "ss_url_cover": "",
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


@protected_route(router.get, "/cover", [Scope.ROMS_READ])
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

    try:
        covers = await meta_sgdb_handler.get_details(search_term=search_term)
    except SGDBInvalidAPIKeyException as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str("Invalid SGDB API key")
        ) from err

    return [SearchCoverSchema.model_validate(cover) for cover in covers]
