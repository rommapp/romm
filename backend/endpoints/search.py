import asyncio

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from endpoints.responses.search import SearchCoverSchema, SearchRomSchema
from exceptions.endpoint_exceptions import SGDBInvalidAPIKeyException
from handler.auth.constants import Scope
from handler.database import db_rom_handler
from handler.metadata import (
    meta_flashpoint_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_sgdb_handler,
    meta_ss_handler,
)
from handler.metadata.flashpoint_handler import FlashpointRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.launchbox_handler import LaunchboxRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import SSRom
from handler.scan_handler import (
    MetadataSource,
    get_main_platform_igdb_id,
    get_priority_ordered_metadata_sources,
)
from logger.formatter import BLUE, CYAN
from logger.formatter import highlight as hl
from logger.logger import log
from utils import emoji
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

    if (
        not meta_igdb_handler.is_enabled()
        and not meta_ss_handler.is_enabled()
        and not meta_moby_handler.is_enabled()
        and not meta_flashpoint_handler.is_enabled()
        and not meta_launchbox_handler.is_enabled()
    ):
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
        f"{emoji.EMOJI_MAGNIFYING_GLASS_TILTED_RIGHT} Searching metadata providers..."
    )

    log.info(f"Searching by {hl(search_by.lower(), color=CYAN)}:")
    log.info(
        f"{emoji.EMOJI_VIDEO_GAME} {hl(rom.platform_display_name, color=BLUE)} [{rom.platform_fs_slug}]: {hl(search_term)}[{rom.fs_name}]"
    )

    igdb_matched_roms: list[IGDBRom] = []
    moby_matched_roms: list[MobyGamesRom] = []
    ss_matched_roms: list[SSRom] = []
    flashpoint_matched_roms: list[FlashpointRom] = []
    launchbox_matched_roms: list[LaunchboxRom] = []

    if search_by.lower() == "id":
        try:
            igdb_rom, moby_rom, ss_rom, lb_rom = await asyncio.gather(
                meta_igdb_handler.get_matched_rom_by_id(int(search_term)),
                meta_moby_handler.get_matched_rom_by_id(int(search_term)),
                meta_ss_handler.get_matched_rom_by_id(rom, int(search_term)),
                meta_launchbox_handler.get_matched_rom_by_id(int(search_term)),
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
            launchbox_matched_roms = [lb_rom] if lb_rom else []
    elif search_by.lower() == "name":
        (
            igdb_matched_roms,
            moby_matched_roms,
            ss_matched_roms,
            flashpoint_matched_roms,
            launchbox_matched_roms,
        ) = await asyncio.gather(
            meta_igdb_handler.get_matched_roms_by_name(
                search_term, get_main_platform_igdb_id(rom.platform)
            ),
            meta_moby_handler.get_matched_roms_by_name(
                search_term, rom.platform.moby_id
            ),
            meta_ss_handler.get_matched_roms_by_name(
                rom, search_term, rom.platform.ss_id
            ),
            meta_flashpoint_handler.get_matched_roms_by_name(
                search_term, rom.platform.slug
            ),
            meta_launchbox_handler.get_matched_roms_by_name(
                search_term, rom.platform.slug
            ),
        )

    merged_dict: dict[str, dict] = {}

    source_configs = {
        MetadataSource.IGDB: (
            igdb_matched_roms,
            meta_igdb_handler,
            "igdb_id",
            "igdb_url_cover",
        ),
        MetadataSource.MOBY: (
            moby_matched_roms,
            meta_moby_handler,
            "moby_id",
            "moby_url_cover",
        ),
        MetadataSource.FLASHPOINT: (
            flashpoint_matched_roms,
            meta_flashpoint_handler,
            "flashpoint_id",
            "flashpoint_url_cover",
        ),
        MetadataSource.LAUNCHBOX: (
            launchbox_matched_roms,
            meta_launchbox_handler,
            "launchbox_id",
            "launchbox_url_cover",
        ),
        MetadataSource.SS: (ss_matched_roms, meta_ss_handler, "ss_id", "ss_url_cover"),
    }

    ordered_sources = get_priority_ordered_metadata_sources(
        metadata_sources=list(source_configs.keys()), priority_type="metadata"
    )

    for meta_source in ordered_sources:
        source_matched_roms, meta_handler, id_key, cover_key = source_configs[
            meta_source
        ]
        for source_rom in source_matched_roms:  # trunk-ignore(mypy/attr-defined)
            if source_rom[id_key]:
                normalized_name = meta_handler.normalize_search_term(
                    source_rom.get("name", ""),
                    remove_articles=False,
                )
                merged_dict[normalized_name] = {
                    **source_rom,
                    "is_identified": True,
                    "is_unidentified": False,
                    "platform_id": rom.platform_id,
                    cover_key: source_rom.get("url_cover", ""),
                    **merged_dict.get(normalized_name, {}),
                }

    async def get_sgdb_rom(name: str) -> tuple[str, SGDBRom]:
        return name, await meta_sgdb_handler.get_details_by_names([name])

    sgdb_roms = await asyncio.gather(
        *[get_sgdb_rom(name) for name in list(merged_dict.keys())]
    )

    for name, sgdb_rom in sgdb_roms:
        if sgdb_rom["sgdb_id"]:
            merged_dict[name] = {
                **merged_dict[name],
                "sgdb_id": sgdb_rom.get("sgdb_id", ""),
                "sgdb_url_cover": sgdb_rom.get("url_cover", ""),
            }

    matched_roms: list = list(merged_dict.values())

    log.info("Results:")
    for m_rom in matched_roms:
        log.info(f"\t - {m_rom['name']}")

    return matched_roms


@protected_route(router.get, "/cover", [Scope.ROMS_READ])
async def search_cover(
    request: Request,
    search_term: str = "",
) -> list[SearchCoverSchema]:

    if not meta_sgdb_handler.is_enabled():
        log.error("Search error: No SteamGridDB enabled")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No SteamGridDB enabled",
        )

    try:
        covers = await meta_sgdb_handler.get_details(search_term=search_term)
    except SGDBInvalidAPIKeyException as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SGDB API key"
        ) from err

    return [SearchCoverSchema.model_validate(cover) for cover in covers]
