from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.filesystem import fs_asset_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/raw",
    tags=["raw"],
)


@protected_route(router.head, "/assets/{path:path}", [Scope.ASSETS_READ])
def head_raw_asset(request: Request, path: str):
    try:
        resolved_path = fs_asset_handler.validate_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc

    # Check if file exists and is a file (not directory)
    if not resolved_path.exists() or not resolved_path.is_file():
        return HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(path=str(resolved_path), filename=resolved_path.name)


@protected_route(router.get, "/assets/{path:path}", [Scope.ASSETS_READ])
def get_raw_asset(request: Request, path: str):
    """Download a single asset file

    Args:
        request (Request): Fastapi Request object
        path (str): Relative path to the asset file

    Returns:
        FileResponse: Returns a single asset file

    Raises:
        HTTPException: 404 if asset not found or access denied
    """
    try:
        resolved_path = fs_asset_handler.validate_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc

    # Check if file exists and is a file (not directory)
    if not resolved_path.exists() or not resolved_path.is_file():
        return HTTPException(status_code=404, detail="Asset not found")

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(path=str(resolved_path), filename=resolved_path.name)
