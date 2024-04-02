from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from endpoints.responses.heartbeat import HeartbeatResponse
from handler.metadata_handler.igdb_handler import IGDB_API_ENABLED
from handler.metadata_handler.moby_handler import MOBY_API_ENABLED
from fastapi import APIRouter
from handler import github_handler

router = APIRouter()


@router.get("/heartbeat")
def heartbeat() -> HeartbeatResponse:
    """Endpoint to set the CSFR token in cache and return all the basic RomM config

    Returns:
        HeartbeatReturn: TypedDict structure with all the defined values in the HeartbeatReturn class.
    """

    return {
        "VERSION": github_handler.get_version(),
        "NEW_VERSION": github_handler.check_new_version(),
        "ANY_SOURCE_ENABLED": IGDB_API_ENABLED or MOBY_API_ENABLED,
        "METADATA_SOURCES": {
            "IGDB_API_ENABLED": IGDB_API_ENABLED,
            "MOBY_API_ENABLED": MOBY_API_ENABLED,
        },
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
                "MESSAGE": "Updates the Nintedo Switch TitleDB file",
            },
        }
    }
