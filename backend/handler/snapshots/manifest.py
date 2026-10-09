import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Final, Literal

from models.assets import SaveFormat, SaveShape


class Carry(Enum):
    """A manifest field left out, so the snapshot takes its parent's value."""

    PARENT = "parent"


CARRY: Final = Carry.PARENT

Bank = dict[str, dict[str, str]]


@dataclass(frozen=True)
class SaveEntry:
    hash: str
    shape: SaveShape | None
    format: SaveFormat | None


@dataclass(frozen=True)
class Manifest:
    """What a push declares. Entries are content hashes, never file names."""

    save: SaveEntry | None | Literal[Carry.PARENT] = CARRY
    # A listed core replaces the parent's; a slot left out of it is deleted.
    states: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    is_hardcore: bool = False
    approve_hardcore_downgrade: bool = False
    emulator: str | None = None
    emulator_version: str | None = None
    # The libretro core the push ran, which names the states bank's matching core.
    core: str | None = None
    core_version: str | None = None


@dataclass(frozen=True)
class Resolved:
    """A snapshot's content after carried entries are filled from its parent."""

    save: SaveEntry | None
    bank: Bank

    @property
    def digest(self) -> str:
        return snapshot_digest(self.save, self.bank)


def resolve(manifest: Manifest, parent: Resolved | None) -> Resolved:
    """Fill what `manifest` leaves out from `parent`. A hardcore snapshot holds no states."""
    if isinstance(manifest.save, Carry):
        save = parent.save if parent else None
    else:
        save = manifest.save

    if manifest.is_hardcore:
        return Resolved(save=save, bank={})

    bank: Bank = {
        core: dict(slots) for core, slots in (parent.bank if parent else {}).items()
    }
    for core, slots in manifest.states.items():
        if slots:
            bank[core] = dict(slots)
        else:
            bank.pop(core, None)
    return Resolved(save=save, bank=bank)


def snapshot_digest(
    save: SaveEntry | None, bank: Mapping[str, Mapping[str, str]]
) -> str:
    """sha256 over the canonical JSON of a resolved snapshot. The only digest implementation."""
    document = {
        "save": (
            {
                "hash": save.hash,
                "shape": save.shape.value if save.shape else None,
                "format": save.format.value if save.format else None,
            }
            if save
            else None
        ),
        "states": {core: dict(slots) for core, slots in bank.items() if slots},
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
