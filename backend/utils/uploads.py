import os
import re
from datetime import datetime

from fastapi import HTTPException, status
from starlette.datastructures import UploadFile

from config import MAX_ASSET_UPLOAD_SIZE_BYTES
from utils.filesystem import check_filename_length, sanitize_filename

# Milliseconds are optional: files already on disk carry tags without them.
DATETIME_TAG_PATTERN = re.compile(
    r" \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d{3})?\]"
)


def _untagged_parts(filename: str) -> tuple[str, str]:
    name, ext = os.path.splitext(filename)
    return DATETIME_TAG_PATTERN.sub("", name), ext


def strip_datetime_tag(filename: str) -> str:
    """`filename` without the datetime tag `apply_datetime_tag` gave it."""
    name, ext = _untagged_parts(filename)
    return f"{name}{ext}"


def apply_datetime_tag(filename: str, at: datetime | None = None) -> str:
    """`filename` with its datetime tag replaced by `at`, the server's local time now by default."""
    name, ext = _untagged_parts(filename)
    timestamp = (at or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
    return f"{name} [{timestamp}]{ext}"


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


def is_emulator_folder_name(emulator: str) -> bool:
    """Whether `emulator` is usable verbatim as one folder name."""
    try:
        return sanitize_filename(emulator) == emulator
    except ValueError:
        return False


def check_emulator_folder_name(emulator: str | None) -> None:
    """Reject an asset's emulator unless it is usable verbatim as one folder name."""
    if not emulator:
        return

    if not is_emulator_folder_name(emulator):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid emulator name: {emulator}",
        )
