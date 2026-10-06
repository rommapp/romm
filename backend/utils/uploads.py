import os
import re
from datetime import datetime

from fastapi import HTTPException, status
from starlette.datastructures import UploadFile

from config import MAX_ASSET_UPLOAD_SIZE_BYTES
from utils.filesystem import check_filename_length, sanitize_filename

# Matches tags written before milliseconds were added, too.
DATETIME_TAG_PATTERN = re.compile(
    r" \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d{3})?\]"
)


def apply_datetime_tag(filename: str) -> str:
    """`filename` with its datetime tag replaced by the server's local time now."""
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
    return f"{DATETIME_TAG_PATTERN.sub('', name)} [{timestamp}]{ext}"


def sanitize_asset_filename(filename: str, label: str) -> str:
    """`filename` made safe to write, or a 400 naming the `label` upload, so a
    caller can reject a bad name before it stores anything."""
    try:
        sanitized = sanitize_filename(filename)
        check_filename_length(sanitized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label} filename: {exc}",
        ) from exc
    return sanitized


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
