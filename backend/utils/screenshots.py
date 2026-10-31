from collections.abc import Sequence

from config import FRONTEND_RESOURCES_PATH
from models.assets import Save
from models.rom import Rom

TITLE_SCREEN_PIN_KEY = "artwork:title_screen"
SCRAPED_PIN_PREFIX = "scraped:"


def _title_screen(rom: Rom) -> str | None:
    title_screen = (rom.ss_metadata or {}).get("title_screen_path") or (
        rom.gamelist_metadata or {}
    ).get("title_screen_path")
    return f"{FRONTEND_RESOURCES_PATH}/{title_screen}" if title_screen else None


def _pinned_image(rom: Rom, pinned_media: Sequence[str]) -> str | None:
    """The first pinned title screen or scraped screenshot that still exists."""
    screenshots = rom.merged_screenshots
    for key in pinned_media:
        if key == TITLE_SCREEN_PIN_KEY:
            if title_screen := _title_screen(rom):
                return title_screen
        elif key.startswith(SCRAPED_PIN_PREFIX):
            url = key.removeprefix(SCRAPED_PIN_PREFIX)
            if url in screenshots:
                return url
    return None


def continue_playing_screenshot(
    rom: Rom, latest_save: Save | None, pinned_media: Sequence[str] | None = None
) -> str | None:
    """The "where you left off" image for a rom, in priority order: the latest
    save's screenshot, the user's first pinned title screen or screenshot, the
    title screen, then the first gameplay screenshot. None lets the frontend
    fall back to cover art. Shared by the continue-playing rail and the
    live-activity board."""
    if latest_save is not None and latest_save.screenshot is not None:
        return latest_save.screenshot.download_path

    if pinned_media and (pinned := _pinned_image(rom, pinned_media)):
        return pinned

    if title_screen := _title_screen(rom):
        return title_screen

    if rom.merged_screenshots:
        return rom.merged_screenshots[0]

    return None
