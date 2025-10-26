import os
from typing import Final

import yarl
from dotenv import load_dotenv

load_dotenv()


def str_to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


ROMM_BASE_URL = os.environ.get("ROMM_BASE_URL", "http://0.0.0.0")
ROMM_PORT = int(os.environ.get("ROMM_PORT", 8080))

# GUNICORN
DEV_MODE: Final = str_to_bool(os.environ.get("DEV_MODE", "false"))
DEV_HOST: Final = os.environ.get("DEV_HOST", "127.0.0.1")
DEV_PORT: Final = int(os.environ.get("DEV_PORT", "5000"))
DEV_SQL_ECHO: Final = str_to_bool(os.environ.get("DEV_SQL_ECHO", "false"))

# PATHS
ROMM_BASE_PATH: Final = os.environ.get("ROMM_BASE_PATH", "/romm")
ROMM_TMP_PATH: Final = os.environ.get("ROMM_TMP_PATH", None)
LIBRARY_BASE_PATH: Final = f"{ROMM_BASE_PATH}/library"
RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
ASSETS_BASE_PATH: Final = f"{ROMM_BASE_PATH}/assets"
FRONTEND_RESOURCES_PATH: Final = "/assets/romm/resources"

# SEVEN ZIP
SEVEN_ZIP_TIMEOUT: Final = int(os.environ.get("SEVEN_ZIP_TIMEOUT", 60))

# DATABASE
DB_HOST: Final[str | None] = os.environ.get("DB_HOST", "127.0.0.1") or None
DB_PORT: Final[int | None] = (
    int(os.environ.get("DB_PORT", 3306)) if os.environ.get("DB_PORT") != "" else None
)
DB_USER: Final[str | None] = os.environ.get("DB_USER")
DB_PASSWD: Final[str | None] = os.environ.get("DB_PASSWD")
DB_NAME: Final[str] = os.environ.get("DB_NAME", "romm")
DB_QUERY_JSON: Final[str | None] = os.environ.get("DB_QUERY_JSON")
ROMM_DB_DRIVER: Final[str] = os.environ.get("ROMM_DB_DRIVER", "mariadb")

# REDIS
REDIS_HOST: Final = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT: Final = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD: Final = os.environ.get("REDIS_PASSWORD")
REDIS_USERNAME: Final = os.environ.get("REDIS_USERNAME", "")
REDIS_DB: Final = int(os.environ.get("REDIS_DB", 0))
REDIS_SSL: Final = str_to_bool(os.environ.get("REDIS_SSL", "false"))
REDIS_URL: Final = yarl.URL.build(
    scheme="rediss" if REDIS_SSL else "redis",
    user=REDIS_USERNAME or None,
    password=REDIS_PASSWORD or None,
    host=REDIS_HOST,
    port=REDIS_PORT,
    path=f"/{REDIS_DB}",
)

# IGDB
IGDB_CLIENT_ID: Final[str] = os.environ.get(
    "IGDB_CLIENT_ID", os.environ.get("CLIENT_ID", "")
).strip()
IGDB_CLIENT_SECRET: Final[str] = os.environ.get(
    "IGDB_CLIENT_SECRET", os.environ.get("CLIENT_SECRET", "")
).strip()

# MOBYGAMES
MOBYGAMES_API_KEY: Final[str] = os.environ.get("MOBYGAMES_API_KEY", "").strip()

# SCREENSCRAPER
SCREENSCRAPER_USER: Final[str] = os.environ.get("SCREENSCRAPER_USER", "")
SCREENSCRAPER_PASSWORD: Final[str] = os.environ.get("SCREENSCRAPER_PASSWORD", "")

# STEAMGRIDDB
STEAMGRIDDB_API_KEY: Final[str] = os.environ.get("STEAMGRIDDB_API_KEY", "").strip()

# RETROACHIEVEMENTS
RETROACHIEVEMENTS_API_KEY: Final[str] = os.environ.get("RETROACHIEVEMENTS_API_KEY", "")
REFRESH_RETROACHIEVEMENTS_CACHE_DAYS: Final[int] = int(
    os.environ.get("REFRESH_RETROACHIEVEMENTS_CACHE_DAYS", 30)
)

# LAUNCHBOX
LAUNCHBOX_API_ENABLED: Final[bool] = str_to_bool(
    os.environ.get("LAUNCHBOX_API_ENABLED", "false")
)

# PLAYMATCH
PLAYMATCH_API_ENABLED: Final[bool] = str_to_bool(
    os.environ.get("PLAYMATCH_API_ENABLED", "false")
)

# HASHEOUS
HASHEOUS_API_ENABLED: Final[bool] = str_to_bool(
    os.environ.get("HASHEOUS_API_ENABLED", "false")
)

# THEGAMESDB
TGDB_API_ENABLED: Final[bool] = str_to_bool(os.environ.get("TGDB_API_ENABLED", "false"))

# FLASHPOINT
FLASHPOINT_API_ENABLED: Final = str_to_bool(
    os.environ.get("FLASHPOINT_API_ENABLED", "false")
)

# HOWLONGTOBEAT
HLTB_API_ENABLED: Final = str_to_bool(os.environ.get("HLTB_API_ENABLED", "false"))

# AUTH
ROMM_AUTH_SECRET_KEY: Final[str] = os.environ.get("ROMM_AUTH_SECRET_KEY", "")
if not ROMM_AUTH_SECRET_KEY:
    raise ValueError("ROMM_AUTH_SECRET_KEY environment variable is not set!")

SESSION_MAX_AGE_SECONDS: Final = int(
    os.environ.get("SESSION_MAX_AGE_SECONDS", 14 * 24 * 60 * 60)
)  # 14 days, in seconds
DISABLE_CSRF_PROTECTION = str_to_bool(
    os.environ.get("DISABLE_CSRF_PROTECTION", "false")
)
DISABLE_DOWNLOAD_ENDPOINT_AUTH = str_to_bool(
    os.environ.get("DISABLE_DOWNLOAD_ENDPOINT_AUTH", "false")
)
DISABLE_USERPASS_LOGIN = str_to_bool(os.environ.get("DISABLE_USERPASS_LOGIN", "false"))
DISABLE_SETUP_WIZARD = str_to_bool(os.environ.get("DISABLE_SETUP_WIZARD", "false"))

# OIDC
OIDC_ENABLED: Final = str_to_bool(os.environ.get("OIDC_ENABLED", "false"))
OIDC_PROVIDER: Final = os.environ.get("OIDC_PROVIDER", "")
OIDC_CLIENT_ID: Final = os.environ.get("OIDC_CLIENT_ID", "").strip()
OIDC_CLIENT_SECRET: Final = os.environ.get("OIDC_CLIENT_SECRET", "").strip()
OIDC_CLAIM_ROLES: Final = os.environ.get("OIDC_CLAIM_ROLES", "").strip()
OIDC_ROLE_VIEWER: Final = os.environ.get("OIDC_ROLE_VIEWER", "").strip()
OIDC_ROLE_EDITOR: Final = os.environ.get("OIDC_ROLE_EDITOR", "").strip()
OIDC_ROLE_ADMIN: Final = os.environ.get("OIDC_ROLE_ADMIN", "").strip()
OIDC_REDIRECT_URI: Final = os.environ.get("OIDC_REDIRECT_URI", "")
OIDC_SERVER_APPLICATION_URL: Final = os.environ.get("OIDC_SERVER_APPLICATION_URL", "")
OIDC_TLS_CACERTFILE: Final = os.environ.get("OIDC_TLS_CACERTFILE", None)

# SCANS
SCAN_TIMEOUT: Final = int(os.environ.get("SCAN_TIMEOUT", 60 * 60 * 4))  # 4 hours
SCAN_WORKERS: Final = max(1, int(os.environ.get("SCAN_WORKERS", "1")))

# TASKS
TASK_TIMEOUT: Final = int(os.environ.get("TASK_TIMEOUT", 60 * 5))  # 5 minutes
TASK_RESULT_TTL: Final = int(
    os.environ.get("TASK_RESULT_TTL", 24 * 60 * 60)
)  # 24 hours
ENABLE_RESCAN_ON_FILESYSTEM_CHANGE: Final = str_to_bool(
    os.environ.get("ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", "false")
)
RESCAN_ON_FILESYSTEM_CHANGE_DELAY: Final = int(
    os.environ.get("RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 5)  # 5 minutes
)
ENABLE_SCHEDULED_RESCAN: Final = str_to_bool(
    os.environ.get("ENABLE_SCHEDULED_RESCAN", "false")
)
SCHEDULED_RESCAN_CRON: Final = os.environ.get(
    "SCHEDULED_RESCAN_CRON",
    "0 3 * * *",  # At 3:00 AM every day
)
ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: Final = str_to_bool(
    os.environ.get("ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB", "false")
)
SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: Final = os.environ.get(
    "SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA: Final = str_to_bool(
    os.environ.get("ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA", "false")
)
SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON: Final = os.environ.get(
    "SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP: Final = str_to_bool(
    os.environ.get("ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP", "false")
)
SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON: Final = os.environ.get(
    "SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)
ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC: Final[bool] = str_to_bool(
    os.environ.get("ENABLE_SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC", "false")
)
SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON: Final[str] = os.environ.get(
    "SCHEDULED_RETROACHIEVEMENTS_PROGRESS_SYNC_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)

# EMULATION
DISABLE_EMULATOR_JS = str_to_bool(os.environ.get("DISABLE_EMULATOR_JS", "false"))
DISABLE_RUFFLE_RS = str_to_bool(os.environ.get("DISABLE_RUFFLE_RS", "false"))

# FRONTEND
UPLOAD_TIMEOUT = int(os.environ.get("UPLOAD_TIMEOUT", 600))
KIOSK_MODE = str_to_bool(os.environ.get("KIOSK_MODE", "false"))

# LOGGING
LOGLEVEL: Final = os.environ.get("LOGLEVEL", "INFO").upper()
FORCE_COLOR: Final = str_to_bool(os.environ.get("FORCE_COLOR", "false"))
NO_COLOR: Final = str_to_bool(os.environ.get("NO_COLOR", "false"))

# YOUTUBE
YOUTUBE_BASE_URL: Final = os.environ.get(
    "YOUTUBE_BASE_URL", "https://www.youtube.com"
).rstrip("/")

# TINFOIL
TINFOIL_WELCOME_MESSAGE: Final = os.environ.get(
    "TINFOIL_WELCOME_MESSAGE", "RomM Switch Library"
)

# SENTRY
SENTRY_DSN: Final = os.environ.get("SENTRY_DSN", None)

# TESTING
IS_PYTEST_RUN: Final = bool(os.environ.get("PYTEST_VERSION", False))
