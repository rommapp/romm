import os

from config import FRONTEND_RESOURCES_PATH
from models.assets import Save
from models.rom import Rom

# Image formats every modern browser can decode. Shared by the per-ROM
# (endpoints/roms/screenshot.py) and per-user (endpoints/screenshots.py)
# screenshot upload endpoints.
ALLOWED_SCREENSHOT_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
)


def is_allowed_screenshot_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext.lower() in ALLOWED_SCREENSHOT_EXTENSIONS


def continue_playing_screenshot(rom: Rom, latest_save: Save | None) -> str | None:
    """The "where you left off" image for a rom, in priority order: the latest
    save's screenshot, then the title screen, then the first gameplay
    screenshot. None lets the frontend fall back to cover art. Shared by the
    continue-playing rail and the live-activity board."""
    if latest_save is not None and latest_save.screenshot is not None:
        return latest_save.screenshot.download_path

    title_screen = (rom.ss_metadata or {}).get("title_screen_path") or (
        rom.gamelist_metadata or {}
    ).get("title_screen_path")
    if title_screen:
        return f"{FRONTEND_RESOURCES_PATH}/{title_screen}"

    if rom.merged_screenshots:
        return rom.merged_screenshots[0]

    return None
