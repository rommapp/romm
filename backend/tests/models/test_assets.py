from models.assets import Save, Screenshot, State


def test_save(save: Save):
    assert "test_platform_slug/saves/test_emulator/test_save.sav" in save.full_path
    assert (
        "/api/raw/assets/test_platform_slug/saves/test_emulator/test_save.sav"
        in save.download_path
    )


def test_state(state: State):
    assert "test_platform_slug/states/test_emulator/test_state.state" in state.full_path
    assert (
        "/api/raw/assets/test_platform_slug/states/test_emulator/test_state.state"
        in state.download_path
    )


def test_screenshot(screenshot: Screenshot):
    assert "test_platform_slug/screenshots/test_screenshot.png" in screenshot.full_path
    assert (
        "/api/raw/assets/test_platform_slug/screenshots/test_screenshot.png"
        in screenshot.download_path
    )
