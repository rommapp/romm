import json
import os
from datetime import UTC, datetime
from typing import Any, Literal, NotRequired, TypedDict

from handler.redis_handler import async_cache
from models.platform import Platform
from utils.arcade_platforms import MAME_SHORTNAME_PLATFORMS

from .base_handler import MAME_XML_KEY, BaseRom, MetadataHandler
from .mame_index import MameMachine, get_index_info, get_machine

MameSetType = Literal["parent", "clone", "bios", "device"]


class MameMetadata(TypedDict):
    set_name: str
    set_type: MameSetType
    cloneof: NotRequired[str]
    romof: NotRequired[str]
    is_mechanical: NotRequired[bool]
    status: NotRequired[str]
    sourcefile: NotRequired[str]
    players: NotRequired[int]
    first_release_date: NotRequired[int]
    year: NotRequired[str]
    companies: NotRequired[list[str]]
    genres: NotRequired[list[str]]
    mame_build: NotRequired[str]


class MameRom(BaseRom):
    mame_id: str | None
    mame_metadata: NotRequired[MameMetadata]


def set_name_of(fs_name: str) -> str:
    """The set's short name: the file name without its extension, lowercased."""
    name, ext = os.path.splitext(fs_name)
    return (name if ext else fs_name).strip().lower()


def year_epoch(year: str | None) -> int | None:
    """January 1st of a 4-digit year, in epoch seconds; MAME writes unknown digits as '?'."""
    if not year or len(year) != 4 or not year.isdigit():
        return None
    return int(datetime(int(year), 1, 1, tzinfo=UTC).timestamp())


def set_type_of(machine: MameMachine) -> MameSetType:
    if machine["is_bios"]:
        return "bios"
    if machine["is_device"]:
        return "device"
    return "clone" if machine["cloneof"] else "parent"


async def _fixture_entry(set_name: str) -> dict[str, Any] | None:
    raw = await async_cache.hget(MAME_XML_KEY, set_name)
    return json.loads(raw) if raw else None


def _from_fixture(set_name: str, entry: dict[str, Any]) -> MameMachine:
    """A bundled-index entry in the loaded index's shape; it has no flags or driver."""
    return MameMachine(
        name=set_name,
        description=entry.get("description") or set_name,
        year=entry.get("year"),
        manufacturer=entry.get("manufacturer"),
        cloneof=entry.get("cloneof"),
        romof=None,
        sourcefile=None,
        is_bios=False,
        is_device=False,
        is_mechanical=False,
        runnable=True,
        status=None,
        players=None,
    )


class MameHandler(MetadataHandler):
    """MAME's own data for arcade sets, from the loaded listxml or the bundled index."""

    @classmethod
    def is_enabled(cls) -> bool:
        # The bundled index is always there, so the source always works.
        return True

    async def heartbeat(self) -> bool:
        return True

    async def get_rom(self, fs_name: str, platform: Platform) -> MameRom:
        if platform.slug not in MAME_SHORTNAME_PLATFORMS:
            return MameRom(mame_id=None)

        set_name = set_name_of(fs_name)
        fixture = await _fixture_entry(set_name)
        machine = await get_machine(set_name)
        if machine is None:
            if fixture is None:
                return MameRom(mame_id=None)
            machine = _from_fixture(set_name, fixture)
        from_listxml = machine["sourcefile"] is not None

        set_type = set_type_of(machine)
        metadata = MameMetadata(set_name=set_name, set_type=set_type)
        if machine["cloneof"]:
            metadata["cloneof"] = machine["cloneof"]
        if machine["romof"]:
            metadata["romof"] = machine["romof"]
        if from_listxml:
            metadata["is_mechanical"] = machine["is_mechanical"]
            info = await get_index_info()
            if info:
                metadata["mame_build"] = info["build"]
        if machine["status"]:
            metadata["status"] = machine["status"]
        if machine["sourcefile"]:
            metadata["sourcefile"] = machine["sourcefile"]
        if machine["players"] is not None:
            metadata["players"] = machine["players"]
        if machine["year"]:
            metadata["year"] = machine["year"]
        if (release := year_epoch(machine["year"])) is not None:
            metadata["first_release_date"] = release
        if machine["manufacturer"]:
            metadata["companies"] = [machine["manufacturer"]]
        # The listxml has no genre; the bundled index carries one for most sets.
        if fixture and fixture.get("genre"):
            metadata["genres"] = [fixture["genre"]]

        # Clones share their parent's id, which groups them as its versions.
        group = machine["cloneof"] if set_type == "clone" else set_name
        return MameRom(
            mame_id=group,
            name=machine["description"],
            mame_metadata=metadata,
        )
