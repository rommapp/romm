import os
from dotenv import load_dotenv

load_dotenv()

# Uvicorn
DEV_PORT: int = int(os.environ.get('VITE_BACKEND_DEV_PORT', '5000'))
DEV_HOST: str = "0.0.0.0"

# PATHS
ROMM_BASE_PATH: str = os.environ.get('ROMM_BASE_PATH', '/romm')
LIBRARY_BASE_PATH: str = f"{ROMM_BASE_PATH}/library"
ROMM_USER_CONFIG_PATH: str = f"{ROMM_BASE_PATH}/config.yml"
SQLITE_DB_BASE_PATH: str = f"{ROMM_BASE_PATH}/database"
RESOURCES_BASE_PATH: str = f"{ROMM_BASE_PATH}/resources"
HIGH_PRIO_STRUCTURE_PATH: str = f"{LIBRARY_BASE_PATH}/roms"

# DEFAULT RESOURCES
DEFAULT_URL_COVER_L: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_PATH_COVER_L: str = f"default/default/cover/big.png"
DEFAULT_URL_COVER_S: str = "https://images.igdb.com/igdb/image/upload/t_cover_small/nocover.png"
DEFAULT_PATH_COVER_S: str = f"default/default/cover/small.png"

# IGDB
CLIENT_ID: str = os.environ.get('CLIENT_ID')
CLIENT_SECRET: str = os.environ.get('CLIENT_SECRET')
# STEAMGRIDDB
STEAMGRIDDB_API_KEY: str = os.environ.get('STEAMGRIDDB_API_KEY')

# DB DRIVERS
SUPPORTED_DB_DRIVERS: list = ['sqlite', 'mariadb']
ROMM_DB_DRIVER: str = os.environ.get('ROMM_DB_DRIVER', 'sqlite')
