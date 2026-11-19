from unittest.mock import AsyncMock, patch

import pytest
from tests.factories import make_platform, make_rom

from handler.database import db_rom_handler
from handler.metadata.mame_handler import MameMetadata, MameRom
from models.rom import Rom
from tasks.manual.match_mame_platform import match_mame_platform_task

SF2CE = MameRom(
    mame_id="sf2ce",
    name="Street Fighter II': Champion Edition (Etc 920313)",
    mame_metadata=MameMetadata(set_name="sf2ceea", set_type="clone", cloneof="sf2ce"),
)


def _stored(rom_id: int) -> Rom:
    rom = db_rom_handler.get_rom(rom_id)
    assert rom is not None
    return rom


async def _by_set_name(fs_name: str) -> MameRom:
    return SF2CE if fs_name.startswith("sf2ce") else MameRom(mame_id=None)


@pytest.fixture
def match_machine():
    with patch(
        "tasks.manual.match_mame_platform.meta_mame_handler.match_machine",
        AsyncMock(side_effect=_by_set_name),
    ) as mocked:
        yield mocked


async def test_matches_and_renames_unless_locked(match_machine):
    platform = make_platform("arcade")
    clone = make_rom(platform, "sf2ceea")
    locked = make_rom(
        platform, "My name", fs_stem="sf2cejc", locked_fields=["name"]
    )
    other = make_rom(platform, "unknown")

    result = await match_mame_platform_task.run(platform.id)

    assert result == {"games": 3, "changed": 2}
    stored = _stored(clone.id)
    assert stored.mame_id == "sf2ce"
    assert stored.name == SF2CE["name"]
    assert (stored.mame_metadata or {})["set_type"] == "clone"
    assert _stored(locked.id).name == "My name"
    assert _stored(locked.id).mame_id == "sf2ce"
    assert _stored(other.id).mame_id is None


async def test_rename_off_keeps_names(match_machine):
    platform = make_platform("arcade")
    clone = make_rom(platform, "sf2ceea")

    await match_mame_platform_task.run(platform.id, rename=False)

    assert _stored(clone.id).name == "sf2ceea"


async def test_clear_drops_mame_data():
    platform = make_platform("arcade")
    matched = make_rom(
        platform, "sf2ceea", mame_id="sf2ce", mame_metadata={"set_name": "sf2ceea"}
    )

    result = await match_mame_platform_task.run(platform.id, action="clear")

    assert result["changed"] == 1
    stored = _stored(matched.id)
    assert stored.mame_id is None
    assert not stored.mame_metadata


async def test_refuses_other_platforms():
    platform = make_platform("snes")
    with pytest.raises(ValueError, match="not an arcade platform"):
        await match_mame_platform_task.run(platform.id)
