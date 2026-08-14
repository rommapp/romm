from models.assets import Save, Screenshot, State


def test_save(save: Save):
    assert "test_platform_slug/saves/test_emulator/test_save.sav" in save.full_path
    assert save.download_path.startswith(f"/api/saves/{save.id}/content")


def test_state(state: State):
    assert "test_platform_slug/states/test_emulator/test_state.state" in state.full_path
    assert state.download_path.startswith(f"/api/states/{state.id}/content")


def test_screenshot(screenshot: Screenshot):
    assert "test_platform_slug/screenshots/test_screenshot.png" in screenshot.full_path
    assert screenshot.download_path.startswith(
        f"/api/screenshots/{screenshot.id}/content"
    )
