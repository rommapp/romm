from datetime import datetime, timezone
from typing import Annotated

from fastapi import Body
from fastapi import Path as PathVar
from fastapi import Request, status

from decorators.auth import protected_route
from endpoints.responses.platform import PlatformSchema
from exceptions.endpoint_exceptions import PlatformNotFoundInDatabaseException
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.auth.constants import Scope
from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from handler.metadata import (
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS
from handler.scan_handler import scan_platform
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.platform import DEFAULT_COVER_ASPECT_RATIO, Platform
from utils.router import APIRouter

router = APIRouter(
    prefix="/platforms",
    tags=["platforms"],
)


@protected_route(
    router.post,
    "",
    [Scope.PLATFORMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def add_platform(
    request: Request,
    fs_slug: Annotated[str, Body(description="Platform slug.", embed=True)],
) -> PlatformSchema:
    """Create a platform."""

    try:
        await fs_platform_handler.add_platform(fs_slug=fs_slug)
    except PlatformAlreadyExistsException:
        log.info(f"Detected platform: {hl(fs_slug)}")

    scanned_platform = await scan_platform(fs_slug, [fs_slug])
    return PlatformSchema.model_validate(
        db_platform_handler.add_platform(scanned_platform)
    )


@protected_route(router.get, "", [Scope.PLATFORMS_READ])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Retrieve platforms."""

    return [
        PlatformSchema.model_validate(p) for p in db_platform_handler.get_platforms()
    ]


@protected_route(router.get, "/supported", [Scope.PLATFORMS_READ])
def get_supported_platforms(request: Request) -> list[PlatformSchema]:
    """Retrieve the list of supported platforms."""

    db_platforms = db_platform_handler.get_platforms()
    db_platforms_map = {p.slug: p for p in db_platforms}

    now = datetime.now(timezone.utc)
    supported_platforms = []

    for upslug in UPS:
        slug = upslug.value

        db_platform = db_platforms_map.get(slug, None)
        if db_platform:
            supported_platforms.append(
                PlatformSchema.model_validate(db_platform).model_dump()
            )
            continue

        igdb_platform = meta_igdb_handler.get_platform(slug)
        moby_platform = meta_moby_handler.get_platform(slug)
        ss_platform = meta_ss_handler.get_platform(slug)
        ra_platform = meta_ra_handler.get_platform(slug)
        launchbox_platform = meta_launchbox_handler.get_platform(slug)
        hasheous_platform = meta_hasheous_handler.get_platform(slug)
        tgdb_platform = meta_tgdb_handler.get_platform(slug)
        flashpoint_platform = meta_flashpoint_handler.get_platform(slug)
        hltb_platform = meta_hltb_handler.get_platform(slug)

        platform_attrs = {
            "id": -1,
            "name": slug.replace("-", " ").title(),
            "fs_slug": slug,
            "slug": slug,
            "roms": [],
            "rom_count": 0,
            "created_at": now,
            "updated_at": now,
            "fs_size_bytes": 0,
            "missing_from_fs": False,
            "aspect_ratio": DEFAULT_COVER_ASPECT_RATIO,
        }

        platform_attrs.update(
            {
                **hltb_platform,
                **flashpoint_platform,
                **hasheous_platform,
                **tgdb_platform,
                **launchbox_platform,
                **ra_platform,
                **moby_platform,
                **ss_platform,
                **igdb_platform,
                "igdb_id": igdb_platform.get("igdb_id")
                or hasheous_platform.get("igdb_id")
                or None,
                "ra_id": ra_platform.get("ra_id")
                or hasheous_platform.get("ra_id")
                or None,
                "tgdb_id": moby_platform.get("tgdb_id")
                or hasheous_platform.get("tgdb_id")
                or None,
                "name": igdb_platform.get("name")
                or ss_platform.get("name")
                or moby_platform.get("name")
                or ra_platform.get("name")
                or launchbox_platform.get("name")
                or hasheous_platform.get("name")
                or tgdb_platform.get("name")
                or flashpoint_platform.get("name")
                or hltb_platform.get("name")
                or slug.replace("-", " ").title(),
                "url_logo": igdb_platform.get("url_logo")
                or tgdb_platform.get("url_logo")
                or "",
            }
        )

        platform = Platform(**platform_attrs)
        supported_platforms.append(PlatformSchema.model_validate(platform).model_dump())

    return supported_platforms


@protected_route(
    router.get,
    "/{id}",
    [Scope.PLATFORMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
) -> PlatformSchema:
    """Retrieve a platform by ID."""

    platform = db_platform_handler.get_platform(id)
    if not platform:
        raise PlatformNotFoundInDatabaseException(id)
    return PlatformSchema.model_validate(platform)


@protected_route(
    router.put,
    "/{id}",
    [Scope.PLATFORMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
    aspect_ratio: Annotated[str | None, Body(description="Cover aspect ratio.")] = None,
    custom_name: Annotated[
        str | None, Body(description="Custom platform name.")
    ] = None,
) -> PlatformSchema:
    """Update a platform."""

    platform_db = db_platform_handler.get_platform(id)
    if not platform_db:
        raise PlatformNotFoundInDatabaseException(id)

    if aspect_ratio is not None:
        platform_db.aspect_ratio = aspect_ratio
    if custom_name is not None:
        platform_db.custom_name = custom_name
    platform_db = db_platform_handler.add_platform(platform_db)

    return PlatformSchema.model_validate(platform_db)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.PLATFORMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
) -> None:
    """Delete a platform by ID."""

    platform = db_platform_handler.get_platform(id)
    if not platform:
        raise PlatformNotFoundInDatabaseException(id)

    log.info(
        f"Deleting {hl(platform.name, color=BLUE)} [{hl(platform.fs_slug)}] from database"
    )
    db_platform_handler.delete_platform(id)
