from config import FRONTEND_RESOURCES_PATH
from models.assets import Save
from models.rom import Rom


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
