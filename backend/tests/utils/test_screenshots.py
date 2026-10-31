from types import SimpleNamespace
from typing import Any

from config import FRONTEND_RESOURCES_PATH
from models.assets import Save
from models.rom import Rom
from utils.screenshots import continue_playing_screenshot

TITLE = "roms/1/1/title_screen/title_screen.png"
SHOTS = ["roms/1/1/screenshots/0.jpg", "roms/1/1/screenshots/1.jpg"]
TITLE_URL = f"{FRONTEND_RESOURCES_PATH}/{TITLE}"
SHOT_URLS = [f"{FRONTEND_RESOURCES_PATH}/{s}" for s in SHOTS]


def _rom(**kwargs: Any) -> Rom:
    return Rom(
        ss_metadata={"title_screen_path": TITLE}, path_screenshots=SHOTS, **kwargs
    )


def _save_with_screenshot() -> Save:
    return SimpleNamespace(  # type: ignore[return-value]
        screenshot=SimpleNamespace(download_path="/saves/shot.png")
    )


def test_defaults_to_the_title_screen():
    assert continue_playing_screenshot(_rom(), None) == TITLE_URL


def test_falls_back_to_the_first_screenshot():
    rom = Rom(path_screenshots=SHOTS)
    assert continue_playing_screenshot(rom, None) == SHOT_URLS[0]


def test_latest_save_screenshot_beats_a_pin():
    pinned = [f"scraped:{SHOT_URLS[1]}"]
    assert (
        continue_playing_screenshot(_rom(), _save_with_screenshot(), pinned)
        == "/saves/shot.png"
    )


def test_a_pinned_screenshot_beats_the_title_screen():
    pinned = [f"scraped:{SHOT_URLS[1]}"]
    assert continue_playing_screenshot(_rom(), None, pinned) == SHOT_URLS[1]


def test_the_first_usable_pin_wins():
    pinned = [
        "file:12",
        f"scraped:{FRONTEND_RESOURCES_PATH}/gone.jpg",
        f"scraped:{SHOT_URLS[1]}",
        "artwork:title_screen",
    ]
    assert continue_playing_screenshot(_rom(), None, pinned) == SHOT_URLS[1]


def test_a_pinned_title_screen_beats_a_later_pinned_screenshot():
    pinned = ["artwork:title_screen", f"scraped:{SHOT_URLS[0]}"]
    assert continue_playing_screenshot(_rom(), None, pinned) == TITLE_URL


def test_unusable_pins_fall_back_to_the_default_order():
    pinned = ["artwork:logo", "screenshot:3"]
    assert continue_playing_screenshot(_rom(), None, pinned) == TITLE_URL
