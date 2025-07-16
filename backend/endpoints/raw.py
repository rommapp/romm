from pathlib import Path
from typing import Optional

from config import ASSETS_BASE_PATH
from decorators.auth import protected_route
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from handler.auth.constants import Scope
from utils.router import APIRouter

router = APIRouter(
    prefix="/raw",
    tags=["raw"],
)


def validate_and_resolve_path(path: str) -> Optional[Path]:
    try:
        base_path = Path(ASSETS_BASE_PATH).resolve()
        requested_path = (base_path / path).resolve()

        # Ensure the resolved path is within the base directory
        if not str(requested_path).startswith(str(base_path)):
            return None

        # Check if file exists and is a file (not directory)
        if not requested_path.exists() or not requested_path.is_file():
            return None

        return requested_path
    except (ValueError, OSError):
        return None


@protected_route(router.head, "/assets/{path:path}", [Scope.ASSETS_READ])
def head_raw_asset(request: Request, path: str):
    resolved_path = validate_and_resolve_path(path)

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Asset not found")

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
    resolved_path = validate_and_resolve_path(path)

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(path=str(resolved_path), filename=resolved_path.name)
