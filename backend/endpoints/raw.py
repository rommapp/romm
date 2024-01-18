from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from decorators.auth import protected_route
from config import LIBRARY_BASE_PATH

router = APIRouter()


@protected_route(router.get, "/raw/{path:path}", ["assets.read"])
def get_raw_asset(request: Request, path: str):
    """Download a single asset file

    Args:
        request (Request): Fastapi Request object

    Returns:
        FileResponse: Returns a single asset file
    """

    asset_path = f"{LIBRARY_BASE_PATH}/{path}"

    return FileResponse(path=asset_path, filename=path.split("/")[-1])
