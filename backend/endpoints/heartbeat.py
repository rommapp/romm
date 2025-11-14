from fastapi import HTTPException

from config import (
    DISABLE_EMULATOR_JS,
    DISABLE_RUFFLE_RS,
    DISABLE_SETUP_WIZARD,
    DISABLE_USERPASS_LOGIN,
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    OIDC_ENABLED,
    OIDC_PROVIDER,
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
    UPLOAD_TIMEOUT,
    YOUTUBE_BASE_URL,
)
from endpoints.responses.heartbeat import HeartbeatResponse
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
from utils import get_version
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
