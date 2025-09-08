from config import (
    DISABLE_EMULATOR_JS,
    DISABLE_RUFFLE_RS,
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
    meta_hasheous_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
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

    return {
        "SYSTEM": {
            "VERSION": get_version(),
            "SHOW_SETUP_WIZARD": len(db_user_handler.get_admin_users()) == 0,
        },
        "METADATA_SOURCES": {
            "ANY_SOURCE_ENABLED": (
                meta_igdb_handler.is_enabled()
                or meta_ss_handler.is_enabled()
                or meta_moby_handler.is_enabled()
                or meta_ra_handler.is_enabled()
                or meta_launchbox_handler.is_enabled()
                or meta_hasheous_handler.is_enabled()
                or meta_tgdb_handler.is_enabled()
            ),
            "IGDB_API_ENABLED": meta_igdb_handler.is_enabled(),
            "SS_API_ENABLED": meta_ss_handler.is_enabled(),
            "MOBY_API_ENABLED": meta_moby_handler.is_enabled(),
            "STEAMGRIDDB_API_ENABLED": meta_sgdb_handler.is_enabled(),
            "RA_API_ENABLED": meta_ra_handler.is_enabled(),
            "LAUNCHBOX_API_ENABLED": meta_launchbox_handler.is_enabled(),
            "HASHEOUS_API_ENABLED": meta_hasheous_handler.is_enabled(),
            "PLAYMATCH_API_ENABLED": meta_playmatch_handler.is_enabled(),
            "TGDB_API_ENABLED": meta_tgdb_handler.is_enabled(),
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
