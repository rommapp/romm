import os

# Image formats every modern browser can decode. Shared by the per-ROM
# (endpoints/roms/screenshot.py) and per-user (endpoints/screenshots.py)
# screenshot upload endpoints.
ALLOWED_SCREENSHOT_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
)


def is_allowed_screenshot_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_SCREENSHOT_EXTENSIONS
