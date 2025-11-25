from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import URLPath

from config import (
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    TINFOIL_WELCOME_MESSAGE,
)
from decorators.auth import protected_route
from endpoints.responses.feeds import (
    WEBRCADE_SLUG_TO_TYPE_MAP,
    WEBRCADE_SUPPORTED_PLATFORM_SLUGS,
    FPKGiFeedItemSchema,
    KekatsuDSItemSchema,
    PKGiFeedPS3ItemSchema,
    PKGiFeedPSPItemSchema,
    PKGiFeedPSVitaItemSchema,
    TinfoilFeedFileSchema,
    TinfoilFeedSchema,
    TinfoilFeedTitleDBSchema,
    WebrcadeFeedCategorySchema,
    WebrcadeFeedItemPropsSchema,
    WebrcadeFeedItemSchema,
    WebrcadeFeedSchema,
)
from handler.auth.constants import Scope
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import is_compressed_file
from handler.metadata import meta_igdb_handler
from handler.metadata.base_handler import (
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.rom import Rom, RomFile, RomFileCategory
from utils.router import APIRouter


def generate_rom_download_url(request: Request, rom: Rom) -> str:
    return str(
        request.url_for(
            "get_rom_content",
            id=rom.id,
            file_name=quote(rom.fs_name, safe="/"),
        )
    )


def generate_romfile_download_url(request: Request, file: RomFile) -> str:
    return str(
        request.url_for(
            "get_romfile_content",
            id=file.id,
            file_name=quote(file.file_name, safe="/"),
        )
    )


router = APIRouter(
    prefix="/feeds",
    tags=["feeds"],
)


@protected_route(
    router.get,
    "/webrcade",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def platforms_webrcade_feed(request: Request) -> WebrcadeFeedSchema:
    """Get webrcade feed endpoint
    https://docs.webrcade.com/feeds/format/

    Args:
        request (Request): Fastapi Request object

    Returns:
        WebrcadeFeedSchema: Webrcade feed object schema
    """

    platforms = db_platform_handler.get_platforms()

    categories = []
    for p in platforms:
        if p.slug not in WEBRCADE_SUPPORTED_PLATFORM_SLUGS:
            continue

        category_items = []
        roms = db_rom_handler.get_roms_scalar(platform_id=p.id)
        for rom in roms:
            download_url = generate_rom_download_url(request, rom)
            category_item = WebrcadeFeedItemSchema(
                title=rom.name or rom.fs_name_no_tags,
                description=rom.summary or "",
                type=WEBRCADE_SLUG_TO_TYPE_MAP.get(p.slug, p.slug),
                props=WebrcadeFeedItemPropsSchema(
                    rom=download_url,
                ),
            )
            if rom.path_cover_small:
                category_item["thumbnail"] = str(
                    URLPath(rom.path_cover_small).make_absolute_url(request.base_url)
                )
            if rom.path_cover_large:
                category_item["background"] = str(
                    URLPath(rom.path_cover_large).make_absolute_url(request.base_url)
                )
            category_items.append(category_item)

        categories.append(
            WebrcadeFeedCategorySchema(
                title=p.name,
                longTitle=f"{p.name} Games",
                background=str(
                    URLPath(
                        f"/assets/webrcade/feed/{p.slug.lower()}-background.png"
                    ).make_absolute_url(request.base_url)
                ),
                thumbnail=str(
                    URLPath(
                        f"/assets/webrcade/feed/{p.slug.lower()}-thumb.png"
                    ).make_absolute_url(request.base_url)
                ),
                items=category_items,
            )
        )

    return WebrcadeFeedSchema(
        title="RomM Feed",
        longTitle="Custom RomM Feed",
        description="Custom feed from your RomM library",
        thumbnail="https://raw.githubusercontent.com/rommapp/romm/release/.github/resources/isotipo.svg",
        background="https://raw.githubusercontent.com/rommapp/romm/release/.github/resources/screenshots/gallery.png",
        categories=categories,
    )


@protected_route(
    router.get,
    "/tinfoil",
    [],
)
async def tinfoil_index_feed(
    request: Request, slug: str = "switch"
) -> TinfoilFeedSchema:
    """Get tinfoil custom index feed endpoint
    https://blawar.github.io/tinfoil/custom_index/

    Args:
        request (Request): Fastapi Request object
        slug (str, optional): Platform slug. Defaults to "switch".

    Returns:
        TinfoilFeedSchema: Tinfoil feed object schema
    """
    switch = db_platform_handler.get_platform_by_fs_slug(slug)
    if not switch:
        return TinfoilFeedSchema(
            files=[],
            directories=[],
            error="Nintendo Switch platform not found",
        )

    async def extract_titledb(
        roms: Sequence[Rom],
    ) -> dict[str, dict]:
        titledb: dict[str, dict] = {}
        for rom in roms:
            tdb_match = SWITCH_TITLEDB_REGEX.search(rom.fs_name)
            pid_match = SWITCH_PRODUCT_ID_REGEX.search(rom.fs_name)
            if tdb_match:
                (
                    _search_term,
                    index_entry,
                ) = await meta_igdb_handler._switch_titledb_format(
                    tdb_match, rom.fs_name
                )
                if index_entry:
                    key = str(index_entry.get("nsuId", None))
                    if key is not None:  # only store if we have an id
                        titledb[key] = TinfoilFeedTitleDBSchema(
                            **index_entry
                        ).model_dump()
            elif pid_match:
                (
                    _search_term,
                    index_entry,
                ) = await meta_igdb_handler._switch_productid_format(
                    pid_match, rom.fs_name
                )
                if index_entry:
                    key = str(index_entry.get("nsuId", None))
                    if key is not None:
                        titledb[key] = TinfoilFeedTitleDBSchema(
                            **index_entry
                        ).model_dump()

        return titledb

    roms = db_rom_handler.get_roms_scalar(platform_id=switch.id)

    return TinfoilFeedSchema(
        files=[
            TinfoilFeedFileSchema(
                url=generate_romfile_download_url(request, rom_file),
                size=rom_file.file_size_bytes,
            )
            for rom in roms
            for rom_file in db_rom_handler.get_rom_files(rom.id)
            if rom_file.file_extension in ["xci", "nsp", "nsz", "xcz", "nro"]
        ],
        directories=[],
        success=TINFOIL_WELCOME_MESSAGE,
        titledb=await extract_titledb(roms),
    )


CONTENT_TYPE_MAP: dict[RomFileCategory, int] = {
    RomFileCategory.GAME: 1,
    RomFileCategory.DLC: 2,
    RomFileCategory.DEMO: 5,
    RomFileCategory.UPDATE: 6,
    RomFileCategory.PATCH: 6,
}


def validate_pkgi_file(file: RomFile, content_type: RomFileCategory) -> bool:
    # Match content type by file category
    if content_type != RomFileCategory.GAME and file.category != content_type:
        return False

    # Only consider top-level files as games
    if content_type == RomFileCategory.GAME and not file.is_top_level:
        return False

    # Compressed files get a free pass
    full_path = fs_rom_handler.validate_path(file.full_path)
    if content_type == RomFileCategory.GAME and is_compressed_file(str(full_path)):
        return True

    # PKGi only supports PKG files
    if file.file_extension.lower() != "pkg":
        return False

    return True


def generate_content_id(file: RomFile) -> str:
    """Generate content ID for a rom file"""
    titleid_match = SONY_SERIAL_REGEX.search(file.file_name)
    if titleid_match:
        # UP9644 is our custom Publisher ID
        return f"UP9644-{titleid_match.group(1).replace('-', '')}_00-0000000000000000"
    return f"UP9644-{file.id:09d}_00-0000000000000000"


@protected_route(
    router.get,
    "/pkgi/ps3/{content_type}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def pkgi_ps3_feed(
    request: Request,
    content_type: Annotated[str, PathVar(description="Content type")],
) -> Response:
    """Get PKGi PS3 feed endpoint
    https://github.com/bucanero/pkgi-ps3

    Args:
        request (Request): Fastapi Request object
        content_type (str): Content type (game, dlc, demo, update, patch, mod, translation, prototype)

    Returns:
        Response: txt file with PKGi PS3 database format
    """
    ps3_platform = db_platform_handler.get_platform_by_fs_slug(UPS.PS3)
    if not ps3_platform:
        raise HTTPException(status_code=404, detail="PlayStation 3 platform not found")

    try:
        content_type_enum = RomFileCategory(content_type)
        content_type_int = CONTENT_TYPE_MAP[content_type_enum]
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid content type: {content_type}"
        ) from e

    roms = db_rom_handler.get_roms_scalar(platform_id=ps3_platform.id)
    txt_lines = []

    for rom in roms:
        for file in db_rom_handler.get_rom_files(rom.id):
            if not validate_pkgi_file(file, content_type_enum):
                continue

            content_id = generate_content_id(file)
            download_url = generate_romfile_download_url(request, file)

            # Validate the item schema
            pkgi_item = PKGiFeedPS3ItemSchema(
                contentid=content_id,
                type=content_type_int,
                name=file.file_name_no_tags,
                description="",
                rap="",
                url=download_url,
                size=file.file_size_bytes,
                checksum=file.sha1_hash or "",
            )

            # Format: contentid,type,name,description,rap,url,size,checksum
            txt_line = f'{pkgi_item.contentid},{pkgi_item.type},"{pkgi_item.name}",{pkgi_item.description},{pkgi_item.rap},"{pkgi_item.url}",{pkgi_item.size},{pkgi_item.checksum}'
            txt_lines.append(txt_line)

    txt_content = "\n".join(txt_lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"filename=pkgi_{content_type_enum.value}.txt",
            "Cache-Control": "no-cache",
        },
    )


@protected_route(
    router.get,
    "/pkgi/psvita/{content_type}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def pkgi_psvita_feed(
    request: Request,
    content_type: Annotated[str, PathVar(description="Content type")],
) -> Response:
    """Get PKGi PS Vita feed endpoint
    https://github.com/mmozeiko/pkgi

    Args:
        request (Request): Fastapi Request object
        content_type (str): Content type (game, dlc, demo, update, patch, mod, translation, prototype)

    Returns:
        Response: txt file with PKGi PS Vita database format
    """
    psvita_platform = db_platform_handler.get_platform_by_fs_slug(UPS.PSVITA)
    if not psvita_platform:
        raise HTTPException(
            status_code=404, detail="PlayStation Vita platform not found"
        )

    try:
        content_type_enum = RomFileCategory(content_type)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid content type: {content_type}"
        ) from e

    roms = db_rom_handler.get_roms_scalar(platform_id=psvita_platform.id)
    txt_lines = []

    for rom in roms:
        for file in db_rom_handler.get_rom_files(rom.id):
            if not validate_pkgi_file(file, content_type_enum):
                continue

            content_id = generate_content_id(file)
            download_url = generate_romfile_download_url(request, file)

            pkgi_item = PKGiFeedPSVitaItemSchema(
                contentid=content_id,
                flags=0,
                name=file.file_name_no_tags,
                name2="",
                zrif="",
                url=download_url,
                size=file.file_size_bytes,
                checksum=file.sha1_hash or "",
            )

            # Format: contentid,flags,name,name2,zrif,url,size,checksum
            txt_line = f'{pkgi_item.contentid},{pkgi_item.flags},"{pkgi_item.name}",{pkgi_item.name2},{pkgi_item.zrif},"{pkgi_item.url}",{pkgi_item.size},{pkgi_item.checksum}'
            txt_lines.append(txt_line)

    txt_content = "\n".join(txt_lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"filename=pkgi_{content_type_enum.value}.txt",
            "Cache-Control": "no-cache",
        },
    )


@protected_route(
    router.get,
    "/pkgi/psp/{content_type}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def pkgi_psp_feed(
    request: Request,
    content_type: Annotated[str, PathVar(description="Content type")],
) -> Response:
    """Get PKGi PSP feed endpoint
    https://github.com/bucanero/pkgi-psp

    Args:
        request (Request): Fastapi Request object
        content_type (str): Content type (game, dlc, demo, update, patch, mod, translation, prototype)

    Returns:
        Response: txt file with PKGi PSP database format
    """
    psp_platform = db_platform_handler.get_platform_by_fs_slug(UPS.PSP)
    if not psp_platform:
        raise HTTPException(
            status_code=404, detail="PlayStation Portable platform not found"
        )

    try:
        content_type_enum = RomFileCategory(content_type)
        content_type_int = CONTENT_TYPE_MAP[content_type_enum]
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid content type: {content_type}"
        ) from e

    roms = db_rom_handler.get_roms_scalar(platform_id=psp_platform.id)
    txt_lines = []

    for rom in roms:
        for file in db_rom_handler.get_rom_files(rom.id):
            if not validate_pkgi_file(file, content_type_enum):
                continue

            content_id = generate_content_id(file)
            download_url = generate_romfile_download_url(request, file)

            # Validate the item schema
            pkgi_item = PKGiFeedPSPItemSchema(
                contentid=content_id,
                type=content_type_int,
                name=file.file_name_no_tags,
                description="",
                rap="",
                url=download_url,
                size=file.file_size_bytes,
                checksum=file.sha1_hash or "",
            )

            # Format: contentid,type,name,description,rap,url,size,checksum
            txt_line = f'{pkgi_item.contentid},{pkgi_item.type},"{pkgi_item.name}",{pkgi_item.description},{pkgi_item.rap},"{pkgi_item.url}",{pkgi_item.size},{pkgi_item.checksum}'
            txt_lines.append(txt_line)

    txt_content = "\n".join(txt_lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"filename=pkgi_{content_type_enum.value}.txt",
            "Cache-Control": "no-cache",
        },
    )


def _format_release_date(timestamp: int | None) -> str | None:
    """Format release date to MM-DD-YYYY format"""
    if not timestamp:
        return None

    return datetime.fromtimestamp(timestamp / 1000).strftime("%m-%d-%Y")


@protected_route(
    router.get,
    "/fpkgi/{platform_slug}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def fpkgi_feed(request: Request, platform_slug: str) -> Response:
    """
    https://github.com/ItsJokerZz/FPKGi

    Args:
        request (Request): Fastapi Request object
        platform_slug (str): Platform slug (ps4, ps5)

    Returns:
        Response: JSON file in FPKGi format
    """
    platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
    if not platform:
        raise HTTPException(
            status_code=404, detail=f"Platform {platform_slug} not found"
        )

    roms = db_rom_handler.get_roms_scalar(platform_id=platform.id)
    response_data = {}

    for rom in roms:
        download_url = generate_rom_download_url(request, rom)
        response_data[download_url] = FPKGiFeedItemSchema(
            name=rom.name or rom.fs_name,
            size=rom.fs_size_bytes,
            title_id=f"ROMM{str(rom.id)[-5:].zfill(5)}",
            region=rom.regions[0] if rom.regions else None,
            version=rom.revision or None,
            release=_format_release_date(rom.metadatum.first_release_date),
            min_fw=None,
            cover_url=str(
                URLPath(rom.path_cover_large).make_absolute_url(request.base_url)
            ),
        ).model_dump()

    return JSONResponse(
        content={"DATA": response_data},
        headers={"Cache-Control": "no-cache"},
    )


@protected_route(
    router.get,
    "/kekatsu/{platform_slug}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def kekatsu_ds_feed(request: Request, platform_slug: str) -> Response:
    """Get Kekatsu DS feed endpoint
    https://github.com/cavv-dev/Kekatsu-DS

    Args:
        request (Request): Fastapi Request object
        platform_slug (str): Platform slug (nds, nintendo-ds, ds, gba, etc.)

    Returns:
        Response: Text file with Kekatsu DS database format
    """
    platform = db_platform_handler.get_platform_by_fs_slug(platform_slug)
    if not platform:
        raise HTTPException(
            status_code=404, detail=f"Platform {platform_slug} not found"
        )

    roms = db_rom_handler.get_roms_scalar(platform_id=platform.id)

    txt_lines = []
    txt_lines.append("1")  # Database version
    txt_lines.append(
        "\t"
    )  # Delimiter (cannot use csv (coma) as kekatsu does not support " (double quotes) as a text delimiter)

    for rom in roms:
        download_url = generate_rom_download_url(request, rom)

        # Generate box art URL if cover exists
        box_art_url = ""
        if rom.path_cover_small:
            box_art_url = str(
                URLPath(rom.path_cover_small).make_absolute_url(request.base_url)
            )

        # Create Kekatsu DS item
        kekatsu_item = KekatsuDSItemSchema(
            title=rom.name or rom.fs_name_no_tags,
            platform=platform.slug,
            region=rom.regions[0] if rom.regions else "ANY",
            version=rom.revision or "1.0.0",
            author="RomM",
            download_url=download_url,
            filename=rom.fs_name,
            size=rom.fs_size_bytes,
            box_art_url=box_art_url,
        )

        # Format: title	platform	region	version	author	download_url	filename	size	box_art_url
        txt_line = f"{kekatsu_item.title}\t{kekatsu_item.platform}\t{kekatsu_item.region}\t{kekatsu_item.version}\t{kekatsu_item.author}\t{kekatsu_item.download_url}\t{kekatsu_item.filename}\t{kekatsu_item.size}\t{kekatsu_item.box_art_url}"
        txt_lines.append(txt_line)

    txt_content = "\n".join(txt_lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"filename=kekatsu_{platform_slug}.txt",
            "Cache-Control": "no-cache",
        },
    )
