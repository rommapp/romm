from __future__ import annotations

import mimetypes
import os
from typing import Final

# File extensions that are safe to serve inline (rendered/streamed by the
# browser) from the ROM download endpoint. Images and videos never execute
# scripts, so serving them inline under an explicit, trusted Content-Type
# avoids the content-sniffing/XSS risk that keeps arbitrary files served as
# attachments. Manuals (PDF/Markdown) are served inline too so the in-page
# manual viewer can render them; the browser renders PDFs in a sandboxed
# viewer and Markdown is served as text/markdown (never sniffed to HTML).
ALLOWED_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tiff", ".tif", ".bmp", ".avif"}
)
ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".ogv", ".mov", ".m4v"})
ALLOWED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".md"})

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
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}

# Image MIME types we trust to (a) accept as avatar uploads and (b) serve
# inline from the raw asset endpoint. Maps each trusted MIME type to its
# canonical file extension.
IMAGE_EXT_BY_MIME_TYPE: Final[dict[str, str]] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def is_allowed_image_file(file_name: str) -> bool:
    """Whether a library file is an image the browser can render inline."""
    ext = os.path.splitext(file_name)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def is_allowed_video_file(file_name: str) -> bool:
    """Whether a library file is a video the browser can render inline."""
    ext = os.path.splitext(file_name)[1].lower()
    return ext in ALLOWED_VIDEO_EXTENSIONS


def is_allowed_document_file(file_name: str) -> bool:
    """Whether a library file is a manual document the browser can render inline."""
    ext = os.path.splitext(file_name)[1].lower()
    return ext in ALLOWED_DOCUMENT_EXTENSIONS


def is_allowed_media_file(file_name: str) -> bool:
    """Whether a library file is an image/video the browser can render inline."""
    return is_allowed_image_file(file_name) or is_allowed_video_file(file_name)


def guess_media_file_type(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if ext in MEDIA_MIME_OVERRIDES:
        return MEDIA_MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"
