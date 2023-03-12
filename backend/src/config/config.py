import os
import pathlib

# Uvicorn
PORT: int = 5000
HOST: str = "0.0.0.0"

# PATHS
EMULATION_BASE_PATH: str = f"{pathlib.Path(__file__).parent.parent.parent.parent.resolve()}/emulation"

DEFAULT_LOGO_URL: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_LOGO_PATH: str = f"/assets/emulation/resources/default/logo_big.png"

DEFAULT_COVER_URL_BIG: str = "https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png"
DEFAULT_COVER_PATH_BIG: str = f"/assets/emulation/resources/default/cover_big.png"
DEFAULT_COVER_URL_SMALL: str = "https://images.igdb.com/igdb/image/upload/t_cover_small/nocover.png"
DEFAULT_COVER_PATH_SMALL: str = f"/assets/emulation/resources/default/cover_small.png"


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