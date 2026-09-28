from fastapi import HTTPException, UploadFile, status

from config import MAX_ASSET_UPLOAD_SIZE_BYTES
from utils.filesystem import sanitize_filename


def check_asset_upload_size(file: UploadFile | None, label: str) -> None:
    """Reject an asset upload whose parsed size exceeds the configured ceiling.

    Backstop for `UploadSizeLimitMiddleware`, which rejects on Content-Length
    before the body is spooled. This catches requests that arrive without a
    declared length (chunked transfer encoding).
    """
    if file is None or not MAX_ASSET_UPLOAD_SIZE_BYTES:
        return

    if file.size is not None and file.size > MAX_ASSET_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"{label} exceeds the maximum allowed size of "
                f"{MAX_ASSET_UPLOAD_SIZE_BYTES} bytes"
            ),
        )


def check_emulator_folder_name(emulator: str | None) -> None:
    """Reject an asset's emulator unless it is usable verbatim as one folder name."""
    if not emulator:
        return

    try:
        is_segment = sanitize_filename(emulator) == emulator
    except ValueError:
        is_segment = False

    if not is_segment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid emulator name: {emulator}",
        )
