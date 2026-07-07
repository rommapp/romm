from __future__ import annotations

import mimetypes
import os

# File extensions that are safe to serve inline (rendered/streamed by the
# browser) from the ROM download endpoint. Images and videos never execute
# scripts, so serving them inline under an explicit, trusted Content-Type
# avoids the content-sniffing/XSS risk that keeps arbitrary files served as
# attachments.
ALLOWED_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
)
ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".ogv", ".mov", ".m4v"})

# MIME types the stdlib mimetypes module guesses inconsistently (or not at
# all) across platforms.
MEDIA_MIME_OVERRIDES = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".ogv": "video/ogg",
    ".mov": "video/quicktime",
}


def is_inline_media_file(file_name: str) -> bool:
    """Whether a library file is an image/video the browser can render inline."""
    ext = os.path.splitext(file_name)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS or ext in ALLOWED_VIDEO_EXTENSIONS


def guess_media_file_type(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if ext in MEDIA_MIME_OVERRIDES:
        return MEDIA_MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"
