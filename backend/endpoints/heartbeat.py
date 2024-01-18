from config import (
    ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
    ENABLE_SCHEDULED_RESCAN,
    ENABLE_SCHEDULED_UPDATE_MAME_XML,
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
    RESCAN_ON_FILESYSTEM_CHANGE_DELAY,
    ROMM_AUTH_ENABLED,
    SCHEDULED_RESCAN_CRON,
    SCHEDULED_UPDATE_MAME_XML_CRON,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
)
from endpoints.responses.heartbeat import HeartbeatResponse
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
        "ROMM_AUTH_ENABLED": ROMM_AUTH_ENABLED,
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
            "MAME_XML": {
                "ENABLED": ENABLE_SCHEDULED_UPDATE_MAME_XML,
                "CRON": SCHEDULED_UPDATE_MAME_XML_CRON,
                "TITLE": "Scheduled MAME XML update",
                "MESSAGE": "Updates the MAME XML file",
            },
        }
    }
