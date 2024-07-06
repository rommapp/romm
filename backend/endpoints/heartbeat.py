from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from endpoints.responses.heartbeat import HeartbeatResponse
from fastapi import APIRouter
from handler.database import db_user_handler
from handler.filesystem import fs_platform_handler
from handler.metadata.igdb_handler import IGDB_API_ENABLED
from handler.metadata.moby_handler import MOBY_API_ENABLED
from handler.metadata.sgdb_handler import STEAMGRIDDB_API_ENABLED
from utils import get_version

router = APIRouter()


@router.get("/heartbeat")
def heartbeat() -> HeartbeatResponse:
    """Endpoint to set the CSFR token in cache and return all the basic RomM config

    Returns:
        HeartbeatReturn: TypedDict structure with all the defined values in the HeartbeatReturn class.
    """

    return {
        "VERSION": get_version(),
        "SHOW_SETUP_WIZARD": len(db_user_handler.get_admin_users()) == 0,
        "ANY_SOURCE_ENABLED": IGDB_API_ENABLED or MOBY_API_ENABLED,
        "METADATA_SOURCES": {
            "IGDB_API_ENABLED": IGDB_API_ENABLED,
            "MOBY_API_ENABLED": MOBY_API_ENABLED,
            "STEAMGRIDDB_ENABLED": STEAMGRIDDB_API_ENABLED,
        },
        "FS_PLATFORMS": fs_platform_handler.get_platforms(),
        "WATCHER": {
            "ENABLED": ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
            "TITLE": "Rescan on filesystem change",
            "MESSAGE": f"Runs a scan when a change is detected in the library path, with a {RESCAN_ON_FILESYSTEM_CHANGE_DELAY} minute delay",
        },
        "SCHEDULER": {
            "RESCAN": {
                "ENABLED": ENABLE_SCHEDULED_RESCAN,
                "CRON": SCHEDULED_RESCAN_CRON,
                "TITLE": "Scheduled rescan",
                "MESSAGE": "Rescans the entire library",
            },
            "SWITCH_TITLEDB": {
                "ENABLED": ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,  # noqa
                "CRON": SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
                "TITLE": "Scheduled Switch TitleDB update",
                "MESSAGE": "Updates the Nintendo Switch TitleDB file",
            },
        },
    }
