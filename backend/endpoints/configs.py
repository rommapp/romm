from fastapi import HTTPException, Request, status
from pydantic import BaseModel, field_validator

from config.config_manager import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
    VALID_GAMELIST_IMAGE_TYPES,
    VALID_GAMELIST_THUMBNAIL_TYPES,
    VALID_SCAN_PRIORITY_SOURCES,
    MetadataMediaType,
)
from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses.config import ConfigResponse
from exceptions.config_exceptions import ConfigNotWritableException
from handler.auth.constants import Scope
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/config",
    tags=["config"],
)


class PlatformBindingPayload(BaseModel):
    fs_slug: str
    slug: str


class ExclusionPayload(BaseModel):
    exclusion_value: str
    exclusion_type: str


class ScanSettingsPayload(BaseModel):
    """Full replacement of the scan.* config section.

    The three artwork override lists (cover/screenshot/manual) are optional:
    a null value clears the override so that field falls back to
    `artwork_priority`.
    """

    metadata_priority: list[str]
    artwork_priority: list[str]
    cover_priority: list[str] | None = None
    screenshot_priority: list[str] | None = None
    manual_priority: list[str] | None = None
    region_priority: list[str]
    language_priority: list[str]
    media: list[MetadataMediaType]
    gamelist_export: bool
    gamelist_thumbnail: MetadataMediaType
    gamelist_image: MetadataMediaType
    pegasus_export: bool

    @field_validator(
        "metadata_priority",
        "artwork_priority",
        "cover_priority",
        "screenshot_priority",
        "manual_priority",
    )
    @classmethod
    def validate_sources(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        invalid = [s for s in value if s not in VALID_SCAN_PRIORITY_SOURCES]
        if invalid:
            raise ValueError(f"Unknown metadata source(s): {sorted(set(invalid))}")
        # Drop duplicates while preserving priority order.
        return list(dict.fromkeys(value))

    @field_validator("region_priority", "language_priority")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        # Region/language codes are open sets (provider-defined), so we only
        # normalize to lowercase, trim blanks, and drop duplicates.
        cleaned = [code.strip().lower() for code in value if code and code.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("gamelist_thumbnail")
    @classmethod
    def validate_thumbnail(cls, value: MetadataMediaType) -> MetadataMediaType:
        if value not in VALID_GAMELIST_THUMBNAIL_TYPES:
            raise ValueError(
                f"Invalid gamelist thumbnail; valid options: "
                f"{sorted(o.value for o in VALID_GAMELIST_THUMBNAIL_TYPES)}"
            )
        return value

    @field_validator("gamelist_image")
    @classmethod
    def validate_image(cls, value: MetadataMediaType) -> MetadataMediaType:
        if value not in VALID_GAMELIST_IMAGE_TYPES:
            raise ValueError(
                f"Invalid gamelist image; valid options: "
                f"{sorted(o.value for o in VALID_GAMELIST_IMAGE_TYPES)}"
            )
        return value


@router.get("")
def get_config(request: Request) -> ConfigResponse:
    """Get config endpoint

    Returns:
        ConfigResponse: RomM's configuration
    """

    cfg = cm.get_config()
    return ConfigResponse(
        CONFIG_FILE_MOUNTED=cfg.CONFIG_FILE_MOUNTED,
        CONFIG_FILE_WRITABLE=cfg.CONFIG_FILE_WRITABLE,
        # Raw parser error may leak the config file path, so only send when authenticated
        CONFIG_FILE_PARSE_ERROR=(
            cfg.CONFIG_FILE_PARSE_ERROR if request.user.is_authenticated else None
        ),
        EXCLUDED_PLATFORMS=cfg.EXCLUDED_PLATFORMS,
        EXCLUDED_SINGLE_EXT=cfg.EXCLUDED_SINGLE_EXT,
        EXCLUDED_SINGLE_FILES=cfg.EXCLUDED_SINGLE_FILES,
        EXCLUDED_MULTI_FILES=cfg.EXCLUDED_MULTI_FILES,
        EXCLUDED_MULTI_PARTS_EXT=cfg.EXCLUDED_MULTI_PARTS_EXT,
        EXCLUDED_MULTI_PARTS_FILES=cfg.EXCLUDED_MULTI_PARTS_FILES,
        DEFAULT_EXCLUDED_DIRS=list(DEFAULT_EXCLUDED_DIRS),
        DEFAULT_EXCLUDED_FILES=list(DEFAULT_EXCLUDED_FILES),
        DEFAULT_EXCLUDED_EXTENSIONS=list(DEFAULT_EXCLUDED_EXTENSIONS),
        PLATFORMS_BINDING=cfg.PLATFORMS_BINDING,
        PLATFORMS_VERSIONS=cfg.PLATFORMS_VERSIONS,
        SKIP_HASH_CALCULATION=cfg.SKIP_HASH_CALCULATION,
        EJS_DEBUG=cfg.EJS_DEBUG,
        EJS_CACHE_LIMIT=cfg.EJS_CACHE_LIMIT,
        EJS_DISABLE_AUTO_UNLOAD=cfg.EJS_DISABLE_AUTO_UNLOAD,
        EJS_DISABLE_BATCH_BOOTUP=cfg.EJS_DISABLE_BATCH_BOOTUP,
        EJS_NETPLAY_ENABLED=cfg.EJS_NETPLAY_ENABLED,
        # Contains credentials, so only send when authenticated
        EJS_NETPLAY_ICE_SERVERS=(
            cfg.EJS_NETPLAY_ICE_SERVERS if request.user.is_authenticated else []
        ),
        EJS_CONTROLS=cfg.EJS_CONTROLS,
        EJS_SETTINGS=cfg.EJS_SETTINGS,
        SCAN_METADATA_PRIORITY=cfg.SCAN_METADATA_PRIORITY,
        SCAN_ARTWORK_PRIORITY=cfg.SCAN_ARTWORK_PRIORITY,
        SCAN_ARTWORK_PRIORITY_OVERRIDES=cfg.SCAN_ARTWORK_PRIORITY_OVERRIDES,
        SCAN_REGION_PRIORITY=cfg.SCAN_REGION_PRIORITY,
        SCAN_LANGUAGE_PRIORITY=cfg.SCAN_LANGUAGE_PRIORITY,
        SCAN_MEDIA=cfg.SCAN_MEDIA,
        GAMELIST_AUTO_EXPORT_ON_SCAN=cfg.GAMELIST_AUTO_EXPORT_ON_SCAN,
        GAMELIST_MEDIA_THUMBNAIL=cfg.GAMELIST_MEDIA_THUMBNAIL,
        GAMELIST_MEDIA_IMAGE=cfg.GAMELIST_MEDIA_IMAGE,
        PEGASUS_AUTO_EXPORT_ON_SCAN=cfg.PEGASUS_AUTO_EXPORT_ON_SCAN,
    )


@protected_route(router.post, "/system/platforms", [Scope.PLATFORMS_WRITE])
async def add_platform_binding(
    request: Request, payload: PlatformBindingPayload
) -> None:
    """Add platform binding to the configuration"""

    fs_slug = payload.fs_slug
    slug = payload.slug

    try:
        cm.add_platform_binding(fs_slug, slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.delete, "/system/platforms/{fs_slug}", [Scope.PLATFORMS_WRITE])
async def delete_platform_binding(request: Request, fs_slug: str) -> None:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_platform_binding(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.post, "/system/versions", [Scope.PLATFORMS_WRITE])
async def add_platform_version(
    request: Request, payload: PlatformBindingPayload
) -> None:
    """Add platform version to the configuration"""

    fs_slug = payload.fs_slug
    slug = payload.slug

    try:
        cm.add_platform_version(fs_slug, slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.delete, "/system/versions/{fs_slug}", [Scope.PLATFORMS_WRITE])
async def delete_platform_version(request: Request, fs_slug: str) -> None:
    """Delete platform version from the configuration"""

    try:
        cm.remove_platform_version(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.post, "/exclude", [Scope.PLATFORMS_WRITE])
async def add_exclusion(request: Request, payload: ExclusionPayload) -> None:
    """Add platform exclusion to the configuration"""

    exclusion_value = payload.exclusion_value
    exclusion_type = payload.exclusion_type
    try:
        cm.add_exclusion(exclusion_type, exclusion_value)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(
    router.delete,
    "/exclude/{exclusion_type}/{exclusion_value}",
    [Scope.PLATFORMS_WRITE],
)
async def delete_exclusion(
    request: Request, exclusion_type: str, exclusion_value: str
) -> None:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_exclusion(exclusion_type, exclusion_value)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.put, "/scan", [Scope.PLATFORMS_WRITE])
async def update_scan_settings(request: Request, payload: ScanSettingsPayload) -> None:
    """Replace the scan.* section of the configuration"""

    try:
        cm.update_scan_settings(
            metadata_priority=payload.metadata_priority,
            artwork_priority=payload.artwork_priority,
            artwork_overrides={
                "cover": payload.cover_priority,
                "screenshot": payload.screenshot_priority,
                "manual": payload.manual_priority,
            },
            region_priority=payload.region_priority,
            language_priority=payload.language_priority,
            media=[str(m) for m in payload.media],
            gamelist_export=payload.gamelist_export,
            gamelist_thumbnail=str(payload.gamelist_thumbnail),
            gamelist_image=str(payload.gamelist_image),
            pegasus_export=payload.pegasus_export,
        )
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
