"""How the legacy save API's slots map onto channels."""

from collections.abc import Iterable
from typing import Final

from handler.snapshots.file_key import FileKey
from models.assets import Save
from models.channel import DEFAULT_CHANNEL_LABEL
from models.rom import RomFile, RomFileCategory
from utils.uploads import DATETIME_TAG_PATTERN

# The slot names clients have used for the save a game makes on its own.
DEFAULT_SLOTS: Final = frozenset({"autosave", "default"})
# The file an emulator loads from a multi-file disc set, ahead of its tracks.
LOADER_EXTENSIONS: Final = frozenset({"cue", "gdi", "ccd", "mds", "toc"})
# Slots some clients used to file states as saves; they map to no channel.
STATE_SLOT_PREFIX: Final = "state_"


def channel_label(slot: str) -> str | None:
    """The channel a legacy slot files a save under, or None for none."""
    label = DATETIME_TAG_PATTERN.sub("", slot).strip()
    if not label or label.lower().startswith(STATE_SLOT_PREFIX):
        return None
    if label.lower() in DEFAULT_SLOTS:
        return DEFAULT_CHANNEL_LABEL
    return label


def may_load(
    save: Save,
    emulators: Iterable[str | None] | None,
    cores: Iterable[str | None] | None,
) -> bool:
    """Whether a client running one of `cores` or `emulators` might load `save`."""
    named_cores = {c.lower() for c in cores or () if c}
    if save.core and named_cores:
        return save.core.lower() in named_cores
    named_emulators = {e.lower() for e in emulators or () if e}
    if save.emulator and named_emulators:
        return save.emulator.lower() in named_emulators
    return True


def sync_file(files: Iterable[RomFile]) -> RomFile | None:
    """The file a ROM's channels key to: the one an emulator loads, such as a
    `.cue`, else the first by name."""
    games = sorted(
        (
            f
            for f in files
            if f.category in (None, RomFileCategory.GAME) and not f.missing_from_fs
        ),
        key=lambda f: f.file_name.lower(),
    )
    loaders = [
        f for f in games if f.file_name.rsplit(".", 1)[-1].lower() in LOADER_EXTENSIONS
    ]
    candidates = loaders or games
    return candidates[0] if candidates else None


def sync_key(files: Iterable[RomFile]) -> FileKey | None:
    rom_file = sync_file(files)
    return FileKey.of_file(rom_file) if rom_file else None
