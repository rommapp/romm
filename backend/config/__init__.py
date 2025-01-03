import os
import secrets
from typing import Final

import yarl
from dotenv import load_dotenv

load_dotenv()


def str_to_bool(value: str) -> bool:
    return value.lower() in ("true", "1")


# GUNICORN
DEV_MODE: Final = str_to_bool(os.environ.get("DEV_MODE", "false"))
DEV_HOST: Final = os.environ.get("DEV_HOST", "127.0.0.1")
DEV_PORT: Final = int(os.environ.get("DEV_PORT", "5000"))
GUNICORN_WORKERS: Final = int(os.environ.get("GUNICORN_WORKERS", 2))

# PATHS
ROMM_BASE_PATH: Final = os.environ.get("ROMM_BASE_PATH", "/romm")
LIBRARY_BASE_PATH: Final = f"{ROMM_BASE_PATH}/library"
RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
ASSETS_BASE_PATH: Final = f"{ROMM_BASE_PATH}/assets"
FRONTEND_RESOURCES_PATH: Final = "/assets/romm/resources"

# DATABASE
DB_HOST: Final = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT: Final = int(os.environ.get("DB_PORT", 3306))
DB_USER: Final = os.environ.get("DB_USER")
DB_PASSWD: Final = os.environ.get("DB_PASSWD")
DB_NAME: Final = os.environ.get("DB_NAME", "romm")
ROMM_DB_DRIVER: Final = os.environ.get("ROMM_DB_DRIVER", "mariadb")

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
IGDB_CLIENT_ID: Final = os.environ.get(
    "IGDB_CLIENT_ID", os.environ.get("CLIENT_ID", "")
)
IGDB_CLIENT_SECRET: Final = os.environ.get(
    "IGDB_CLIENT_SECRET", os.environ.get("CLIENT_SECRET", "")
)

# STEAMGRIDDB
STEAMGRIDDB_API_KEY: Final = os.environ.get("STEAMGRIDDB_API_KEY", "")

# MOBYGAMES
MOBYGAMES_API_KEY: Final = os.environ.get("MOBYGAMES_API_KEY", "")

# AUTH
ROMM_AUTH_SECRET_KEY: Final = os.environ.get(
    "ROMM_AUTH_SECRET_KEY", secrets.token_hex(32)
)
DISABLE_CSRF_PROTECTION = str_to_bool(
    os.environ.get("DISABLE_CSRF_PROTECTION", "false")
)
DISABLE_DOWNLOAD_ENDPOINT_AUTH = str_to_bool(
    os.environ.get("DISABLE_DOWNLOAD_ENDPOINT_AUTH", "false")
)

# OIDC
OIDC_ENABLED: Final = str_to_bool(os.environ.get("OIDC_ENABLED", "false"))
OIDC_PROVIDER: Final = os.environ.get("OIDC_PROVIDER", "")
OIDC_CLIENT_ID: Final = os.environ.get("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET: Final = os.environ.get("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI: Final = os.environ.get("OIDC_REDIRECT_URI", "")
OIDC_SERVER_APPLICATION_URL: Final = os.environ.get("OIDC_SERVER_APPLICATION_URL", "")

# SCANS
SCAN_TIMEOUT: Final = int(os.environ.get("SCAN_TIMEOUT", 60 * 60 * 4))  # 4 hours

# TASKS
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

# EMULATION
DISABLE_EMULATOR_JS = str_to_bool(os.environ.get("DISABLE_EMULATOR_JS", "false"))
DISABLE_RUFFLE_RS = str_to_bool(os.environ.get("DISABLE_RUFFLE_RS", "false"))

# FRONTEND
UPLOAD_TIMEOUT = int(os.environ.get("UPLOAD_TIMEOUT", 600))

# LOGGING
LOGLEVEL: Final = os.environ.get("LOGLEVEL", "INFO")
FORCE_COLOR: Final = str_to_bool(os.environ.get("FORCE_COLOR", "false"))
NO_COLOR: Final = str_to_bool(os.environ.get("NO_COLOR", "false"))

# SENTRY
SENTRY_DSN: Final = os.environ.get("SENTRY_DSN", None)

# TESTING
IS_PYTEST_RUN: Final = bool(os.environ.get("PYTEST_VERSION", False))
