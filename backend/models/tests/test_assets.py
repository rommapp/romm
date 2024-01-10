from config import FRONTEND_LIBRARY_PATH

def test_save(save):
    assert save.full_path == "test_platform_slug/saves/test_emulator/test_save.sav"
    assert save.download_path == f"{FRONTEND_LIBRARY_PATH}/test_platform_slug/saves/test_emulator/test_save.sav"

def test_state(state):
    assert state.full_path == "test_platform_slug/states/test_emulator/test_state.state"
    assert state.download_path == f"{FRONTEND_LIBRARY_PATH}/test_platform_slug/states/test_emulator/test_state.state"

def test_screenshot(screenshot):
    assert screenshot.full_path == "test_platform_slug/screenshots/test_screenshot.png"
    assert screenshot.download_path == f"{FRONTEND_LIBRARY_PATH}/test_platform_slug/screenshots/test_screenshot.png"
