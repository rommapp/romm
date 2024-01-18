from models import Save, State, Screenshot

def test_save(save: Save):
    assert save.full_path == "test_platform_slug/saves/test_emulator/test_save.sav"
    assert save.download_path == "/api/raw/test_platform_slug/saves/test_emulator/test_save.sav"

def test_state(state: State):
    assert state.full_path == "test_platform_slug/states/test_emulator/test_state.state"
    assert state.download_path == "/api/raw/test_platform_slug/states/test_emulator/test_state.state"

def test_screenshot(screenshot: Screenshot):
    assert screenshot.full_path == "test_platform_slug/screenshots/test_screenshot.png"
    assert screenshot.download_path == "/api/raw/test_platform_slug/screenshots/test_screenshot.png"
