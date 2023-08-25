import os
import secrets
from dotenv import load_dotenv
from typing import Final

load_dotenv()

# UVICORN
DEV_PORT: Final = int(os.environ.get("VITE_BACKEND_DEV_PORT", "5000"))
DEV_HOST: Final = "0.0.0.0"

# PATHS
ROMM_BASE_PATH: Final = os.environ.get("ROMM_BASE_PATH", "/romm")
LIBRARY_BASE_PATH: Final = f"{ROMM_BASE_PATH}/library"
FRONT_LIBRARY_PATH: Final = "/assets/romm/library"
ROMM_USER_CONFIG_PATH: Final = f"{ROMM_BASE_PATH}/config.yml"
SQLITE_DB_BASE_PATH: Final = f"{ROMM_BASE_PATH}/database"
RESOURCES_BASE_PATH: Final = f"{ROMM_BASE_PATH}/resources"
LOGS_BASE_PATH: Final = f"{ROMM_BASE_PATH}/logs"
HIGH_PRIO_STRUCTURE_PATH: Final = f"{LIBRARY_BASE_PATH}/roms"

# DEFAULT RESOURCES
DEFAULT_URL_COVER_L: Final = (
    "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
)
DEFAULT_PATH_COVER_L: Final = "default/default/cover/big.png"
DEFAULT_URL_COVER_S: Final = (
    "https://images.igdb.com/igdb/image/upload/t_cover_small/nocover.png"
)
DEFAULT_PATH_COVER_S: Final = "default/default/cover/small.png"

# MARIADB
DB_HOST: Final = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT: Final = int(os.environ.get("DB_PORT", 3306))
DB_USER: Final = os.environ.get("DB_USER")
DB_PASSWD: Final = os.environ.get("DB_PASSWD")
DB_NAME: Final = os.environ.get("DB_NAME", "romm")

# REDIS
ENABLE_EXPERIMENTAL_REDIS: Final = (
    os.environ.get("ENABLE_EXPERIMENTAL_REDIS", "false") == "true"
)
REDIS_HOST: Final = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT: Final = os.environ.get("REDIS_PORT", "6379")

# IGDB
IGDB_CLIENT_ID: Final = os.environ.get(
    "IGDB_CLIENT_ID", os.environ.get("CLIENT_ID", "")
)
IGDB_CLIENT_SECRET: Final = os.environ.get(
    "IGDB_CLIENT_SECRET", os.environ.get("CLIENT_SECRET", "")
)

# STEAMGRIDDB
STEAMGRIDDB_API_KEY: Final = os.environ.get("STEAMGRIDDB_API_KEY", "")

# DB DRIVERS
ROMM_DB_DRIVER: Final = os.environ.get("ROMM_DB_DRIVER", "sqlite")

# AUTH
ROMM_AUTH_ENABLED: Final = os.environ.get("ROMM_AUTH_ENABLED", "false") == "true"
ROMM_AUTH_USERNAME: Final = os.environ.get("ROMM_AUTH_USERNAME", "admin")
ROMM_AUTH_PASSWORD: Final = os.environ.get("ROMM_AUTH_PASSWORD", "admin")
ROMM_AUTH_SECRET_KEY: Final = os.environ.get(
    "ROMM_AUTH_SECRET_KEY", secrets.token_hex(32)
)
