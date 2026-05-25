from mimetypes import guess_type
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import SAFE_IMAGE_MIME_TYPES
from utils.router import APIRouter

router = APIRouter(
    prefix="/raw",
    tags=["raw"],
)


def _build_asset_response(resolved_path: Path) -> FileResponse:
    guessed_type, _ = guess_type(resolved_path.name)
    if guessed_type in SAFE_IMAGE_MIME_TYPES:
        return FileResponse(
            path=str(resolved_path),
            filename=resolved_path.name,
            media_type=guessed_type,
            content_disposition_type="inline",
        )

    return FileResponse(
        path=str(resolved_path),
        filename=resolved_path.name,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )


@protected_route(router.head, "/assets/{path:path}", [Scope.ASSETS_READ])
def head_raw_asset(request: Request, path: str):
    try:
        resolved_path = fs_asset_handler.validate_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc

    # Check if file exists and is a file (not directory)
    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    return _build_asset_response(resolved_path)


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
        raise HTTPException(status_code=404, detail="Asset not found")

    return _build_asset_response(resolved_path)
