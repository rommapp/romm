import os
from typing import Final, overload

import yarl
from dotenv import load_dotenv

from utils.database import safe_int, safe_str_to_bool

load_dotenv()


# Supplying a string literal for fallback guarantees a `str` result
@overload
def _get_env(var: str, fallback: str) -> str: ...
@overload
def _get_env(var: str, fallback: None = None) -> str | None: ...


def _get_env(var: str, fallback: str | None = None) -> str | None:
    val = os.environ.get(var) or fallback
    return val.strip() if val else val


ROMM_BASE_URL: Final[str] = _get_env("ROMM_BASE_URL", "http://0.0.0.0")
ROMM_PORT: Final[int] = safe_int(_get_env("ROMM_PORT"), 8080)

# GUNICORN
DEV_MODE: Final[bool] = safe_str_to_bool(_get_env("DEV_MODE"))
DEV_HOST: Final[str] = _get_env("DEV_HOST", "127.0.0.1")
DEV_PORT: Final[int] = safe_int(_get_env("DEV_PORT"), 5000)
DEV_SQL_ECHO: Final[bool] = safe_str_to_bool(_get_env("DEV_SQL_ECHO"))

# PATHS
ROMM_BASE_PATH: Final[str] = _get_env("ROMM_BASE_PATH", "/romm")
ROMM_TMP_PATH: Final[str | None] = _get_env("ROMM_TMP_PATH")
LIBRARY_BASE_PATH: Final[str] = f"{ROMM_BASE_PATH}/library"
RESOURCES_BASE_PATH: Final[str] = f"{ROMM_BASE_PATH}/resources"
ASSETS_BASE_PATH: Final[str] = f"{ROMM_BASE_PATH}/assets"
FRONTEND_RESOURCES_PATH: Final[str] = "/assets/romm/resources"

# SEVEN ZIP
SEVEN_ZIP_TIMEOUT: Final[int] = safe_int(_get_env("SEVEN_ZIP_TIMEOUT"), 60)

# DATABASE
DB_HOST: Final[str | None] = _get_env("DB_HOST")
DB_PORT: Final[int] = safe_int(_get_env("DB_PORT"), 3306)
DB_USER: Final[str | None] = _get_env("DB_USER")
DB_PASSWD: Final[str | None] = _get_env("DB_PASSWD")
DB_NAME: Final[str] = _get_env("DB_NAME", "romm")
DB_QUERY_JSON: Final[str | None] = _get_env("DB_QUERY_JSON")
ROMM_DB_DRIVER: Final[str] = _get_env("ROMM_DB_DRIVER", "mariadb")

# REDIS
REDIS_HOST: Final[str | None] = _get_env("REDIS_HOST")
REDIS_PORT: Final[int] = safe_int(_get_env("REDIS_PORT"), 6379)
REDIS_PASSWORD: Final[str | None] = _get_env("REDIS_PASSWORD")
REDIS_USERNAME: Final[str | None] = _get_env("REDIS_USERNAME")
REDIS_DB: Final[int] = safe_int(_get_env("REDIS_DB"), 0)
REDIS_SSL: Final[bool] = safe_str_to_bool(_get_env("REDIS_SSL"))
REDIS_URL: Final[str] = str(
    yarl.URL.build(
        scheme="rediss" if REDIS_SSL else "redis",
        user=REDIS_USERNAME or None,
        password=REDIS_PASSWORD or None,
        host=REDIS_HOST or "127.0.0.1",
        port=REDIS_PORT,
        path=f"/{REDIS_DB}",
    )
)

# IGDB
IGDB_CLIENT_ID: Final[str | None] = _get_env("IGDB_CLIENT_ID")
IGDB_CLIENT_SECRET: Final[str | None] = _get_env("IGDB_CLIENT_SECRET")

# MOBYGAMES
MOBYGAMES_API_KEY: Final[str | None] = _get_env("MOBYGAMES_API_KEY")

# SCREENSCRAPER
SCREENSCRAPER_USER: Final[str | None] = _get_env("SCREENSCRAPER_USER")
SCREENSCRAPER_PASSWORD: Final[str | None] = _get_env("SCREENSCRAPER_PASSWORD")

# STEAMGRIDDB
STEAMGRIDDB_API_KEY: Final[str | None] = _get_env("STEAMGRIDDB_API_KEY")

# RETROACHIEVEMENTS
RETROACHIEVEMENTS_API_KEY: Final[str | None] = _get_env("RETROACHIEVEMENTS_API_KEY")
REFRESH_RETROACHIEVEMENTS_CACHE_DAYS: Final[int] = safe_int(
    _get_env("REFRESH_RETROACHIEVEMENTS_CACHE_DAYS"), 30
)

# LAUNCHBOX
LAUNCHBOX_API_ENABLED: Final[bool] = safe_str_to_bool(_get_env("LAUNCHBOX_API_ENABLED"))

# PLAYMATCH
PLAYMATCH_API_ENABLED: Final[bool] = safe_str_to_bool(_get_env("PLAYMATCH_API_ENABLED"))

# HASHEOUS
HASHEOUS_API_ENABLED: Final[bool] = safe_str_to_bool(_get_env("HASHEOUS_API_ENABLED"))

# THEGAMESDB
TGDB_API_ENABLED: Final[bool] = safe_str_to_bool(_get_env("TGDB_API_ENABLED"))

# FLASHPOINT
FLASHPOINT_API_ENABLED: Final[bool] = safe_str_to_bool(
    _get_env("FLASHPOINT_API_ENABLED")
)

# HOWLONGTOBEAT
HLTB_API_ENABLED: Final[bool] = safe_str_to_bool(_get_env("HLTB_API_ENABLED"))

# AUTH
ROMM_AUTH_SECRET_KEY: Final[str] = _get_env("ROMM_AUTH_SECRET_KEY", "")
if not ROMM_AUTH_SECRET_KEY:
    raise ValueError("ROMM_AUTH_SECRET_KEY environment variable is not set!")

SESSION_MAX_AGE_SECONDS: Final[int] = safe_int(
    _get_env("SESSION_MAX_AGE_SECONDS"), 14 * 24 * 60 * 60
)  # 14 days, in seconds
DISABLE_CSRF_PROTECTION: Final[bool] = safe_str_to_bool(
    _get_env("DISABLE_CSRF_PROTECTION")
)
DISABLE_DOWNLOAD_ENDPOINT_AUTH: Final[bool] = safe_str_to_bool(
    _get_env("DISABLE_DOWNLOAD_ENDPOINT_AUTH")
)
DISABLE_USERPASS_LOGIN: Final[bool] = safe_str_to_bool(
    _get_env("DISABLE_USERPASS_LOGIN")
)
DISABLE_SETUP_WIZARD: Final[bool] = safe_str_to_bool(_get_env("DISABLE_SETUP_WIZARD"))

# OIDC
OIDC_ENABLED: Final[bool] = safe_str_to_bool(_get_env("OIDC_ENABLED"))
OIDC_PROVIDER: Final[str] = _get_env("OIDC_PROVIDER", "")
OIDC_CLIENT_ID: Final[str] = _get_env("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET: Final[str] = _get_env("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI: Final[str] = _get_env("OIDC_REDIRECT_URI", "")
OIDC_SERVER_APPLICATION_URL: Final[str] = _get_env("OIDC_SERVER_APPLICATION_URL", "")
OIDC_CLAIM_ROLES: Final[str] = _get_env("OIDC_CLAIM_ROLES", "")
OIDC_ROLE_VIEWER: Final[str | None] = _get_env("OIDC_ROLE_VIEWER")
OIDC_ROLE_EDITOR: Final[str | None] = _get_env("OIDC_ROLE_EDITOR")
OIDC_ROLE_ADMIN: Final[str | None] = _get_env("OIDC_ROLE_ADMIN")
OIDC_TLS_CACERTFILE: Final[str | None] = _get_env("OIDC_TLS_CACERTFILE")

# SCANS
SCAN_TIMEOUT: Final[int] = safe_int(_get_env("SCAN_TIMEOUT"), 60 * 60 * 4)  # 4 hours
SCAN_WORKERS: Final[int] = max(1, safe_int(_get_env("SCAN_WORKERS"), 1))

# TASKS
TASK_TIMEOUT: Final[int] = safe_int(_get_env("TASK_TIMEOUT"), 60 * 5)  # 5 minutes
TASK_RESULT_TTL: Final[int] = safe_int(
    _get_env("TASK_RESULT_TTL"), 24 * 60 * 60
)  # 24 hours
ENABLE_RESCAN_ON_FILESYSTEM_CHANGE: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_RESCAN_ON_FILESYSTEM_CHANGE")
)
RESCAN_ON_FILESYSTEM_CHANGE_DELAY: Final[int] = safe_int(
    _get_env("RESCAN_ON_FILESYSTEM_CHANGE_DELAY"),
    5,  # 5 minutes
)
ENABLE_SCHEDULED_RESCAN: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_SCHEDULED_RESCAN")
)
SCHEDULED_RESCAN_CRON: Final[str] = _get_env(
    "SCHEDULED_RESCAN_CRON",
    "0 3 * * *",  # At 3:00 AM every day
)
ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB")
)
SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: Final[str] = _get_env(
    "SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA")
)
SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON: Final[str] = _get_env(
    "SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP")
)
SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON: Final[str] = _get_env(
    "SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC: Final[bool] = safe_str_to_bool(
    _get_env("ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC")
)
SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON: Final[str] = _get_env(
    "SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)

# EMULATION
DISABLE_EMULATOR_JS: Final[bool] = safe_str_to_bool(_get_env("DISABLE_EMULATOR_JS"))
DISABLE_RUFFLE_RS: Final[bool] = safe_str_to_bool(_get_env("DISABLE_RUFFLE_RS"))

# FRONTEND
UPLOAD_TIMEOUT: Final[int] = safe_int(_get_env("UPLOAD_TIMEOUT"), 600)
KIOSK_MODE: Final[bool] = safe_str_to_bool(_get_env("KIOSK_MODE"))

# LOGGING
LOGLEVEL: Final[str] = _get_env("LOGLEVEL", "INFO").upper()
FORCE_COLOR: Final[bool] = safe_str_to_bool(_get_env("FORCE_COLOR"))
NO_COLOR: Final[bool] = safe_str_to_bool(_get_env("NO_COLOR"))

# YOUTUBE
YOUTUBE_BASE_URL: Final[str] = _get_env(
    "YOUTUBE_BASE_URL", "https://www.youtube.com"
).rstrip("/")

# TINFOIL
TINFOIL_WELCOME_MESSAGE: Final[str] = _get_env(
    "TINFOIL_WELCOME_MESSAGE", "RomM Switch Library"
)

# SENTRY
SENTRY_DSN: Final[str | None] = _get_env("SENTRY_DSN")

# TESTING
IS_PYTEST_RUN: Final = bool(_get_env("PYTEST_VERSION"))
