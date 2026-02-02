import os

from fastapi import HTTPException, Request, status

from config import (
    DISABLE_EMULATOR_JS,
    DISABLE_RUFFLE_RS,
    DISABLE_SETUP_WIZARD,
    DISABLE_USERPASS_LOGIN,
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    LIBRARY_BASE_PATH,
    OIDC_AUTOLOGIN,
    OIDC_ENABLED,
    OIDC_PROVIDER,
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
    UPLOAD_TIMEOUT,
    YOUTUBE_BASE_URL,
)
from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses.heartbeat import HeartbeatResponse
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.auth.constants import Scope
from handler.database import db_user_handler
from handler.filesystem import fs_platform_handler
from handler.metadata import (
    meta_flashpoint_handler,
    meta_gamelist_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.scan_handler import MetadataSource
from logger.logger import log
from utils import get_version
from utils.platforms import get_supported_platforms
from utils.router import APIRouter

router = APIRouter(
    tags=["system"],
)


@router.get("/heartbeat")
async def heartbeat() -> HeartbeatResponse:
    """Endpoint to set the CSRF token in cache and return all the basic RomM config

    Returns:
        HeartbeatReturn: TypedDict structure with all the defined values in the HeartbeatReturn class.
    """
    igdb_enabled = meta_igdb_handler.is_enabled()
    flashpoint_enabled = meta_flashpoint_handler.is_enabled()
    ss_enabled = meta_ss_handler.is_enabled()
    moby_enabled = meta_moby_handler.is_enabled()
    ra_enabled = meta_ra_handler.is_enabled()
    sgdb_enabled = meta_sgdb_handler.is_enabled()
    launchbox_enabled = meta_launchbox_handler.is_enabled()
    hasheous_enabled = meta_hasheous_handler.is_enabled()
    playmatch_enabled = meta_playmatch_handler.is_enabled()
    hltb_enabled = meta_hltb_handler.is_enabled()
    tgdb_enabled = meta_tgdb_handler.is_enabled()

    return {
        "SYSTEM": {
            "VERSION": get_version(),
            "SHOW_SETUP_WIZARD": len(db_user_handler.get_admin_users()) == 0
            and not DISABLE_SETUP_WIZARD,
        },
        "METADATA_SOURCES": {
            "ANY_SOURCE_ENABLED": (
                igdb_enabled
                or ss_enabled
                or moby_enabled
                or ra_enabled
                or launchbox_enabled
                or hasheous_enabled
                or tgdb_enabled
                or flashpoint_enabled
                or hltb_enabled
            ),
            "IGDB_API_ENABLED": igdb_enabled,
            "SS_API_ENABLED": ss_enabled,
            "MOBY_API_ENABLED": moby_enabled,
            "STEAMGRIDDB_API_ENABLED": sgdb_enabled,
            "RA_API_ENABLED": ra_enabled,
            "LAUNCHBOX_API_ENABLED": launchbox_enabled,
            "HASHEOUS_API_ENABLED": hasheous_enabled,
            "PLAYMATCH_API_ENABLED": playmatch_enabled,
            "TGDB_API_ENABLED": tgdb_enabled,
            "FLASHPOINT_API_ENABLED": flashpoint_enabled,
            "HLTB_API_ENABLED": hltb_enabled,
        },
        "FILESYSTEM": {
            "FS_PLATFORMS": await fs_platform_handler.get_platforms(),
        },
        "EMULATION": {
            "DISABLE_EMULATOR_JS": DISABLE_EMULATOR_JS,
            "DISABLE_RUFFLE_RS": DISABLE_RUFFLE_RS,
        },
        "FRONTEND": {
            "UPLOAD_TIMEOUT": UPLOAD_TIMEOUT,
            "DISABLE_USERPASS_LOGIN": DISABLE_USERPASS_LOGIN,
            "YOUTUBE_BASE_URL": YOUTUBE_BASE_URL,
        },
        "OIDC": {
            "ENABLED": OIDC_ENABLED,
            "AUTOLOGIN": OIDC_AUTOLOGIN,
            "PROVIDER": OIDC_PROVIDER,
        },
        "TASKS": {
            "ENABLE_SCHEDULED_RESCAN": ENABLE_SCHEDULED_RESCAN,
            "SCHEDULED_RESCAN_CRON": SCHEDULED_RESCAN_CRON,
            "ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB": ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
            "SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON": SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
            "ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA": ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
            "SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON": SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
            "ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP": ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
            "SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON": SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
        },
    }


@router.get("/heartbeat/metadata/{source}")
async def metadata_heartbeat(source: str) -> bool:
    """Endpoint to return the heartbeat of the metadata sources"""
    try:
        metadata_source = MetadataSource(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid metadata source") from e

    match metadata_source:
        case MetadataSource.IGDB:
            return await meta_igdb_handler.heartbeat()
        case MetadataSource.MOBY:
            return await meta_moby_handler.heartbeat()
        case MetadataSource.SS:
            return await meta_ss_handler.heartbeat()
        case MetadataSource.RA:
            return await meta_ra_handler.heartbeat()
        case MetadataSource.LAUNCHBOX:
            return await meta_launchbox_handler.heartbeat()
        case MetadataSource.HASHEOUS:
            return await meta_hasheous_handler.heartbeat()
        case MetadataSource.TGDB:
            return await meta_tgdb_handler.heartbeat()
        case MetadataSource.SGDB:
            return await meta_sgdb_handler.heartbeat()
        case MetadataSource.FLASHPOINT:
            return await meta_flashpoint_handler.heartbeat()
        case MetadataSource.HLTB:
            return await meta_hltb_handler.heartbeat()
        case MetadataSource.GAMELIST:
            return await meta_gamelist_handler.heartbeat()
        case _:
            return False


@protected_route(
    router.get,
    "/setup/library",
    [],
)
async def get_setup_library_info(request: Request):
    """Get library structure information for setup wizard.

    Only accessible during initial setup (no admin users) or with authentication.

    Returns:
        - detected_structure: "struct_a" (roms/{platform}), "struct_b" ({platform}/roms), or None
        - existing_platforms: list of objects with fs_slug and rom_count
        - supported_platforms: list of all supported platforms with metadata
    """

    # Check authentication - only allow public access if no admin users
    # If admin users exist, this would need authentication (but won't be called during setup)

    # Auto-detect structure type
    # Structure A: /library/roms/{platform}
    # Structure B: /library/{platform}/roms
    # If there are admin users already, enforce the USERS_WRITE scope.
    if (
        Scope.PLATFORMS_READ not in request.auth.scopes
        and len(db_user_handler.get_admin_users()) > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    detected_structure = fs_platform_handler.detect_library_structure()

    # Get existing platforms from filesystem
    try:
        existing_platform_slugs = await fs_platform_handler.get_platforms()
    except Exception:
        log.warning("Error retrieving existing platforms", exc_info=True)
        existing_platform_slugs = []

    # Build existing platforms with rom counts
    existing_platforms = []
    if detected_structure and existing_platform_slugs:
        cnfg = cm.get_config()
        for fs_slug in existing_platform_slugs:
            rom_count = 0
            try:
                # Determine the roms directory based on structure
                if detected_structure == "struct_a":
                    roms_path = os.path.join(
                        LIBRARY_BASE_PATH, cnfg.ROMS_FOLDER_NAME, fs_slug
                    )
                else:  # Structure B
                    roms_path = os.path.join(
                        LIBRARY_BASE_PATH, fs_slug, cnfg.ROMS_FOLDER_NAME
                    )

                # Count files and folders in the roms directory
                if os.path.exists(roms_path):
                    items = os.listdir(roms_path)
                    # Filter out hidden files and system files
                    rom_count = len(
                        [
                            item
                            for item in items
                            if not item.startswith(".")
                            and item not in ["_resources", "_cache"]
                        ]
                    )
            except Exception:
                log.warning(
                    f"Error counting ROMs for platform {fs_slug}", exc_info=True
                )

            existing_platforms.append(
                {
                    "fs_slug": fs_slug,
                    "rom_count": rom_count,
                }
            )

    # Get all supported platforms with metadata
    supported_platforms = get_supported_platforms()

    return {
        "detected_structure": detected_structure,
        "existing_platforms": existing_platforms,
        "supported_platforms": supported_platforms,
    }


@protected_route(
    router.post,
    "/setup/platforms",
    [],
    status_code=status.HTTP_201_CREATED,
)
async def create_setup_platforms(request: Request, platform_slugs: list[str]):
    """Create platform folders during setup wizard.

    Only accessible during initial setup (no admin users) or with authentication.

    Args:
        platform_slugs: List of platform fs_slugs to create

    Returns:
        - success: bool
        - created_count: number of platforms created
        - message: success or error message
    """

    # If there are admin users already, enforce the USERS_WRITE scope.
    if (
        Scope.PLATFORMS_WRITE not in request.auth.scopes
        and len(db_user_handler.get_admin_users()) > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    if not platform_slugs:
        return {
            "success": True,
            "created_count": 0,
            "message": "No platforms selected",
        }

    try:
        # Detect structure type to determine if we need to create the roms folder
        detected_structure = fs_platform_handler.detect_library_structure()

        # If no structure detected, create structure A
        if detected_structure is None:
            fs_platform_handler.create_library_structure()

        # Create platform folders
        created_count = 0
        failed_platforms = []

        for fs_slug in platform_slugs:
            try:
                await fs_platform_handler.add_platform(fs_slug=fs_slug)
                created_count += 1
            except PlatformAlreadyExistsException:
                continue
            except (PermissionError, OSError) as e:
                failed_platforms.append(f"{fs_slug}: {str(e)}")

        if failed_platforms:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create some platform folders: {', '.join(failed_platforms)}",
            )

        return {
            "success": True,
            "created_count": created_count,
            "message": f"Successfully created {created_count} platform folder(s)",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating platform folders: {str(e)}",
        ) from e
