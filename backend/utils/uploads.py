from fastapi import HTTPException, UploadFile, status

from config import MAX_ASSET_UPLOAD_SIZE_BYTES


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
