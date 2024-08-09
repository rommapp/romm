from config import ASSETS_BASE_PATH
from decorators.auth import protected_route
from fastapi import Request
from fastapi.responses import FileResponse
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.head, "/raw/assets/{path:path}", ["assets.read"])
def head_raw_asset(request: Request, path: str):
    asset_path = f"{ASSETS_BASE_PATH}/{path}"
    return FileResponse(path=asset_path, filename=path.split("/")[-1])


@protected_route(router.get, "/raw/assets/{path:path}", ["assets.read"])
def get_raw_asset(request: Request, path: str):
    """Download a single asset file

    Args:
        request (Request): Fastapi Request object

    Returns:
        FileResponse: Returns a single asset file
    """

    asset_path = f"{ASSETS_BASE_PATH}/{path}"
    return FileResponse(path=asset_path, filename=path.split("/")[-1])
