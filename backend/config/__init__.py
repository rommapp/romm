import os
import secrets
from typing import Final

from dotenv import load_dotenv

load_dotenv()

# GUNICORN
DEV_PORT: Final = int(os.environ.get("VITE_BACKEND_DEV_PORT", "5000"))
DEV_HOST: Final = "127.0.0.1"
ROMM_HOST: Final = os.environ.get("ROMM_HOST", DEV_HOST)
GUNICORN_WORKERS: Final = int(os.environ.get("GUNICORN_WORKERS", 2))

# PATHS
ROMM_BASE_PATH: Final = os.environ.get("ROMM_BASE_PATH", "/romm")
LIBRARY_BASE_PATH: Final = f"{ROMM_BASE_PATH}/library"
RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
ASSETS_BASE_PATH: Final = f"{ROMM_BASE_PATH}/assets"
FRONTEND_RESOURCES_PATH: Final = "/assets/romm/resources"

# MARIADB
DB_HOST: Final = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT: Final = int(os.environ.get("DB_PORT", 3306))
DB_USER: Final = os.environ.get("DB_USER")
DB_PASSWD: Final = os.environ.get("DB_PASSWD")
DB_NAME: Final = os.environ.get("DB_NAME", "romm")

# REDIS
REDIS_HOST: Final = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT: Final = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD: Final = os.environ.get("REDIS_PASSWORD")
REDIS_USERNAME: Final = os.environ.get("REDIS_USERNAME", "")
REDIS_DB: Final = int(os.environ.get("REDIS_DB", 0))

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

# DB DRIVERS
ROMM_DB_DRIVER: Final = os.environ.get("ROMM_DB_DRIVER", "mariadb")

# AUTH
ROMM_AUTH_USERNAME: Final = os.environ.get("ROMM_AUTH_USERNAME", "admin")
ROMM_AUTH_PASSWORD: Final = os.environ.get("ROMM_AUTH_PASSWORD", "admin")
ROMM_AUTH_SECRET_KEY: Final = os.environ.get(
    "ROMM_AUTH_SECRET_KEY", secrets.token_hex(32)
)
DISABLE_CSRF_PROTECTION = os.environ.get("DISABLE_CSRF_PROTECTION", "false") == "true"
DISABLE_DOWNLOAD_ENDPOINT_AUTH = (
    os.environ.get("DISABLE_DOWNLOAD_ENDPOINT_AUTH", "false") == "true"
)

# SCANS
SCAN_TIMEOUT: Final = int(os.environ.get("SCAN_TIMEOUT", 60 * 60 * 4))  # 4 hours

# TASKS
ENABLE_RESCAN_ON_FILESYSTEM_CHANGE: Final = (
    os.environ.get("ENABLE_RESCAN_ON_FILESYSTEM_CHANGE", "false") == "true"
)
RESCAN_ON_FILESYSTEM_CHANGE_DELAY: Final = int(
    os.environ.get("RESCAN_ON_FILESYSTEM_CHANGE_DELAY", 5)  # 5 minutes
)
ENABLE_SCHEDULED_RESCAN: Final = (
    os.environ.get("ENABLE_SCHEDULED_RESCAN", "false") == "true"
)
SCHEDULED_RESCAN_CRON: Final = os.environ.get(
    "SCHEDULED_RESCAN_CRON",
    "0 3 * * *",  # At 3:00 AM every day
)
ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: Final = (
    os.environ.get("ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB", "false") == "true"
)
SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: Final = os.environ.get(
    "SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON",
    "0 4 * * *",  # At 4:00 AM every day
)

# TESTING
IS_PYTEST_RUN: Final = bool(os.environ.get("PYTEST_VERSION", False))

#TINFOIL
TINFOIL_WELCOME_MESSAGE: Final = os.environ.get("TINFOIL_WELCOME_MESSAGE", "RomM Switch Library")
