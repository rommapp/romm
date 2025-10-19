from collections.abc import Sequence
from typing import Annotated

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request
from fastapi.responses import Response
from starlette.datastructures import URLPath

from config import (
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    FRONTEND_RESOURCES_PATH,
    TINFOIL_WELCOME_MESSAGE,
)
from decorators.auth import protected_route
from endpoints.responses.feeds import (
    WEBRCADE_SLUG_TO_TYPE_MAP,
    WEBRCADE_SUPPORTED_PLATFORM_SLUGS,
    PKGiFeedItemSchema,
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
from handler.metadata import meta_igdb_handler
from handler.metadata.base_handler import (
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from models.rom import Rom, RomFileCategory
from utils.router import APIRouter

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
            category_item = WebrcadeFeedItemSchema(
                title=rom.name or "",
                description=rom.summary or "",
                type=WEBRCADE_SLUG_TO_TYPE_MAP.get(p.slug, p.slug),
                props=WebrcadeFeedItemPropsSchema(
                    rom=str(
                        request.url_for(
                            "get_rom_content",
                            id=rom.id,
                            file_name=rom.fs_name,
                        )
                    ),
                ),
            )
            if rom.path_cover_s:
                category_item["thumbnail"] = str(
                    URLPath(
                        f"{FRONTEND_RESOURCES_PATH}/{rom.path_cover_s}"
                    ).make_absolute_url(request.base_url)
                )
            if rom.path_cover_l:
                category_item["background"] = str(
                    URLPath(
                        f"{FRONTEND_RESOURCES_PATH}/{rom.path_cover_l}"
                    ).make_absolute_url(request.base_url)
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
                _search_term, index_entry = (
                    await meta_igdb_handler._switch_titledb_format(
                        tdb_match, rom.fs_name
                    )
                )
                if index_entry:
                    key = str(index_entry.get("nsuId", None))
                    if key is not None:  # only store if we have an id
                        titledb[key] = TinfoilFeedTitleDBSchema(
                            **index_entry
                        ).model_dump()
            elif pid_match:
                _search_term, index_entry = (
                    await meta_igdb_handler._switch_productid_format(
                        pid_match, rom.fs_name
                    )
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
                url=str(
                    request.url_for(
                        "get_romfile_content",
                        id=rom_file.id,
                        file_name=rom_file.file_name,
                    )
                ),
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


CONTENT_TYPE_MAP = {
    1: RomFileCategory.GAME,
    2: RomFileCategory.DLC,
    5: RomFileCategory.DEMO,
    6: RomFileCategory.UPDATE,
    6: RomFileCategory.PATCH,
}


@protected_route(
    router.get,
    "/pkgi/ps3/{content_type}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
def pkgi_ps3_feed(
    request: Request,
    content_type: Annotated[int, PathVar(description="Content type.", ge=1, le=9)],
) -> Response:
    ps3_platform = db_platform_handler.get_platform_by_fs_slug(UPS.PS3)
    if not ps3_platform:
        raise HTTPException(status_code=404, detail="PlayStation 3 platform not found")

    content_type_enum = CONTENT_TYPE_MAP.get(content_type)
    if not content_type_enum:
        raise HTTPException(
            status_code=400, detail=f"Invalid content type: {content_type}"
        )

    roms = db_rom_handler.get_roms_scalar(platform_id=ps3_platform.id)
    csv_lines = []

    for rom in roms:
        for file in db_rom_handler.get_rom_files(rom.id):
            if file.category != content_type_enum:
                continue

            if file.file_extension.lower() != "pkg":
                continue

            content_id = f"UP9644-{file.id:09d}_00-0000000000000000"
            titleid_match = SONY_SERIAL_REGEX.search(file.file_name)
            if titleid_match:
                content_id = f"UP9644-{titleid_match.group(1).replace('-', '')}_00-0000000000000000"

            download_url = str(
                request.url_for(
                    "get_romfile_content",
                    id=rom.id,
                    file_name=file.file_name,
                )
            )

            # Validate the item schema
            pkgi_item = PKGiFeedItemSchema(
                contentid=content_id,
                type=content_type,
                name=file.file_name_no_ext,
                description=file.file_name,
                rap=None,
                url=download_url,
                size=file.file_size_bytes,
                checksum=file.sha1_hash,
            )

            # Format: contentid,type,name,description,rap,url,size,checksum (tab-separated)
            csv_line = f"{pkgi_item.contentid},{pkgi_item.type},{pkgi_item.name},{pkgi_item.description},{pkgi_item.rap},{pkgi_item.url},{pkgi_item.size},{pkgi_item.checksum or ''}"
            csv_lines.append(csv_line)

    tsv_content = "\n".join(csv_lines)

    return Response(
        content=tsv_content,
        media_type="text/tab-separated-values",
        headers={
            f"Content-Disposition": f"attachment; filename=pkgi_{content_type_enum.value}.txt",
            "Cache-Control": "no-cache",
        },
    )
