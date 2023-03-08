import os
import pathlib


# PATHS
DEFAULT_IMAGE_URL: str = "https://images.igdb.com/igdb/image/upload/t_cover_med/nocover.png"
EMULATION_BASE_PATH: str = f"{pathlib.Path(__file__).parent.parent.parent.parent.resolve()}/emulation"

DEFAULT_IMAGE_PATH: str = f"{EMULATION_BASE_PATH}/defaults/resources/logo.png"

# IGDB
CLIENT_ID=os.getenv('CLIENT_ID')
CLIENT_SECRET=os.getenv('CLIENT_SECRET')
# STEAMGRIDDB
STEAMGRIDDB_API_KEY=os.getenv('STEAMGRIDDB_API_KEY')

# DB
DB_HOST=os.getenv('DB_HOST')
DB_PORT=int(os.getenv('DB_PORT'))
DB_ROOT_PASSWD=os.getenv('DB_ROOT_PASSWD')
DB_USER=os.getenv('DB_USER')
DB_PASSWD=os.getenv('DB_PASSWD')