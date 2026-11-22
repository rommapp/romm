from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from handler.database import db_rom_handler, db_state_handler
from models.assets import MemoryCardVersion, Save, Screenshot, State
from models.rom import Rom

UPDATED_AT = datetime(2026, 11, 19, 18, 30, 59, 331000, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "asset",
    [
        Save(id=1, file_name="Game (USA) [2026-11-19].srm", updated_at=UPDATED_AT),
        State(id=2, file_name="Game (USA).state", updated_at=UPDATED_AT),
        Screenshot(id=3, file_name="Game (USA).png", updated_at=UPDATED_AT),
        MemoryCardVersion(id=4, file_name="card.zip", updated_at=UPDATED_AT),
    ],
    ids=lambda asset: type(asset).__name__,
)
def test_download_path_query_round_trips_the_timestamp(asset):
    url = asset.download_path

    assert " " not in url
    assert "+" not in url
    assert parse_qs(urlsplit(url).query)["timestamp"] == [str(UPDATED_AT)]


def test_download_path_round_trips_the_file_name():
    save = Save(id=1, file_name="Game (USA) [2026-11-19].srm", updated_at=UPDATED_AT)

    query = parse_qs(urlsplit(save.download_path).query)

    assert query["name"] == ["Game (USA) [2026-11-19].srm"]


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


def test_a_state_defaults_to_no_disc(state: State):
    """A single-disc game records nothing, so the column stays empty."""
    assert state.disc_file_id is None


def test_losing_the_disc_file_does_not_take_the_state_with_it(
    state: State, multi_file_rom: Rom
):
    """A rescan that drops a file row must cost the state its disc hint, not the
    save itself, so the column is SET NULL rather than CASCADE."""
    disc = multi_file_rom.files[1]
    db_state_handler.update_state(state.id, {"disc_file_id": disc.id})

    db_rom_handler.delete_rom_file(disc.id)

    survivor = db_state_handler.get_state_by_id(state.id)
    assert survivor is not None
    assert survivor.disc_file_id is None
