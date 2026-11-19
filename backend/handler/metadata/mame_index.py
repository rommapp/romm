"""The MAME machine index an admin loads from a `mame -listxml` file.

It holds what the XML says about every set, by short name, and replaces the
bundled `mame_index.json` fixture wherever a set's title is looked up.
"""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import IO, Any, Final, NotRequired, TypedDict, cast

from defusedxml import ElementTree as ET

from handler.dump_cache import decode, encode
from handler.redis_handler import async_binary_cache, async_cache
from utils.cache import VersionedCacheStore, is_cache_store_ready

MAME_INDEX_KEY: Final = "romm:mame_index"
MAME_INDEX_INFO_KEY: Final = "romm:mame_index_info"
# An import fills this key, then renames it over the live one in one step.
MAME_INDEX_STAGING_KEY: Final = "romm:mame_index_staging"
MAME_INDEX_STORE: Final = VersionedCacheStore(
    schema_key="romm:mame_index_schema",
    version=1,
    keys=(MAME_INDEX_KEY, MAME_INDEX_INFO_KEY),
)

# The release asset holding the XML, like `mame0289lx.zip`.
MAME_LISTXML_ASSET_RE: Final = re.compile(r"^mame(\d+)lx\.zip$", re.IGNORECASE)
MAME_LATEST_RELEASE_API: Final = (
    "https://api.github.com/repos/mamedev/mame/releases/latest"
)

WRITE_BATCH_SIZE: Final = 2000


class MameMachine(TypedDict):
    """One set as the index stores it."""

    name: str
    description: str
    year: str | None
    manufacturer: str | None
    cloneof: str | None
    romof: str | None
    sourcefile: str | None
    is_bios: bool
    is_device: bool
    is_mechanical: bool
    runnable: bool
    status: str | None
    players: int | None


class MameIndexInfo(TypedDict):
    build: str
    sets: int
    source: str
    updated_at: str
    error: NotRequired[str]


def _flag(elem: Any, attr: str) -> bool:
    return bool(elem.get(attr) == "yes")


def _text(elem: Any, tag: str) -> str | None:
    child = elem.find(tag)
    text = child.text.strip() if child is not None and child.text else ""
    return text or None


def _players(elem: Any) -> int | None:
    node = elem.find("input")
    try:
        return int(node.get("players")) if node is not None else None
    except (TypeError, ValueError):
        return None


def machine_from_element(elem: Any) -> MameMachine:
    """A `<machine>` (or pre-0.162 `<game>`) element as an index entry."""
    driver = elem.find("driver")
    return MameMachine(
        name=elem.get("name", ""),
        description=_text(elem, "description") or elem.get("name", ""),
        year=_text(elem, "year"),
        manufacturer=_text(elem, "manufacturer"),
        cloneof=elem.get("cloneof"),
        romof=elem.get("romof"),
        sourcefile=elem.get("sourcefile"),
        is_bios=_flag(elem, "isbios"),
        is_device=_flag(elem, "isdevice"),
        is_mechanical=_flag(elem, "ismechanical"),
        runnable=elem.get("runnable", "yes") != "no",
        status=driver.get("status") if driver is not None else None,
        players=_players(elem),
    )


def iter_listxml(source: IO[bytes]) -> Iterator[tuple[str, MameMachine]]:
    """Yield (build, machine) for each set of a listxml, without holding the document.

    `build` is the root's version string, like "0.289 (mame0289)".
    """
    ctx = ET.iterparse(source, events=("start", "end"))
    try:
        _, root = next(iter(ctx))
    except StopIteration:
        return
    build = root.get("build", "")

    depth = 0
    for event, elem in ctx:
        if event == "start":
            depth += 1
            continue
        depth -= 1
        if depth > 0:
            continue
        if elem.tag in ("machine", "game") and elem.get("name"):
            yield build, machine_from_element(elem)
        # iterparse keeps every parsed element on the root otherwise.
        root.clear()


async def write_index(
    machines: Iterator[tuple[str, MameMachine]],
    *,
    source: str,
    on_progress: Any = None,
) -> MameIndexInfo:
    """Fill the index from parsed sets, replacing the live one only once complete.

    Args:
        source: Where the XML came from, shown to admins.
        on_progress: Called with the count written so far, every batch.
    """
    await async_binary_cache.unlink(MAME_INDEX_STAGING_KEY)
    build = ""
    count = 0
    # Any-keyed: redis-py's mapping type is invariant in its keys.
    batch: dict[Any, bytes] = {}
    for build, machine in machines:
        batch[machine["name"].lower()] = encode(machine)
        if len(batch) >= WRITE_BATCH_SIZE:
            await async_binary_cache.hset(MAME_INDEX_STAGING_KEY, mapping=batch)
            count += len(batch)
            batch = {}
            if on_progress:
                on_progress(count)
    if batch:
        await async_binary_cache.hset(MAME_INDEX_STAGING_KEY, mapping=batch)
        count += len(batch)

    if not count:
        raise ValueError("The file holds no MAME sets: is it a `mame -listxml` file?")

    await async_binary_cache.rename(MAME_INDEX_STAGING_KEY, MAME_INDEX_KEY)
    info = MameIndexInfo(
        build=build,
        sets=count,
        source=source,
        updated_at=datetime.now(UTC).isoformat(),
    )
    await async_cache.set(MAME_INDEX_INFO_KEY, json.dumps(info))
    await async_cache.set(MAME_INDEX_STORE.schema_key, str(MAME_INDEX_STORE.version))
    return info


async def is_index_loaded() -> bool:
    return await is_cache_store_ready(async_cache, MAME_INDEX_STORE, MAME_INDEX_KEY)


async def get_index_info() -> MameIndexInfo | None:
    raw = await async_cache.get(MAME_INDEX_INFO_KEY)
    if not raw or not await is_index_loaded():
        return None
    return cast(MameIndexInfo, json.loads(raw))


async def get_machine(name: str) -> MameMachine | None:
    """A set from the loaded index, or None when it is absent or none is loaded."""
    if not name:
        return None
    raw = await async_binary_cache.hget(MAME_INDEX_KEY, name.lower())
    return decode(raw) if raw else None
